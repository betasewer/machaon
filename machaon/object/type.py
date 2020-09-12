import os
import re
from inspect import signature

from typing import Any, Sequence, List, Dict, Union, Callable, ItemsView, Optional

from machaon.object.typename import normalize_typename, BadTypename
from machaon.object.method import Method, methoddecl_setter_chain, methoddecl_collect_attribute, UnloadedMethod, BadMethodName
from machaon.object.importer import attribute_loader
from machaon.object.docstring import DocStringParser

# imported from...
# desktop
# object
# formula
# dataset
#

# 型宣言における間違い
class BadTraitDeclaration(Exception):
    pass

# メソッド宣言における間違い
class BadMemberDeclaration(Exception):
    pass

# メソッド実装を読み込めない
class BadMethodDelegation(Exception):
    pass
    
# サポートされない
class UnsupportedMember(Exception):
    pass

#
TYPE_METHODS_INSTANCE_BOUND = 0x01
TYPE_METHODS_TYPE_BOUND = 0x02

#
#
#
class Type():
    __mark = True

    def __init__(self, implklass=None):
        self.typename: str = None
        self.doc: str = ""
        self.flags = 0
        self.value_type: Callable = None
        self._methods: Dict[str, Method] = {}
        self._methodalias: Dict[str, TypeMemberAlias] = {}
        self._implklass = implklass
    
    def __str__(self):
        return "<Type '{}'>".format(self.typename)

    def is_undescribed(self):
        return not self.typename
    
    def get_value_type(self):
        return self.value_type
    
    def copy(self):
        t = Type()
        t.typename = self.typename
        t.doc = self.doc
        t.flags = self.flags
        t.value_type = self.value_type
        t._methods = self._methods.copy()
        t._methodalias = self._methodalias.copy()
        t._implklass = self._implklass
        return t

    #
    #
    #
    def construct_from_string(self, arg: str):
        m = self.method_delegation("construct", fallback=True)
        if m:
            return m(self, arg)
        else:
            # デフォルト動作
            return self.get_value_type()(arg)

    def convert_to_string(self, v: Any):
        m = self.method_delegation("stringify", fallback=True)
        if m:
            return m(self, v)
        else:
            # デフォルト動作
            if v is None:
                return ""
            return str(v)

    # 
    # メソッド呼び出し
    #
    # エイリアスは参照せず、ロードされていなければエラー
    def get_method(self, name) -> Optional[Method]:
        meth = self._methods.get(name, None)
        if meth and not meth.is_loaded():
            raise UnloadedMethod()
        return meth
        
    # エイリアスも参照して探し、ロードされていなければロードする
    def select_method(self, name) -> Optional[Method]:
        meth = self._methods.get(name, None)
        if meth is None:
            name2 = self.get_method_alias(name)
            if name2 is not None:
                meth = self._methods.get(name2)
        if meth:
            meth.load(self)
        return meth

    def enum_methods(self):
        for meth in self._methods.values():
            yield meth
    
    def add_method(self, method):
        name = method.name
        if name in self._methods:
            raise BadMethodName("重複しています")
        self._methods[name] = method
    
    # メソッドの実装を解決する
    def method_delegation(self, attrname, *, fallback=False):
        fn = getattr(self._implklass, attrname, None)
        if fn is None:
            if not fallback:
                raise BadMethodDelegation(attrname)
            return None
        return fn
    
    def get_method_delegator(self):
        return self._implklass
    
    def is_method_bound(self, bound):
        if bound == "TYPE":
            return (self.flags & TYPE_METHODS_TYPE_BOUND) > 0
        else: # bound == "INSTANCE"
            return (self.flags & TYPE_METHODS_INSTANCE_BOUND) > 0

    #
    # メソッド名のエイリアスを取得する
    #
    def get_method_alias(self, name) -> Optional[str]:
        a = self._methodalias.get(name, None)
        if a and not a.is_row():
            return a.get_destination()
        return None
    
    def get_member_group(self, name) -> Optional[List[str]]:
        a = self._methodalias.get(name, None)
        if a:
            if a.is_row():
                return a.get_destination()
            else:
                return [a.get_destination()]
        return None

    def enum_member_alias(self):
        for meth in self._methodalias.values():
            yield meth
    
    def add_member_alias(self, name, dest):
        self._methodalias[name] = TypeMemberAlias(name, dest)

    #
    # 型定義構文用のメソッド
    #
    def describe(self, 
        typename = "",
        doc = "",
        value_type = None,
    ):
        if typename:
            self.typename = normalize_typename(typename)
        if doc:
            self.doc = doc
        if value_type:
            self.value_type = value_type
        return self 
    
    # メソッドのプロトタイプを記述する
    def __getitem__(self, declaration):
        if not isinstance(declaration, str):
            raise TypeError("declaration")
        
        decl, _, restpart = [x.strip() for x in declaration.lstrip().partition(" ")]
        if decl == "alias":
            if not restpart:
                raise BadMemberDeclaration("エイリアスに名前が設定されていません")
            origname = restpart
            def alias_(name):
                self.add_member_alias(origname, name)
                return self
            return alias_
        elif decl in ("method", "task"):
            return methoddecl_setter_chain(self, decl, restpart)
        else:
            raise BadMemberDeclaration("不明な宣言タイプ：'{}'です".format(decl))

    # describeの中で使用できる
    def describe_method(self, **kwargs):
        return Method(**kwargs)
    
    #
    def describe_from_docstring(self, doc):
        # structure of type docstring
        """ summary
        detailed description...
        .......................
        ....
        ValueType:
            <Typename>

        Typename:
            <Alias names>

        MemberAlias:
            long: (mode ftype modtime size name)
            short: (ftype name)
            link: path
        """
        #
        # 型定義の解析
        #
        sections = DocStringParser(doc, ("Typename", "ValueType", "MemberAlias"))

        typename = sections.get_value("Typename")
        if typename:
            self.typename = typename.capitalize()
    
        doc = sections.get_string("Summary", "Description")
        if doc:
            self.doc = doc.strip()

        valtypename = sections.get_value("ValueType")
        if valtypename:
            loader = attribute_loader(valtypename, implicit_syntax=True)
            self.value_type = loader() # 例外発生の可能性
        
        aliases = sections.get_lines("MemberAlias")
        for alias in aliases:
            name, _, dest = [x.strip() for x in alias.partition(":")]
            if not name or not dest:
                raise BadTraitDeclaration()

            if dest[0] == "(" and dest[-1] == ")":
                row = dest[1:-1].split()
                self.add_member_alias(name, row)

    #
    #
    #
    def load(self, describer):
        if hasattr(describer, "describe_object"):
            # 記述メソッドを呼び出す
            describer.describe_object(self) # type: ignore
        elif hasattr(describer, "__doc__"):
            # ドキュメント文字列を解析する
            self.describe_from_docstring(describer.__doc__)
            # メソッド属性を列挙する
            methoddecl_collect_attribute(self, describer)
        else:
            raise BadTraitDeclaration("型定義がありません。クラスメソッド 'describe_object' かドキュメント文字列で記述してください")
        
        # 専用のフォールバック値として
        if not self.typename and hasattr(describer, "__name__"):
            self.typename = normalize_typename(describer.__name__)

        if not self.doc and hasattr(describer, "__doc__"):
            self.doc = describer.__doc__
        
        if not self.value_type and isinstance(describer, type):
            self.value_type = describer
        
        # メソッドに渡すselfの意味
        if self.value_type is describer:
            self.flags |= TYPE_METHODS_INSTANCE_BOUND
        else:
            self.flags |= TYPE_METHODS_TYPE_BOUND
        
        if isinstance(describer, type):
            # typemodule.getで識別子として使用可能にする
            setattr(describer, "Type_typename", self.typename) 
        
        return self

#
# 型の取得時まで定義の読み込みを遅延する
#
class TypeDelayLoader():
    def __init__(self, traits, typename):
        self.traits = traits
        self.typename = typename
        if not isinstance(typename, str):
            raise ValueError("型名を文字列で指定してください")

#
#
#
class TypeMemberAlias:
    def __init__(self, name, dest):
        self.name = name
        self.dest = dest
    
    def get_name(self):
        return self.name
    
    def get_destination(self):
        return self.dest
    
    def is_row(self):
        return isinstance(self.dest, tuple)

#
# 型取得インターフェース
#
class TypeModule():
    def __init__(self):
        self._typelib: Dict[str, Type] = {}
        self._ancestors: List[TypeModule] = [] 
        
    #
    def exists(self, typename: str) -> bool:
        return typename in self._typelib
    
    def find(self, typename: str) -> Optional[Type]:
        # 自分自身の定義を探索
        if typename in self._typelib:
            return self._typelib[typename]
        
        # 親モジュールを探索
        for ancmodule in self._ancestors:
            tt = ancmodule.find(typename)
            if tt is not None:
                return tt

        # 見つからなかった
        return None

    #
    # 型を取得する
    #
    def get(self, typecode: Any, fallback = False) -> Optional[Type]:
        if self._typelib is None:
            raise ValueError("No type library set up")

        if isinstance(typecode, str):
            typename = normalize_typename(typecode)
            t = self.find(typename)
        elif isinstance(typecode, Type):
            t = typecode
        elif hasattr(typecode, "Type_typename"):
            typename = typecode.Type_typename
            t = self.find(typename)
        else:
            raise ValueError("型識別子として無効な値です：{}".format(typecode))
        
        if t is None and not fallback:
            raise BadTypename(typecode)

        # 遅延された読み込みを実行する
        if isinstance(t, TypeDelayLoader):
            t = self.define(t.traits, typename=t.typename)
        
        return t

    # objtypes[<typename>] -> Type
    def __getitem__(self, typecode) -> Optional[Type]:
        return self.get(typecode)

    # objtypes.<typename> -> Type
    def __getattr__(self, name) -> Optional[Type]:
        typename = normalize_typename(name)
        return self.get(typename)
    
    #
    # 取得し、無ければ定義する
    #
    def new(self, typecode):
        tt = self.get(typecode, fallback=True)
        if tt is None:
            if isinstance(typecode, str):
                # 実質は文字列と同一の新しい型を作成
                tt = self.define(typename=typecode, doc="<Prototype {}>".format(typecode))
            else:
                tt = self.define(typecode)
        return tt

    #
    # 型を定義する
    #
    def define(self, 
        traits: Any = None,
        *,
        typename = None, 
        doc = "",
        memberdefs: Dict[str, Any] = None,
    ) -> Type:
        # 登録処理
        t: Any = None # 型オブジェクトのインスタンス
        if traits is None:
            # 辞書で中身を定義する型
            t = self.define_prototype(memberdefs)                
        elif isinstance(traits, TypeDelayLoader):
            t = traits
        elif isinstance(traits, Type):
            # Traitsまたは派生型のインスタンスが渡された
            t = traits.copy()
        elif isinstance(traits, type):
            # 実装移譲先のクラス型が渡された
            t = Type(implklass=traits)
            t.load(traits)
        else:
            raise TypeError("TypeModule.defineの引数型が間違っています：{}".format(type(traits).__init__))
        
        if typename or doc:
            t.describe(typename, doc)

        if not t.typename or t.typename[0].islower():
            raise BadTypename("{}: 型名は1字以上、大文字で始めてください".format(t.typename))
        self._typelib[t.typename] = t

        return t
    
    # 遅延登録デコレータ
    def definition(self, *, typename):
        def _deco(traits):
            self.define(traits=TypeDelayLoader(traits, typename))
            return traits
        return _deco
    
    def define_prototype(self, memberdefs=None): 
        # 
        t = Type()
        if memberdefs:
            def getter(k):
                return lambda x:x[k]
            for key, typename in memberdefs.items():
                mth = Method(key)
                mth.add_result(typename)
                mth.set_action(getter(key))
                t.add_method(mth)
        else:
            t.describe(value_type=str)
        return t

    #
    #
    #
    def add_ancestor(self, other): # type: (TypeModule) -> None
        self._ancestors.append(other)
    
    def add_fundamental_types(self):
        from machaon.object.fundamental import fundamental_type
        self.add_ancestor(fundamental_type)




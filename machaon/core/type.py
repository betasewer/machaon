import os
import re
from inspect import signature
from collections import defaultdict

from typing import Any, Sequence, List, Dict, Union, Callable, ItemsView, Optional, Generator, Tuple, DefaultDict

from machaon.core.symbol import normalize_typename, BadTypename, BadMethodName, PythonBuiltinTypenames
from machaon.core.method import Method, methoddecl_collect_attributes, UnloadedMethod, MethodLoadError
from machaon.core.importer import attribute_loader
from machaon.core.docstring import DocStringParser

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
class UnsupportedMethod(Exception):
    pass

#
TYPE_ANYTYPE = 0x1
TYPE_OBJCOLTYPE = 0x2
TYPE_TYPETRAIT_DESCRIBER = 0x100
TYPE_VALUETYPE_DESCRIBER = 0x200
TYPE_USE_INSTANCE_METHOD = 0x400
TYPE_LOADED = 0x1000

#
#
#
class Type():
    __mark = True

    def __init__(self, describer=None, name=None, value_type=None, scope=None, *, bits = 0):
        self.typename: str = name
        self.doc: str = ""
        self.flags = bits
        self.value_type: Callable = value_type
        self.scope: Optional[str] = scope
        self._methods: Dict[str, Method] = {}
        self._methodalias: Dict[str, TypeMemberAlias] = {}
        self._describer = describer
    
    @property
    def fulltypename(self):
        fulltypename = self.typename
        if self.scope:
            fulltypename = self.scope + "." + fulltypename
        return fulltypename
    
    def __str__(self):
        return "<Type '{}'>".format(self.typename)

    def is_loaded(self):
        return self.flags & TYPE_LOADED > 0
    
    def is_any(self):
        return self.flags & TYPE_ANYTYPE > 0
    
    def is_object_collection(self):
        return self.flags & TYPE_OBJCOLTYPE > 0
    
    def get_value_type(self):
        return self.value_type
    
    def is_scope(self, scope):
        return self.scope == scope
    
    def get_describer(self):
        return self._describer
    
    def get_describer_qualname(self):
        if isinstance(self._describer, type):
            return ".".join([self._describer.__module__, self._describer.__qualname__])
        else:
            return str(self._describer)

    def get_describer_instance(self):
        if isinstance(self._describer, type):
            return self._describer()
        else:
            return self._describer

    def copy(self):
        t = Type()
        t.typename = self.typename
        t.doc = self.doc
        t.flags = self.flags
        t.value_type = self.value_type
        t.scope = self.scope
        t._methods = self._methods.copy()
        t._methodalias = self._methodalias.copy()
        t._describer = self._describer
        return t
    
    def new_object(self, value):
        """ この型のオブジェクトを作る。型変換は行わない """
        from machaon.core.object import Object
        return Object(self, value)

    #
    #
    #
    def construct_from_string(self, arg: str):
        r = self.call_internal_method("construct", "t", arg)
        if r:
            return r[0]
        else:
            # デフォルト動作
            raise UnsupportedMethod("construct")

    def convert_to_string(self, v: Any):
        r = self.call_internal_method("stringify", "i", v)
        if r:
            return r[0]
        else:
            # デフォルト動作
            return str(v) if v is not None else ""

    def summarize_value(self, v: Any):
        r = self.call_internal_method("summarize", "i", v)
        if r:
            return r[0]
        else:
            try:
                s = self.convert_to_string(v)
            except UnsupportedMethod:
                return "{} <summary unsupported>".format(v)
            s = s.replace("\n", " ").strip()
            return s[0:50]+"..." if len(s)>50 else s

    def pprint_value(self, app, v: Any):
        r = self.call_internal_method("pprint", "i", v, app)
        if r:
            return None
        else:
            try:
                s = self.convert_to_string(v)
            except UnsupportedMethod:
                s = "{} <pretty print unsupported>".format(v)
            app.post("message", s)
    
    def conversion_construct(self, context, value, *params):
        r = self.call_internal_method("conversion_construct", "t", context, value, *params)
        if r:
            return r[0]
        else:
            if self.value_type is None: # 制限なし
                return value
            
            def modqualname(t):
                n = getattr(self.value_type, "__name__", None)
                m = getattr(self.value_type, "__module__", None)
                if n and m:
                    return "{}.{}".format(m,n)
                else:
                    return str(t)
            l_name = modqualname(type(value))
            r_name = modqualname(self.value_type)
            raise ValueError("'{}' -> '{}'への変換関数が定義されていません".format(l_name, r_name))

    def construct_from_value(self, context, value, *params):
        if self.check_value_type(type(value)):
            return value 
        elif isinstance(value, str):
            return self.construct_from_string(value)
        else:
            return self.conversion_construct(context, value, *params)
    
    def check_value_type(self, value_type):
        if self.value_type is None: # 制限なし
            return True
        return self.value_type is value_type

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
            name2 = self.get_member_alias(name)
            if name2 is not None:
                meth = self._methods.get(name2)
        
        if meth:
            try:
                meth.load(self)
            except Exception as e:
                raise MethodLoadError(e, meth.name).with_traceback(e.__traceback__)
        return meth

    def enum_methods(self):
        for name, meth in self._methods.items():
            try:
                meth.load(self)
            except Exception as e:
                raise MethodLoadError(e, name)
            yield meth
    
    def add_method(self, method):
        name = method.name
        if name in self._methods:
            raise BadMethodName("{}: メソッド名が重複しています".format(name))
        self._methods[name] = method
    
    # メソッドの実装を解決する
    def delegate_method(self, attrname, *, fallback=True):
        fn = getattr(self._describer, attrname, None)
        if fn is None:
            if not fallback:
                raise BadMethodDelegation(attrname)
            return None
        return fn
    
    # 内部実装で使うメソッドを実行する
    #  -> タプルで返り値を返す。見つからなければNone
    def call_internal_method(self, attrname, calltype, *args, **kwargs):
        fn = self.delegate_method(attrname) # 実装クラスから探す
        if fn:
            if calltype == "i":
                if self.is_methods_instance_bound():
                    pass
                elif self.is_methods_type_bound():
                    args = (self, *args)
            elif calltype == "t":
                args = (self, *args)
            else:
                raise ValueError("bad calltype")

            r = (fn(*args, **kwargs),)
            return r

        return None
    
    @classmethod
    def from_dict(cls, d):
        return cls(d).load()

    @property
    def describer(self):
        return self._describer

    def is_methods_type_bound(self):
        return (self.flags & TYPE_TYPETRAIT_DESCRIBER) > 0
    
    def is_methods_instance_bound(self):
        return (self.flags & TYPE_VALUETYPE_DESCRIBER) > 0

    def is_using_instance_method(self):
        return (self.flags & TYPE_USE_INSTANCE_METHOD) > 0

    #
    # メソッド名のエイリアスを取得する
    #
    def get_member_alias(self, name) -> Optional[str]:
        a = self._methodalias.get(name, None)
        if a and not a.is_group_alias():
            return a.get_destination()
        return None
    
    def get_member_group(self, name) -> Optional[List[str]]:
        a = self._methodalias.get(name, None)
        if a:
            if a.is_group_alias():
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
        scope = None,
        bits = 0,
    ):
        if typename:
            self.typename = normalize_typename(typename)
        if doc:
            self.doc = doc
        if value_type:
            self.value_type = value_type
        if scope:
            self.scope = scope
        if bits:
            self.flags |= bits
        return self
    
    #
    def describe_from_docstring(self, doc):
        # structure of type docstring
        """ @type (no-instance-method)
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
        sections = DocStringParser(doc, ("Typename", "Params", "ValueType", "MemberAlias"))

        typename = sections.get_value("Typename")
        if typename:
            if typename[0].islower():
                typename = typename[0].upper() + typename[1:]
            self.typename = typename
    
        doc = ""
        sumline = sections.get_string("Decl")
        for line in sumline.split():
            if line == "@type":
                continue
            elif line == "use-instance-method":
                self.flags |= TYPE_USE_INSTANCE_METHOD
            elif line == "trait":
                self.flags |= TYPE_TYPETRAIT_DESCRIBER
            else:
                doc += line

        doc += sections.get_string("Description")
        if doc:
            self.doc = doc.strip()

        valtypename = sections.get_value("ValueType")
        if valtypename == "Any":
            self.value_type = None # Any型
        elif valtypename:
            loader = attribute_loader(valtypename)
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
    def load(self):
        if self.is_loaded():
            return

        describer = self._describer
        
        if isinstance(describer, dict):
            # 辞書オブジェクトによる記述
            for key, value in describer.items():
                if key == "Typename":
                    self.typename = value
                elif key == "Doc":
                    self.doc = value
                elif key == "ValueType":
                    self.value_type = value
                else:
                    # メソッド定義
                    from machaon.core.object import Object
                    if len(value)>1 and callable(value[-1]):                      
                        *docs, action = value
                        mth = Method(key)
                        mth.load_from_string("\n".join(docs), action)
                    else:
                        raise ValueError("任意個のドキュメント文字列と、一つの関数のタプルが必要です")
                    self.add_method(mth)
                
        elif hasattr(describer, "describe_object"):
            # 記述メソッドを呼び出す
            describer.describe_object(self) # type: ignore

        elif hasattr(describer, "__doc__") and describer.__doc__:
            # ドキュメント文字列を解析する
            self.describe_from_docstring(describer.__doc__)
            # メソッド属性を列挙する
            methoddecl_collect_attributes(self, describer)

        else:
            raise BadTraitDeclaration("型定義がありません。辞書か、定義クラスのドキュメント文字列で記述してください")
        
        # TYPE_XXX_DESCRIBERフラグを推定する
        if self.flags & (TYPE_TYPETRAIT_DESCRIBER|TYPE_VALUETYPE_DESCRIBER) == 0:
            if self.value_type and describer is not self.value_type: 
                # 別の値型が定義されているならTYPETRAIT
                self.flags |= TYPE_TYPETRAIT_DESCRIBER
            else: 
                # describerを値型とする
                self.flags |= TYPE_VALUETYPE_DESCRIBER
                self.value_type = describer

        # 専用のフォールバック値として
        if not self.typename:
            if hasattr(describer, "__name__"):
                self.typename = normalize_typename(describer.__name__)
            if not self.typename:
                raise BadTypename("{}: 型名を指定してください".format(self.get_describer_qualname()))

        if self.typename[0].islower():
            raise BadTypename("{}: 型名は大文字で始めてください".format(self.typename))

        if not self.doc:
            if hasattr(describer, "__doc__"):
                self.doc = describer.__doc__
        
        if isinstance(describer, type):
            # typemodule.getで識別子として使用可能にする
            setattr(describer, "Type_typename", self.fulltypename) 
        
        # ロード完了
        self.flags |= TYPE_LOADED

        return self

#
# 型の取得時まで定義の読み込みを遅延する
#
class TypeDelayLoader():
    def __init__(self, traits: Union[str, Any], typename: str, doc, scope, bits):
        self.traits = traits
        self.typename = typename
        if not isinstance(typename, str):
            raise ValueError("型名を文字列で指定してください")
        self.doc = doc
        self.scope = scope
        self.bits = bits
        self._t = None
    
    def get_describer_qualname(self):
        if isinstance(self.traits, str):
            return self.traits
        else:
            return ".".join([self.traits.__module__, self.traits.__qualname__])
    
    def is_loaded(self):
        return self._t is not None

    def get_value_type(self):
        return None
    
    def is_scope(self, scope):
        return self.scope == scope
    
    def load(self, typemodule):
        if self._t is None:
            traits = None
            if isinstance(self.traits, str):
                from machaon.core.importer import attribute_loader
                loader = attribute_loader(self.traits)
                traits = loader()
            else:
                traits = self.traits
            
            self._t = typemodule.define(
                traits, 
                typename=self.typename, 
                doc=self.doc, scope=self.scope, bits=self.bits,
                delayedload=True
            )
            self.traits = None
            self.doc = ""
        return self._t

#
#
#
class TypeMemberAlias:
    def __init__(self, name, dest):
        self.name = name
        if isinstance(dest, str):
            self.dest = dest
        else:
            self.dest = list(dest)

    def get_name(self):
        return self.name
    
    def get_destination(self):
        return self.dest

    def is_group_alias(self):
        return isinstance(self.dest, list)

#
# 型取得インターフェース
#
class TypeModule():
    def __init__(self):
        self._typelib: DefaultDict[str, List[Type]] = defaultdict(list)
        self._ancestors: List[TypeModule] = [] 
    
    def _load_type(self, t: Union[Type, TypeDelayLoader]):
        if isinstance(t, TypeDelayLoader):
            return t.load(self)
        else:
            return t
    
    def _select_by_scope(self, typename, scope):
        t = None
        for t in self._typelib[typename]:
            if t.is_scope(scope):
                return t
        else:
            if scope is None:
                return t
        return None

    #
    def exists(self, typename: str) -> bool:
        return typename in self._typelib
    
    def find(self, typename: str, *, scope=None) -> Optional[Type]:
        # 自分自身の定義を探索
        if typename in self._typelib:
            t = self._select_by_scope(typename, scope)
            return self._load_type(t) # 遅延されたロードを行なう
        
        # 親モジュールを探索
        for ancmodule in self._ancestors:
            tt = ancmodule.find(typename, scope=scope)
            if tt is not None:
                return tt

        # 見つからなかった
        return None
    
    #
    # 型を取得する
    #
    def get(self, typecode: Any, fallback=True, *, scope=None) -> Optional[Type]:
        if self._typelib is None:
            raise ValueError("No type library set up")
        
        t = None
        if isinstance(typecode, str):
            typename = normalize_typename(typecode)
            t = self.find(typename, scope=scope)
        elif isinstance(typecode, Type):
            t = typecode
        elif hasattr(typecode, "Type_typename"):
            fulltypename = typecode.Type_typename
            if "." in fulltypename:
                thisscope, _, typename = fulltypename.partition(".")
            else:
                thisscope, typename = None, fulltypename
            t = self.find(typename, scope=thisscope)
        elif not fallback:
            raise ValueError("型識別子として無効な値です：{}".format(typecode))
        
        if t is None:
            if not fallback:
                raise BadTypename(typecode)
            return None

        return t

    # すべての型を取得する
    def enum(self) -> Generator[Type, None, None]:
        for ancs in self._ancestors:
            for t in ancs.enum():
                yield t

        for _, ts in self._typelib.items():
            for t in ts:
                yield self._load_type(t)
    
    #
    # 取得し、無ければ定義する
    #
    def new(self, typecode, *, scope=None):
        tt = self.get(typecode, scope=scope)
        if tt is None:
            if isinstance(typecode, str):
                # 実質は文字列と同一の新しい型を作成
                tt = self.define(typename=typecode, doc="<Prototype {}>".format(typecode), scope=scope)
            else:
                tt = self.define(typecode, scope=scope)
        return tt
        
    #
    # 値型に適合する型を取得する
    #    
    def deduce(self, value_type) -> Optional[Type]:
        if not isinstance(value_type, type):
            raise TypeError("value_type must be type instance, not value")

        t = self.get(value_type)
        if t:
            return t
        
        if hasattr(value_type, "__name__"): 
            typename = value_type.__name__
            if typename in PythonBuiltinTypenames.literals: # 基本型
                return self.get(typename.capitalize())
            elif typename in PythonBuiltinTypenames.dictionaries: # 辞書型
                return self.get("ObjectCollection")
            elif typename in PythonBuiltinTypenames.iterables: # イテラブル型
                return self.get("Tuple")

        for _tn, ts in self._typelib.items(): # 型を比較する
            for t in ts:
                if t.get_value_type() is value_type:
                    return t
        
        # 親モジュールを探索
        for ancmodule in self._ancestors:
            tt = ancmodule.deduce(value_type)
            if tt is not None:
                return tt

        # 見つからなかった
        return None

    #
    # 型を定義する
    #
    def define(self, 
        traits: Any = None,
        *,
        typename = None, 
        doc = "",
        scope = None,
        bits = 0,
        delayedload = False
    ) -> Type:
        # 登録処理
        t: Any = None # 型オブジェクトのインスタンス
        if traits is None:
            # 実質文字列型
            t = Type({})
        elif isinstance(traits, TypeDelayLoader):
            t = traits
        elif isinstance(traits, Type):
            # Traitsまたは派生型のインスタンスが渡された
            t = traits.copy() # 複製する
        elif isinstance(traits, type) or isinstance(traits, dict):
            # 実装移譲先のクラス型が渡された
            t = Type(traits)
        else:
            raise TypeError("TypeModule.defineの引数型が間違っています：{}".format(type(traits).__name__))
        
        if isinstance(t, Type):
            t.describe(typename=typename, doc=doc, scope=scope, bits=bits)
            t.load()

        if not delayedload:
            self._typelib[t.typename].append(t)

        return t
    
    # 遅延登録デコレータ
    def definition(self, *, typename, doc="", scope=None, bits=0):
        def _deco(traits):
            self.define(traits=TypeDelayLoader(traits, typename, doc, scope, bits))
            return traits
        return _deco
    
    #
    def remove_scope(self, scope):
        raise NotImplementedError()

    #
    #
    #
    def add_ancestor(self, other): # type: (TypeModule) -> None
        self._ancestors.append(other)
    
    def add_fundamental_types(self):
        from machaon.types.fundamental import fundamental_type
        self.add_ancestor(fundamental_type)




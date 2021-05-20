import os
import re
from inspect import signature
from collections import defaultdict

from typing import Any, Sequence, List, Dict, Union, Callable, ItemsView, Optional, Generator, Tuple, DefaultDict

from machaon.core.symbol import BadTypename, normalize_typename, BadMethodName, PythonBuiltinTypenames, full_qualified_name, is_valid_typename
from machaon.core.method import BadMethodDeclaration, Method, make_method_prototype, meta_method_prototypes, UnloadedMethod, MethodLoadError, MetaMethod
from machaon.core.importer import attribute_loader
from machaon.core.docstring import DocStringParser, parse_doc_declaration

# imported from...
# desktop
# object
# formula
# dataset
#

# 型宣言における間違い
class BadTypeDeclaration(Exception):
    pass

# メソッド宣言における間違い
class BadMemberDeclaration(Exception):
    pass

# メソッド実装を読み込めない
class BadMethodDelegation(Exception):
    pass

# メタメソッド呼び出し時のエラー
class BadMetaMethod(Exception):
    def __init__(self, error, type, method):
        super().__init__(error, type, method)
    
    def __str__(self):
        err = type(self.args[0]).__name__
        typename = self.args[1].typename
        methname = self.args[2].get_action_target()
        return " BadMetaMethod({}.{}) {} {}".format(typename, methname, err, self.args[0])
    
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
TYPE_DELAY_LOAD_METHODS = 0x2000

#
#
#
class Type():
    def __init__(self, describer=None, name=None, value_type=None, scope=None, *, bits = 0):
        self.typename: str = name
        self.doc: str = ""
        self.flags = bits
        self.value_type: Callable = value_type
        self.scope: Optional[str] = scope
        self._methods: Dict[str, Method] = {}
        self._methodalias: Dict[str, List[TypeMemberAlias]] = defaultdict(list)
        self._describer = describer
        self._metamethods: Dict[str, MetaMethod] = {}
    
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
            return full_qualified_name(self._describer)
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
        if isinstance(value, Object):
            if value.type is not self:
                raise ValueError("'{}' -> '{}' 違う型のオブジェクトです".format(value.get_typename(), self.typename))
            return value
        else:
            if not self.check_value_type(type(value)):
                raise ValueError("'{}' -> '{}' 値の型に互換性がありません".format(type(value).__name__, self.typename))
            return Object(self, value)

    #
    # 内部実装で使うメソッドを実行する
    #  -> タプルで返り値を返す。見つからなければNone
    def invoke_meta_method(self, method, *args, **kwargs):
        """ 
        内部実装で使うメソッドを実行する
        Params:
            method(MetaMethod): メソッド
            calltype(str): i = selfは第一オブジェクト  t = selfは型インスタンス
            *args
            **kwargs
        Returns:
            Any: 実行したメソッドの返り値
        """
        if method.is_type_bound():
            args = (self, *args)
        else:
            if self.is_methods_instance_bound():
                pass
            elif self.is_methods_type_bound():
                args = (self, *args)

        fn = self.delegate_method(method.get_action_target())
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            raise BadMetaMethod(e, self, method)
    
    def construct(self, context, value, *args):
        if self.check_value_type(type(value)):
            return value # 変換の必要なし
        
        fn = self._metamethods.get("constructor")
        if fn is None:
            raise UnsupportedMethod("'{}'型には型変換関数'constructor'が定義されていません".format(self.typename))
        
        if fn.has_extra_args():
            return self.invoke_meta_method(fn, context, value, *args)
        else:
            return self.invoke_meta_method(fn, context, value)

    def convert_to_string(self, value: Any) -> str:
        fn = self._metamethods.get("stringify")
        if fn is None:
            # デフォルト動作
            if type(value).__str__ is object.__str__:
                return "<Object {:0X}({})>".format(id(value), type(value).__name__)
            else:
                return str(value)

        return self.invoke_meta_method(fn, value)

    def summarize_value(self, value: Any):
        fn = self._metamethods.get("summarize")
        if fn is None:
            s = self.convert_to_string(value)
            if not isinstance(s, str):
                s = repr(s) # オブジェクトに想定されない値が入っている
            s = s.replace("\n", " ").strip()
            if len(s) > 50:
                return s[0:30] + "..." + s[-20:]
            else:
                return s
        
        return self.invoke_meta_method(fn, value)

    def pprint_value(self, app, value: Any):
        fn = self._metamethods.get("pprint")
        if fn is None:
            s = self.convert_to_string(value)
            app.post("message", s)
            return
        self.invoke_meta_method(fn, value, app)

    def check_value_type(self, value_type):
        if self.flags & TYPE_ANYTYPE: # 制限なし
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
    def get_member_alias(self, name: str) -> Optional[str]:
        for x in self._methodalias[name]:
            if not x.is_group_alias():
                return x.get_destination()
        return None
    
    def get_member_group(self, name) -> Optional[List[str]]:
        for x in self._methodalias[name]:
            if x.is_group_alias():
                return x.get_destination()
            else:
                return [x.get_destination()]
        return None

    def add_member_alias(self, name, dest):
        self._methodalias[name].append(TypeMemberAlias(dest))
    
    def get_member_identical_names(self, name: str) -> List[str]:
        """ この名前と同一のメンバを指す名前を全て得る """
        truename = self.get_member_alias(name)
        if truename is None:
            truename = name
        
        l = [truename]
        for aliasname, aliases in self._methodalias.items():
            for a in aliases:
                if a.is_group_alias():
                    continue
                if a.get_destination() == truename:
                    l.append(aliasname)
        return l

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
    #
    #
    def load(self, loadbits=0):
        if self.is_loaded():
            return

        describer = self._describer
        
        # メソッド属性を列挙する
        if loadbits & TYPE_DELAY_LOAD_METHODS == 0:
            if isinstance(describer, dict):
                self.load_methods_from_dict(describer)
            else:
                self.load_methods_from_attributes(describer)
        
        if hasattr(describer, "describe_object"):
            # 追加の記述メソッドを呼び出す
            describer.describe_object(self) # type: ignore
        
        # 値を補完する
        # value_type
        if self.value_type is None:
            if self.describer and self.flags & TYPE_ANYTYPE == 0:
                self.value_type = self.describer

        # typename
        if not self.typename:
            raise BadTypeDeclaration("{}: 型名を指定してください".format(self.get_describer_qualname()))

        if self.typename[0].islower():
            raise BadTypeDeclaration("{}: 型名は大文字で始めてください".format(self.typename))

        # doc
        if not self.doc:
            if hasattr(describer, "__doc__"):
                doc = describer.__doc__
                self.doc = doc.strip() if doc else ""
        
        # フラグの整合性をチェックする
        if self.flags & TYPE_TYPETRAIT_DESCRIBER:
            if describer is self.value_type:
                raise BadTypeDeclaration("trait実装が明示的に指定されましたが、型が値型と同じです")
        
        # TYPE_XXX_DESCRIBERフラグを推定する
        if self.flags & (TYPE_TYPETRAIT_DESCRIBER|TYPE_VALUETYPE_DESCRIBER) == 0:
            if describer is not self.value_type: 
                # 別の値型が定義されているならTYPETRAIT
                self.flags |= TYPE_TYPETRAIT_DESCRIBER
            else: 
                # describerを値型とする
                self.flags |= TYPE_VALUETYPE_DESCRIBER
                self.value_type = describer
        
        if isinstance(describer, type):
            # describerをtypemodule.getで識別子として使用可能にする
            setattr(describer, "Type_typename", self.fulltypename) 

        # ロード完了
        self.flags |= TYPE_LOADED

        return self

    def load_methods_from_attributes(self, describer):
        # クラス属性による記述
        for attrname in dir(describer):
            if attrname.startswith("__"):
                continue

            attr = getattr(describer, attrname)
            method, aliasnames = make_method_prototype(attr, attrname)
            if method is None:
                continue

            self.add_method(method)
            for aliasname in aliasnames:
                self.add_member_alias(aliasname, method.name)
        
        for meth in meta_method_prototypes:
            name = meth.get_action_target()
            attr = getattr(describer, name, None)
            if attr is None:
                continue
            
            decl = parse_doc_declaration(attr, ("meta",))
            if decl is None:
                continue
    
            meth = meth.new(decl.props)
            self._metamethods[name] = meth
        
    def load_methods_from_dict(self, describer):
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
                if len(value)>1 and callable(value[-1]):                      
                    *docs, action = value
                    mth = Method(key)
                    mth.load_from_string("\n".join(docs), action)
                else:
                    raise BadTypeDeclaration("任意個のドキュメント文字列と、一つの関数のタプルが必要です")
                self.add_method(mth)


# describer の文字列に value_typeが書かれている場合もある


class TypeDefinition():
    """
    クラス文字列から型をロードする
    """
    def __init__(self, 
        describer: Union[str, Any] = None, 
        typename: str = None, 
        value_type = None, 
        doc = "", 
        scope = None, 
        bits = 0
    ):
        self.describer = describer
        self.typename = typename
        if typename and not isinstance(typename, str):
            raise ValueError("型名を文字列で指定してください")     
        self.value_type = value_type
        if self.describer is None and self.value_type is not None:
            # 型名のみが指定されているなら、クラス実装もそこにあるとみなす
            self.describer = self.value_type
        self.doc = doc
        self.scope = scope
        self.bits = bits
        self._decl = None
        self._t = None
    
    def get_describer_qualname(self):
        if isinstance(self.describer, str):
            return self.describer
        elif isinstance(self.describer, type):
            return full_qualified_name(self.describer)
        else:
            t = self.get_describer()
            return full_qualified_name(t)
    
    def is_loaded(self):
        return self._t is not None

    def get_value_type(self):
        if isinstance(self.value_type, str):
            loader = attribute_loader(self.value_type)
            return loader()
        else:
            return self.value_type

    def get_describer(self):
        if isinstance(self.describer, str):
            loader = attribute_loader(self.describer)
            return loader()
        elif not isinstance(self.describer, type) and callable(self.describer):
            return self.describer()
        else:
            return self.describer

    def is_scope(self, scope):
        return self.scope == scope
    
    def define(self, typemodule):
        if self._t is not None:
            return self._t
        
        if self._decl is not None:
            self.load_definition_docstring(self._decl)
    
        describer = self.get_describer()

        value_type = self.get_value_type()

        self._t = typemodule.define(
            describer, 
            typename=self.typename, 
            value_type=value_type,
            doc=self.doc, 
            scope=self.scope, 
            bits=self.bits,
            delayedload=True
        )
        return self._t

    def load_declaration_docstring(self, doc=None):
        """
        先頭の宣言のみを読み込み、型名を決める
        """
        if doc is None:
            describer = self.get_describer()
            doc = getattr(describer, "__doc__", None)
            if doc is None:
                return False
        
        decl = parse_doc_declaration(doc, ("type",))
        if decl is None:
            return False
        
        if decl.name:
            self.typename = decl.name
        self._decl = decl
        return True
    
    def load_definition_docstring(self, decl):
        """
        型定義の解析
        """
        """ @type no-instance-method alias-name [aliases...]
        detailed description...
        .......................

        ValueType:
            <Typename>

        MemberAlias:
            long: (mode ftype modtime size name)
            short: (ftype name)
            link: path
        """
        if "use-instance-method" in decl.props:
            self.bits |= TYPE_USE_INSTANCE_METHOD
        if "trait" in decl.props:
            self.bits |= TYPE_TYPETRAIT_DESCRIBER

        sections = DocStringParser(decl.rest, ("ValueType", "MemberAlias",))
    
        document = ""
        document += sections.get_string("Document")
        if document:
            self.doc = document.strip()

        valtypename = sections.get_value("ValueType")
        self.value_type = valtypename
        
        aliases = sections.get_lines("MemberAlias")
        for alias in aliases:
            name, _, dest = [x.strip() for x in alias.partition(":")]
            if not name or not dest:
                raise BadTypeDeclaration()

            if dest[0] == "(" and dest[-1] == ")":
                row = dest[1:-1].split()
                self.add_member_alias(name, row)
    
    def load_docstring(self, doc=None):
        """ デバッグ用 """
        if not self.load_declaration_docstring(doc):
            raise BadMethodDeclaration()
        self.load_definition_docstring(self._decl)


#
#
#
class TypeMemberAlias:
    def __init__(self, dest):
        if isinstance(dest, str):
            self.dest = dest
        else:
            self.dest = list(dest)

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
    
    def _load_type(self, t: Union[Type, TypeDefinition]):
        if isinstance(t, TypeDefinition):
            return t.define(self)
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
    def get(self, typecode: Any, *, scope=None) -> Optional[Type]:
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
                thisscope, _, typename = fulltypename.rpartition(".")
            else:
                thisscope, typename = None, fulltypename
            t = self.find(typename, scope=thisscope)
        
        if t is None:
            return None

        return t

    # すべての型を取得する
    def enum(self, fallback=True) -> Generator[Type, None, None]:
        for ancs in self._ancestors:
            for t in ancs.enum():
                yield t

        for _, ts in self._typelib.items():
            for t in ts:
                try:
                    yield self._load_type(t)
                except Exception as e:
                    if fallback:
                        pass
                    else:
                        raise e
        
    #
    # 値型に適合する型を取得する
    #    
    def deduce(self, value_type) -> Optional[Type]:
        if not isinstance(value_type, type):
            raise TypeError("value_type must be type instance, not value")

        if hasattr(value_type, "__name__"): 
            typename = value_type.__name__
            if typename in PythonBuiltinTypenames.literals: # 基本型
                return self.get(typename.capitalize())
            elif typename in PythonBuiltinTypenames.dictionaries: # 辞書型
                return self.get("ObjectCollection")
            elif typename in PythonBuiltinTypenames.iterables: # イテラブル型
                return self.get("Tuple")
        
        t = self.get(value_type)
        if t:
            return t

        for _tn, ts in self._typelib.items(): # 型を比較する
            for t in ts:
                if t.get_value_type() is value_type:
                    return self._load_type(t)
        
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
        describer: Any = None,
        *,
        typename = None, 
        value_type = None,
        doc = "",
        scope = None,
        bits = 0,
        delayedload = False
    ) -> Type:
        # 登録処理
        t: Any = None # 型オブジェクトのインスタンス
        if describer is None:
            # 実質文字列型
            t = Type({})
        elif isinstance(describer, TypeDefinition):
            t = describer
        elif isinstance(describer, Type):
            # Traitsまたは派生型のインスタンスが渡された
            t = describer.copy() # 複製する
        elif isinstance(describer, dict):
            # 実装を記述した辞書型
            t = Type(describer)
        elif isinstance(describer, type):
            t = Type(describer)
            if typename is None:
                if getattr(describer, "__name__", None) is not None:
                    typename = normalize_typename(describer.__name__)
        else:
            raise TypeError("TypeModule.defineは'{}'型に対応していません：".format(type(describer).__name__))
        
        if isinstance(t, Type):
            t.describe(typename=typename, value_type=value_type, doc=doc, scope=scope, bits=bits)
            t.load()

        if not delayedload:
            key = t.typename
            if key is None:
                raise ValueError("TypeDefinition typename is not defined")
            self._typelib[key].append(t)

        return t
    
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

    # 型登録の構文を提供
    class DefinitionSyntax():
        def __init__(self, parent):
            self._parent = parent
        
        def __getattr__(self, typename):
            if not is_valid_typename(typename):
                raise BadTypename(typename)
            def _define(doc, *, describer=None, value_type=None, scope=None, bits=0):
                d = TypeDefinition(describer, typename, value_type, doc, scope, bits)
                self._parent.define(d)
            return _define
        
    # 遅延登録
    def definitions(self):
        return self.DefinitionSyntax(self)
    
    
    





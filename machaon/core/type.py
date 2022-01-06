from collections import defaultdict

from typing import Any, Sequence, Union, Callable, ItemsView, Optional, Generator, DefaultDict
from typing import List, Dict, Tuple

from machaon.core.symbol import (
    BadTypename, normalize_typename, BadMethodName, PythonBuiltinTypenames, 
    full_qualified_name, is_valid_typename, summary_escape, normalize_method_name,
    SIGIL_SCOPE_RESOLUTION
)
from machaon.core.typedecl import (
    TypeProxy, TypeInstance,
    METHODS_BOUND_TYPE_TRAIT_INSTANCE,
    METHODS_BOUND_TYPE_INSTANCE
)
from machaon.core.method import (
    BadMethodDeclaration, UnloadedMethod, MethodLoadError, BadMetaMethod, make_method_from_dict,
    make_method_prototype, meta_method_prototypes, 
    Method, MetaMethod
)
from machaon.core.importer import ClassDescriber, attribute_loader
from machaon.core.docstring import parse_doc_declaration

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

# サポートされない
class UnsupportedMethod(Exception):
    pass

TYPE_ANYTYPE                = 0x0001
TYPE_OBJCOLTYPE             = 0x0002
TYPE_NONETYPE               = 0x0004
TYPE_TYPETYPE               = 0x0008
TYPE_FUNTYPE                = 0x0010

TYPE_TYPETRAIT_DESCRIBER    = 0x0100
TYPE_VALUETYPE_DESCRIBER    = 0x0200
TYPE_USE_INSTANCE_METHOD    = 0x0400
TYPE_MIXIN                  = 0x0800
TYPE_LOADED                 = 0x1000
TYPE_DELAY_LOAD_METHODS     = 0x2000

#
#
#
class Type(TypeProxy):
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
        self._mixin = []
    
    def __str__(self):
        return "<Type '{}'>".format(self.typename)
    
    def get_typename(self):
        return self.typename
    
    def get_conversion(self):
        if self.scope:
            return self.typename + SIGIL_SCOPE_RESOLUTION + self.scope
        else:
            return self.typename
        
    def get_value_type(self):
        return self.value_type
    
    def get_scoped_typename(self):
        if self.scope:
            return self.typename + SIGIL_SCOPE_RESOLUTION + self.scope
        else:
            return self.typename
    
    def get_describer(self, mixin=None):
        if mixin is not None:
            return self._mixin[mixin]
        else:
            return self._describer
    
    def get_describer_qualname(self, mixin=None):
        describer = self.get_describer(mixin)
        if isinstance(describer, dict):
            return str(describer)
        else:
            return describer.get_qualname()

    def get_document(self):
        return self.doc

    #
    def is_loaded(self):
        return self.flags & TYPE_LOADED > 0
    
    def is_scope(self, scope):
        return self.scope == scope

    def is_same_value_type(self, vt):
        # TypeModule.deduceで使用
        return self.value_type is vt
    
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
    
    #
    #
    #
    def get_typedef(self):
        return self
    
    def check_type_instance(self, type):
        return self is type

    def check_value_type(self, valtype):
        if self.flags & TYPE_ANYTYPE:
            return True # 制限なし
        return issubclass(valtype, self.value_type)

    def instance(self, *args):
        return TypeInstance(self, ctorargs=args)
    
    #
    def is_any_type(self):
        return self.flags & TYPE_ANYTYPE > 0

    def is_none_type(self):
        return self.flags & TYPE_NONETYPE > 0

    def is_object_collection_type(self):
        return self.flags & TYPE_OBJCOLTYPE > 0

    def is_type_type(self):
        return self.flags & TYPE_TYPETYPE > 0

    def is_function_type(self):
        return self.flags & TYPE_FUNTYPE > 0

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
        name = normalize_method_name(name)

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
        """
        Yields:
            Tuple[List[str], Method|Exception]:
        """
        for name, meth in self._methods.items():
            try:
                meth.load(self)
            except Exception as e:
                yield [name], MethodLoadError(e, name)
            else:
                names = self.get_member_identical_names(name)
                yield names, meth
    
    def add_method(self, method):
        name = method.name
        if name in self._methods:
            raise BadMethodDeclaration("{}: メソッド名が重複しています".format(name))
        self._methods[name] = method
    
    # メソッドの実装を解決する
    def delegate_method(self, attrname, mixin_index=None, *, fallback=True):
        if mixin_index is not None:
            describer = self._mixin[mixin_index]
        else:
            describer = self._describer
        fn = describer.get_attribute(attrname)
        if fn is None:
            if not fallback:
                raise BadMethodName(attrname, self.typename)
            return None
        return fn

    @property
    def describer(self):
        return self._describer

    def get_methods_bound_type(self):
        if (self.flags & TYPE_TYPETRAIT_DESCRIBER) > 0:
            return METHODS_BOUND_TYPE_TRAIT_INSTANCE
        else:
            return METHODS_BOUND_TYPE_INSTANCE

    def is_selectable_instance_method(self):
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
    # 特殊メソッド
    #
    def constructor(self, context, value, extraarg=None):
        """ 
        コンストラクタ。
        実装メソッド:
            constructor
        """
        fn = self._metamethods.get("constructor")
        if fn is None:
            # 定義が無い場合、単純に生成する
            return self.value_type(value)

        args = fn.prepare_invoke_args(context, value, extraarg)
        return self.invoke_meta_method(fn, context, *args)
    
    def stringify_value(self, value: Any) -> str:
        """ 
        値を文字列に変換する。
        実装メソッド:
            stringify
        """
        fn = self._metamethods.get("stringify")
        if fn is None:
            # デフォルト動作
            return str(value)

        return self.invoke_meta_method(fn, value)

    def summarize_value(self, value: Any):
        """ 
        値を短い文字列に変換する。
        実装メソッド:
            summarize
        """
        fn = self._metamethods.get("summarize")
        if fn is None:
            s = self.stringify_value(value)
            if not isinstance(s, str):
                s = repr(s) # オブジェクトに想定されない値が入っている
            s = summary_escape(s)
            if len(s) > 50:
                return s[0:30] + "..." + s[-20:]
            else:
                return s
        return self.invoke_meta_method(fn, value)

    def pprint_value(self, app, value: Any):
        """ 
        値を画面に表示する。
        実装メソッド:
            pprint
        """
        fn = self._metamethods.get("pprint")
        if fn is None:
            s = self.stringify_value(value)
            app.post("message", s)
            return
        self.invoke_meta_method(fn, value, app)

    def invoke_meta_method(self, method, *args, **kwargs):
        """ 
        内部実装で使うメソッドを実行する
        Params:
            method(MetaMethod): メソッド
            *args
            **kwargs
        Returns:
            Any: 実行したメソッドの返り値
        """
        if method.is_type_bound():
            args = (self, *args)
        else:
            bt = self.get_methods_bound_type()
            if bt == METHODS_BOUND_TYPE_TRAIT_INSTANCE:
                args = (self, *args)

        fn = self.delegate_method(method.get_action_target(), fallback=False)
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            raise BadMetaMethod(e, self, method)

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
                self.load_methods_from_describer(describer)
        
        if isinstance(describer, ClassDescriber):
            describer.do_describe_object(self)
        
        # 値を補完する
        # value_type
        if self.value_type is None and self.flags & TYPE_ANYTYPE == 0:
            if isinstance(describer, ClassDescriber):
                self.value_type = describer.klass

        # typename
        if not self.typename:
            raise BadTypeDeclaration("{}: 型名を指定してください".format(self.get_describer_qualname()))

        if self.typename[0].islower():
            raise BadTypeDeclaration("{}: 型名は大文字で始めてください".format(self.typename))

        # doc
        if not self.doc:
            self.doc = "<no document>"
        
        # フラグの整合性をチェックする
        if isinstance(describer, ClassDescriber):
            if self.flags & TYPE_TYPETRAIT_DESCRIBER:
                if describer.klass is self.value_type:
                    raise BadTypeDeclaration("trait実装が明示的に指定されましたが、型が値型と同じです")
            
            # TYPE_XXX_DESCRIBERフラグを推定する
            if self.flags & (TYPE_TYPETRAIT_DESCRIBER|TYPE_VALUETYPE_DESCRIBER) == 0:
                if describer.klass is not self.value_type: 
                    # 別の値型が定義されているならTYPETRAIT
                    self.flags |= TYPE_TYPETRAIT_DESCRIBER
                else: 
                    # describerを値型とする
                    self.flags |= TYPE_VALUETYPE_DESCRIBER
                    self.value_type = describer.klass
            
            # 値型をtypemodule.getで識別子として使用可能にする
            setattr(describer.klass, "Type_typename", self.get_conversion()) 

        # ロード完了
        self.flags |= TYPE_LOADED

        return self
    
    def mixin_load(self, describer):
        # mixinクラスにIDを発行する
        self._mixin.append(describer)
        index = len(self._mixin)-1

        # メソッド属性を列挙する
        if isinstance(describer, dict):
            self.load_methods_from_dict(describer, mixinkey=index)
        else:
            self.load_methods_from_describer(describer, mixinkey=index)
        
            # 追加の記述メソッドを呼び出す
            describer.do_describe_object(self) # type: ignore
        
    def load_methods_from_describer(self, describer, mixinkey=None):
        # クラス属性による記述
        for attrname, attr in describer.enum_attributes():
            method, aliasnames = make_method_prototype(attr, attrname, mixinkey)
            if method is None:
                continue

            self.add_method(method)
            for aliasname in aliasnames:
                self.add_member_alias(aliasname, method.name)
        
        for meth in meta_method_prototypes:
            name = meth.get_action_target()
            attr = describer.get_attribute(name)
            if attr is None:
                continue
            
            decl = parse_doc_declaration(attr, ("meta",))
            if decl is None:
                continue
    
            meth = meth.new(decl)
            self._metamethods[name] = meth
        
    def load_methods_from_dict(self, describer, mixinkey=None):
        # 辞書オブジェクトによる記述
        for key, value in describer.items():
            if key == "Typename":
                self.typename = value
            elif key == "Doc" or key == "Document":
                self.doc = value
            elif key == "ValueType":
                self.value_type = value
            elif key == "Methods":
                for mdict in value:
                    mth = make_method_from_dict(mdict)
                    self.add_method(mth)
            else:
                raise BadTypeDeclaration("定義の辞書の中に無効なメンバがあります: {}".format(key))


class TypeDefinition():
    """
    クラス文字列から型をロードする
    """
    def __init__(self, 
        describer: Union[str, ClassDescriber] = None, 
        typename: str = None, 
        value_type = None, 
        doc = "", 
        scope = None, 
        bits = 0
    ):
        self.value_type = value_type # Noneの可能性がある

        if describer is None:
            # 型名のみが指定されているなら、クラス実装もそこにあるとみなす
            if isinstance(value_type, str):
                describer = value_type
            elif value_type is not None:
                describer = ClassDescriber(value_type)
            else:
                raise ValueError("value_typeかdescriberを、クラスまたは文字列で与えてください")

        if not isinstance(describer, (str, ClassDescriber)):
            raise TypeError("describer type must be 'str' or 'core.importer.ClassDescriber'")
        if isinstance(describer, str):
            describer = ClassDescriber(attribute_loader(describer))
        self.describer = describer

        self.typename = typename
        if typename and not isinstance(typename, str):
            raise ValueError("型名を文字列で指定してください")     
        
        self.doc = doc
        if self.doc:
            self.doc = self.doc.strip()
        self.scope = scope
        self.bits = bits
        self._decl = None
        self._t = None
        self.mixin_target = None
    
    def get_scoped_typename(self):
        if self.scope:
            return self.typename + SIGIL_SCOPE_RESOLUTION + self.scope
        else:
            return self.typename
    
    def get_describer_qualname(self):
        return self.describer.get_qualname()

    def is_loaded(self):
        return self._t is not None

    def get_value_type(self):
        if isinstance(self.value_type, str):
            loader = attribute_loader(self.value_type)
            return loader()
        else:
            return self.value_type

    def get_describer(self):
        return self.describer

    def is_scope(self, scope):
        return self.scope == scope
    
    def is_same_value_type(self, vt):
        # TypeModule.deduceで使用
        if isinstance(self.value_type, str):
            return self.value_type == full_qualified_name(vt)
        else:
            return self.value_type is vt

    def get_loaded(self):
        return self._t

    def define(self, typemodule):
        """ 実行時に型を読み込み定義する """
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
    
    def mixin(self, typemodule):
        """ 既存の型に定義を追加する """
        target = typemodule.find(self.mixin_target)
        if target is None:
            raise ValueError("Mixin対象の型'{}'がモジュールに見つかりません".format(self.mixin_target))

        describer = self.get_describer()
        target.mixin_load(describer)
    
    def is_mixin_type(self):
        return self.mixin_target is not None

    def load_declaration_docstring(self, doc=None):
        """
        先頭の宣言のみを読み込み、型名を決める
        """
        if doc is None:
            doc = self.get_describer().get_docstring()
            if doc is None:
                return False
        
        decl = parse_doc_declaration(doc, ("type",))
        if decl is None:
            return False
        
        if decl.name:
            self.typename = decl.name
            
        # Mixin宣言はあらかじめ読み込む
        if "mixin" in decl.props:
            self.bits | TYPE_MIXIN
            parser = decl.create_parser(("MixinType",))
            mixin = parser.get_value("MixinType")
            if mixin is None:
                raise ValueError("mixin対象をMixinTypeで指定してください")
            self.mixin_target = mixin

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

        sections = decl.create_parser(("ValueType", "MemberAlias"))

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
    def get(self, typecode: Any, *, scope=None) -> Optional[TypeProxy]:
        if isinstance(typecode, TypeProxy):
            return typecode

        if self._typelib is None:
            raise ValueError("No type library set up")
        
        t = None
        if isinstance(typecode, str):
            typename = normalize_typename(typecode)
            t = self.find(typename, scope=scope)
        elif isinstance(typecode, Type):
            t = typecode
        elif hasattr(typecode, "Type_typename"):
            tn = typecode.Type_typename
            if SIGIL_SCOPE_RESOLUTION in tn:
                thisscope, _, typename = tn.rpartition(SIGIL_SCOPE_RESOLUTION)
            else:
                thisscope = None
                typename = tn
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
    def deduce(self, value_type) -> Optional[TypeProxy]:
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

        for ts in self._typelib.values(): # 型を比較する
            for t in ts:
                if t.is_same_value_type(value_type):
                    try:
                        return self._load_type(t)
                    except:
                        continue # モジュールの読み込みエラーが起きても続行
        
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
        elif isinstance(describer, ClassDescriber) or isinstance(describer, type):
            if not isinstance(describer, ClassDescriber):
                describer = ClassDescriber(describer)
            t = Type(describer)
            if typename is None and describer.get_classname() is not None:
                typename = normalize_typename(describer.get_classname())
        else:
            raise TypeError("TypeModule.defineは'{}'による型定義に対応していません：".format(type(describer).__name__))
        
        if isinstance(t, Type):
            t.describe(typename=typename, value_type=value_type, doc=doc, scope=scope, bits=bits)
            t.load()
        
        if isinstance(t, TypeDefinition) and t.is_mixin_type():
            # Mixin型は直ちにロードが行われる
            t.mixin(self)
        
        elif not delayedload:
            # 型をデータベースに登録
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
        
        def register(self, typename):
            if not is_valid_typename(typename):
                raise BadTypename(typename)
            def _define(doc, *, describer=None, value_type=None, scope=None, bits=0):
                d = TypeDefinition(describer, typename, value_type, doc, scope, bits)
                self._parent.define(d)
            return _define
        
        def __getattr__(self, typename):
            return self.register(typename)
        
        def __getitem__(self, typename):
            return self.register(typename)
        
    # 遅延登録
    def definitions(self):
        return self.DefinitionSyntax(self)

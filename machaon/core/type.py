from collections import defaultdict

from typing import Any, Sequence, Union, Callable, ItemsView, Optional, Generator, DefaultDict
from typing import List, Dict, Tuple

from machaon.core.symbol import (
    BadTypename, normalize_typename, BadMethodName, PythonBuiltinTypenames, 
    full_qualified_name, is_valid_typename, summary_escape, normalize_method_name,
    SIGIL_SCOPE_RESOLUTION
)
from machaon.core.typedecl import (
    TypeProxy, TypeInstance, TypeDecl,
    METHODS_BOUND_TYPE_TRAIT_INSTANCE,
    METHODS_BOUND_TYPE_INSTANCE
)
from machaon.core.method import (
    BadMethodDeclaration, UnloadedMethod, MethodLoadError, BadMetaMethod, 
    make_method_from_dict, make_method_prototype, meta_method_prototypes, 
    Method, MetaMethod, MethodParameter,
    parse_type_declaration, parse_result_line, parse_parameter_line, 
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

TYPE_NONETYPE               = 0x0001
TYPE_OBJCOLTYPE             = 0x0002
TYPE_TYPETYPE               = 0x0004
TYPE_FUNTYPE                = 0x0008

TYPE_TYPETRAIT_DESCRIBER    = 0x0100
TYPE_VALUETYPE_DESCRIBER    = 0x0200
TYPE_USE_INSTANCE_METHOD    = 0x0400
TYPE_LOADED                 = 0x1000
TYPE_DELAY_LOAD_METHODS     = 0x2000
TYPE_MIXIN                  = 0x10000
TYPE_SUBTYPE                = 0x20000

SUBTYPE_BASE_ANY = 23

#
#
#
class Type(TypeProxy):
    def __init__(self, describer=None, name=None, value_type=None, scope=None, params=None, *, doc="", bits=0):
        self.typename: str = normalize_typename(name) if name else None
        self.doc: str = doc
        self.flags = bits
        self.value_type: Callable = value_type
        self.scope: Optional[str] = scope
        self._methods: Dict[str, Method] = {}
        self._methodalias: Dict[str, List[TypeMemberAlias]] = defaultdict(list)
        self._describer = describer
        self._metamethods: Dict[str, MetaMethod] = {}
        self._params: List[MethodParameter] = params or []
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
            return describer.get_full_qualname()

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
        t._metamethods = self._metamethods.copy()
        t._describer = self._describer
        t._params = self._params.copy()
        t._mixin = self._mixin.copy()
        return t
    
    #
    #
    #
    def get_typedef(self):
        return self
    
    def check_type_instance(self, type):
        return self is type

    def check_value_type(self, valtype):
        return issubclass(valtype, self.value_type)

    def instantiate(self, *args):
        # 型変換は行われない
        return TypeInstance(self, ctorargs=args)

    def get_type_params(self):
        return self._params
    
    #
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
    def get_method(self, name) -> Optional[Method]:
        """ エイリアスは参照せず、ロードされていなければエラー """
        meth = self._methods.get(name, None)
        if meth and not meth.is_loaded():
            raise UnloadedMethod()
        return meth

    def _resolve_method(self, name):
        """ メソッドを検索する """
        name = normalize_method_name(name)
        meth = self._methods.get(name, None)
        if meth is None:
            name2 = self.get_member_alias(name)
            if name2 is not None:
                meth = self._methods.get(name2)
        return meth
    
    def select_method(self, name) -> Optional[Method]:
        """ エイリアスも参照して探し、ロードされていなければロードする """
        meth = self._resolve_method(name)
        if meth:
            try:
                meth.load(self)
            except Exception as e:
                raise MethodLoadError(e, meth.name).with_traceback(e.__traceback__)
        return meth

    def is_selectable_method(self, name) -> bool:
        """ エイリアスも参照して探し、存在すればTrue """
        meth = self._resolve_method(name)
        return meth is not None
    
    def enum_methods(self):
        """ すべてのメソッドをロードしつつ列挙する
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
    def constructor(self, context, value, typeinst=None):
        """ 
        コンストラクタ。
        実装メソッド:
            constructor
        """
        fns = self.resolve_meta_method("constructor", context, value, typeinst)
        if fns is None:
            # 定義が無い場合、単純に生成する
            return self.value_type(value)
        
        return self.invoke_meta_method(*fns)
    
    def stringify_value(self, value, typeinst=None) -> str:
        """ 
        値を文字列に変換する。
        実装メソッド:
            stringify
        """
        fns = self.resolve_meta_method("stringify", None, value, typeinst)
        if fns is None:
            # デフォルト動作
            return str(value)
        
        return self.invoke_meta_method(*fns)

    def summarize_value(self, value, typeinst=None):
        """ 
        値を短い文字列に変換する。
        実装メソッド:
            summarize
        """
        fns = self.resolve_meta_method("summarize", None, value, typeinst)
        if fns is None:
            s = self.stringify_value(value)
            if not isinstance(s, str):
                s = repr(s) # オブジェクトに想定されない値が入っている
            s = summary_escape(s)
            if len(s) > 50:
                return s[0:30] + "..." + s[-20:]
            else:
                return s
        return self.invoke_meta_method(*fns)

    def pprint_value(self, app, value, typeinst=None):
        """ 
        値を画面に表示する。
        実装メソッド:
            pprint
        """
        fns = self.resolve_meta_method("pprint", None, value, typeinst, app)
        if fns is None:
            s = self.stringify_value(value)
            app.post("message", s)
            return
        self.invoke_meta_method(*fns)

    def reflux_value(self, value:Any, typeinst=None):
        """
        コンストラクタを呼び出せる別の型の値に変換する。
        実装メソッド:
            reflux
        """
        fns = self.resolve_meta_method("reflux", None, value, typeinst)
        if fns is None:
            return self.stringify_value(value, typeinst) # 文字に変換する
        return self.invoke_meta_method(*fns)

    def resolve_meta_method(self, name, context, value, typeinst, *moreargs):
        """ メソッドと引数の並びを解決する """
        fn = self._metamethods.get(name)
        if fn is None:
            return None
        args = fn.prepare_invoke_args(context, self._params, value, typeinst, *moreargs)
        return (fn, *args)

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
            raise BadMetaMethod(e, self, method) from e

    #
    # 型定義構文用のメソッド
    #
    def describe(self, 
        describer = None,
        typename = None,
        value_type = None, 
        scope = None, 
        doc = None, 
        bits = 0
    ):
        if describer is not None:
            self._describer = describer
        if typename is not None:
            self.typename = typename
        if value_type is not None:
            self.value_type = value_type
        if scope is not None:
            self.scope = scope
        if doc is not None:
            self.doc = doc
        if bits:
            self.flags |= bits
        return self

    def load(self, *, loadbits = 0):
        """
        メソッド定義をロードする
        """
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
        if self.value_type is None:
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
        bits = 0,
        # 直接設定可能
        mixinto = None,
        subtypeof = None,
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
        self.params = [] # 型パラメータ
        self.memberaliases = [] 
        self._t = None

        self._sub_target = None # Mixin, Subtypeのターゲット
        if mixinto is not None:
            self.bits |= TYPE_MIXIN
            self._sub_target = mixinto
        if subtypeof is not None:
            self.bits |= TYPE_SUBTYPE
            self._sub_target = subtypeof
    
    def get_scoped_typename(self):
        if self.scope:
            return self.typename + SIGIL_SCOPE_RESOLUTION + self.scope
        else:
            return self.typename
    
    def is_loaded(self):
        return self._t is not None

    def _resolve_value_type(self):
        if self.value_type is None:
            self.value_type = self.describer.klass
        elif isinstance(self.value_type, str):
            loader = attribute_loader(self.value_type)
            self.value_type = loader()
        elif not isinstance(self.value_type, type):
            raise ValueError("Cannot resolve value_type")

    def get_value_type(self):
        self._resolve_value_type()
        return self.value_type

    def get_describer(self):
        return self.describer

    def get_describer_qualname(self):
        return self.describer.get_full_qualname()

    def is_same_value_type(self, vt):
        # TypeModule.deduceで使用 - ロードせずに名前で一致を判定する
        if self.value_type is None:
            return self.describer.get_full_qualname() == full_qualified_name(vt)
        elif isinstance(self.value_type, str):
            return self.value_type == full_qualified_name(vt)
        else:
            return self.value_type is vt

    def is_scope(self, scope):
        return self.scope == scope
    
    def get_loaded(self):
        return self._t

    def proto_define(self, typemodule):
        """ 型を登録する時点での処理 
        Returns:
            Str: 登録名. Noneなら登録しない
        """
        if self.bits & TYPE_MIXIN:
            # Mixin型は直ちにロードを行う（この時点で対象型がロード済みの必要あり）
            target = typemodule.find(self._sub_target)
            if target is None:
                raise ValueError("Mixin対象の型'{}'がモジュールに見つかりません".format(self._sub_target))
            target.mixin_load(self.get_describer())
            return None # 登録しない

        # 以下、型名が必要
        if self.typename is None:
            if self.describer.get_classname() is not None:
                # クラス名から補完する
                name = self.describer.get_classname()
                if not name[0].isupper():
                    name = name[0].upper() + name[1:]
                self.typename = normalize_typename(name)
            else:
                raise ValueError("TypeDefinition typename is not defined")
        
        if self.bits & TYPE_SUBTYPE:
            # Subtype型を登録する（この時点で対象型はロードされていなくてもよい）
            self.bits |= TYPE_TYPETRAIT_DESCRIBER
            self.value_type = _SubtypeTrait # 代入しておかないと補完されてエラーになる
            base = self._sub_target
            return (base, self.typename)

        # 型名を登録する
        return self.typename

    def load_type(self) -> Type:
        """ 実行時に型を読み込み定義する """
        if self._t is not None:
            return self._t
        
        self._resolve_value_type()

        self._t = Type(
            self.describer, 
            name=self.typename,
            value_type=self.value_type,
            scope=self.scope, 
            params=self.params,
            doc=self.doc,
            bits=self.bits
        )
        try:
            self._t.load()
        except Exception as e:
            raise BadTypeDeclaration(self.typename) from e

        for name, row in self.memberaliases:
            self._t.add_member_alias(name, row)
        
        return self._t
    
    def load_docstring(self, doc=None):
        """
        型定義の解析
        """
        """ @type trait use-instance-method subtype mixin [name aliases...]
        detailed description...
        .......................

        ValueType:
            <Typename>
        Params:
            name(typeconversion): description...
        MemberAlias:
            long: (mode ftype modtime size name)
            short: (ftype name)
            link: path
        MixinType:
            <Typename> (mixin target type)
        BaseType:
            <Typename> (subtype base type)
        """
        if doc is None:
            doc = self.get_describer().get_docstring()
            if doc is None:
                return False
        
        decl = parse_doc_declaration(doc, ("type",))
        if decl is None:
            return False
            
        # 定義部をパースする
        sections = decl.create_parser(("ValueType", "Params", "MemberAlias", "BaseType", "MixinType"))
        
        # Mixin宣言はあらかじめ読み込む
        if "mixin" in decl.props:
            self.bits |= TYPE_MIXIN
            mixin = sections.get_value("MixinType")
            if mixin is None:
                raise ValueError("mixin対象を'MixinType'で指定してください")
            self._sub_target = mixin.rstrip(":") # コロンがついていてもよしとする
            return True

        # Subtype宣言も
        elif "subtype" in decl.props:
            self.bits |= TYPE_SUBTYPE
            base = sections.get_value("BaseType")
            if base is None:
                raise ValueError("ベースクラスを'BaseType'で指定してください")
            self._sub_target = base.rstrip(":") # コロンがついていてもよしとする

        else:
            if "use-instance-method" in decl.props:
                self.bits |= TYPE_USE_INSTANCE_METHOD
            if "trait" in decl.props:
                self.bits |= TYPE_TYPETRAIT_DESCRIBER

        decltypename = decl.get_first_alias()
        if decltypename:
            self.typename = decltypename
        
        document = ""
        document += sections.get_string("Document")
        if document:
            self.doc = document.strip()

        valtypename = sections.get_value("ValueType")
        if valtypename:
            self.value_type = valtypename.rstrip(":") # コロンがついていてもよしとする
        
        # 型引数
        for line in sections.get_lines("Params"):
            typename, name, doc, flags = parse_parameter_line(line.strip())
            typedecl = parse_type_declaration(typename)
            p = MethodParameter(name, typedecl, doc, flags=flags)
            self.params.append(p)

        aliases = sections.get_lines("MemberAlias")
        for alias in aliases:
            name, _, dest = [x.strip() for x in alias.partition(":")]
            if not name or not dest:
                raise BadTypeDeclaration()

            if dest[0] == "(" and dest[-1] == ")":
                row = dest[1:-1].split()
                self.memberaliases.append((name, row))

        return True

# ダミーの値型に使用
class _SubtypeTrait:
    pass


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
        self._subtype_rels: DefaultDict[str, Dict[str, Type]] = defaultdict(dict)
    
    def _load_type(self, t: Union[Type, TypeDefinition]):
        if isinstance(t, TypeDefinition):
            return t.load_type()
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

    # サブタイプを取得する
    def get_subtype(self, parenttypecode: Any, typename: str):
        t = self.get(parenttypecode)
        if t is None:
            return None
        
        subt = self._find_subtype(t.get_typename(), typename)
        if subt is None:
            if parenttypecode != SUBTYPE_BASE_ANY: # 総称型対象のものを探す
                return self._find_subtype(SUBTYPE_BASE_ANY, typename)
            else:
                return None
        else:
            return subt

    def _find_subtype(self, basekey, typename):
        td = self._subtype_rels[basekey].get(typename)
        if td is not None:
            return self._load_type(td)
        
        # 親モジュールを探索
        for ancmodule in self._ancestors:
            tt = ancmodule._find_subtype(basekey, typename)
            if tt is not None:
                return tt
        
        return None
        
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
        bits = 0
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
            td = TypeDefinition(describer)
            t = Type(describer, name=td.proto_define(self))
        else:
            raise TypeError("TypeModule.defineは'{}'による型定義に対応していません：".format(type(describer).__name__))
        
        if isinstance(t, Type):
            # 定義をロードする
            t.describe(
                typename=typename, value_type=value_type, 
                doc=doc, scope=scope, bits=bits
            ).load()
            key = t.get_typename()
            if key is None:
                raise TypeError("No typename is set: {}".format(describer))
            self._typelib[key].append(t)
        elif isinstance(t, TypeDefinition):
            key = t.proto_define(self)
            if key is not None:
                if isinstance(key, tuple):
                    base = key[0]
                    if base == "Any":
                        base = SUBTYPE_BASE_ANY
                    sub = key[1]
                    self._subtype_rels[base][sub] = t
                else:
                    self._typelib[key].append(t)
        else:
            raise TypeError("Unknown result value of TypeModule.define: {}".format(t))

        return t
    
    #
    def remove_scope(self, scope):
        raise NotImplementedError()

    def load_definition(self, describer, classname=None) -> TypeDefinition:
        if not isinstance(describer, (str, ClassDescriber)):
            describer = ClassDescriber(describer)
        td = TypeDefinition(describer, classname)
        if not td.load_docstring():
            raise TypeError("Fail to load declaration")
        return self.define(td)

    #
    #
    #
    def add_ancestor(self, other): # type: (TypeModule) -> None
        self._ancestors.append(other)
    
    def add_fundamental_types(self):
        from machaon.types.fundamental import fundamental_types
        self.add_ancestor(fundamental_types())

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

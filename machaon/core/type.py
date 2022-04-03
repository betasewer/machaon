from collections import defaultdict

from typing import Any, Sequence, Union, Callable, ItemsView, Optional, Generator, DefaultDict
from typing import List, Dict, Tuple
from machaon.core.object import Object

from machaon.core.symbol import (
    BadTypename, normalize_typename, BadMethodName, PythonBuiltinTypenames, 
    full_qualified_name, is_valid_typename, summary_escape, normalize_method_name,
    SIGIL_SCOPE_RESOLUTION
)
from machaon.core.typedecl import (
    TypeAny, TypeProxy, TypeInstance, TypeDecl,
    METHODS_BOUND_TYPE_TRAIT_INSTANCE,
    METHODS_BOUND_TYPE_INSTANCE
)
from machaon.core.method import (
    METHOD_HAS_RECIEVER_PARAM, PARAMETER_REQUIRED, BadMethodDeclaration, UnloadedMethod, MethodLoadError, BadMetaMethod, 
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

# 型定義モジュールのエラー 
class TypeModuleError(Exception):
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

SUBTYPE_BASE_ANY = 1

#
#
#
class Type(TypeProxy):
    def __init__(self, describer=None, name=None, value_type=None, params=None, *, doc="", scope=None, bits=0):
        self.typename: str = normalize_typename(name) if name else None
        self.doc: str = doc
        self.flags = bits
        self.value_type: Callable = value_type
        self.scope: Optional[TypeModule] = scope
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
    
    def get_scoped_typename(self):
        return get_scoped_typename(self.typename, self.scope.scopename if self.scope else None)

    def get_conversion(self):
        if self.scope and self.scope.scopename:
            return self.get_scoped_typename()
        else:
            return self.get_typename()

        
    def get_value_type(self):
        return self.value_type
    
    def get_value_type_qualname(self):
        return full_qualified_name(self.value_type)
    
    def get_describer(self, mixin=None):
        if mixin is not None:
            return self._mixin[mixin]
        else:
            return self._describer
    
    def get_describer_qualname(self, mixin=None):
        describer = self.get_describer(mixin)
        if isinstance(describer, dict):
            return None
        else:
            return describer.get_full_qualname()

    def get_document(self):
        return self.doc

    #
    def is_loaded(self):
        return self.flags & TYPE_LOADED > 0
    
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

    def instantiate(self, context, args):
        """ 型引数を型変換し、束縛したインスタンスを生成する """
        return TypeDecl().instance_type(self, context, args)

    #
    #
    #
    def get_typedef(self):
        return self
    
    def check_type_instance(self, type):
        return self is type

    def check_value_type(self, valtype):
        return issubclass(valtype, self.value_type)

    def get_constructor_param(self):
        meta = self.get_meta_method("constructor")
        return meta.get_param()

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
    def get_meta_method(self, name):
        """ メタメソッドの定義を取得する """
        fn = self._metamethods.get(name)
        if fn is None:
            fn = meta_method_prototypes[name]
        return fn

    def resolve_meta_method(self, name, context, value, typeargs, *moreargs):
        """ メソッドと引数の並びを解決する """
        fn = self.get_meta_method(name)
        args = fn.prepare_invoke_args(context, self._params, value, typeargs or [], *moreargs)
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
        fn = self.delegate_method(method.get_action_target())
        if fn is None:
            fn = getattr(self, "default_"+method.get_action_target())
        else:
            # メタメソッドの指定によって引数を調整する
            if method.is_type_bound():
                args = (self, *args)
            else:
                bt = self.get_methods_bound_type()
                if bt == METHODS_BOUND_TYPE_TRAIT_INSTANCE:
                    args = (self, *args)

        try:
            return fn(*args, **kwargs)
        except Exception as e:
            raise BadMetaMethod(e, self, method) from e

    def constructor(self, context, value, args=None):
        """ 
        コンストラクタ。
        実装メソッド:
            constructor
        """
        fns = self.resolve_meta_method("constructor", context, value, args)
        return self.invoke_meta_method(*fns)

    def stringify_value(self, value, args=None) -> str:
        """ 
        値を文字列に変換する。
        実装メソッド:
            stringify
        """
        fns = self.resolve_meta_method("stringify", None, value, args)
        s = self.invoke_meta_method(*fns)
        if not isinstance(s, str):
            raise TypeError("stringifyの返り値が文字列ではありません:{}".format(s))
        return s

    def summarize_value(self, value, args=None):
        """ 
        値を短い文字列に変換する。
        実装メソッド:
            summarize
        """
        fns = self.resolve_meta_method("summarize", None, value, args)
        s = self.invoke_meta_method(*fns)
        if not isinstance(s, str):
            raise TypeError("summarizeの返り値が文字列ではありません:{}".format(s))
        return s

    def pprint_value(self, app, value, args=None):
        """ 
        値を画面に表示する。
        実装メソッド:
            pprint
        """
        fns = self.resolve_meta_method("pprint", None, value, args, app)
        try:
            self.invoke_meta_method(*fns)
        except Exception as e:
            app.post("error", "オブジェクトの表示中にエラーが発生:")
            app.post("message", e)

    def reflux_value(self, value, args=None):
        """
        コンストラクタを呼び出せる別の型の値に変換する。
        実装メソッド:
            reflux
        """
        fns = self.resolve_meta_method("reflux", None, value, args)
        return self.invoke_meta_method(*fns)

    # デフォルト定義
    def default_constructor(self, value, *args):
        """ 定義が無い場合、単純に生成する """
        return self.value_type(value, *args)
    
    def default_stringify(self, value, *_args):
        """ 定義が無い場合、単純に文字にする """
        return str(value)
    
    def default_summarize(self, value, *args):
        """ stringifyに流し、縮める """
        s = self.stringify_value(value, args)
        s = summary_escape(s)
        if len(s) > 100:
            return s[0:50] + "..." + s[-47:]
        else:
            return s
    
    def default_pprint(self, app, value, *args):
        """ stringifyに流す """
        s = self.stringify_value(value, args)
        app.post("message", s)

    def default_reflux(self, value, *args):
        """ stringifyに流す """
        return self.stringify_value(value, args)
    
    #
    # 型定義構文用のメソッド
    #
    def describe(self, 
        describer = None,
        typename = None,
        value_type = None, 
        doc = None, 
        bits = 0
    ):
        if describer is not None:
            self._describer = describer
        if typename is not None:
            self.typename = typename
        if value_type is not None:
            self.value_type = value_type
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
            else:
                raise BadTypeDeclaration("no value_type is specified")

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

    def mixins(self):
        return self._mixin

    def load_methods_from_describer(self, describer, mixinkey=None):
        # クラス属性による記述
        for attrname, attr in describer.enum_attributes():
            method, aliasnames = make_method_prototype(attr, attrname, mixinkey)
            if method is None:
                continue

            self.add_method(method)
            for aliasname in aliasnames:
                self.add_member_alias(aliasname, method.name)
        
        for meth in meta_method_prototypes.values():
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
        self.bits = bits
        self.params = [] # 型パラメータ
        self.memberaliases = [] 
        self.scope = None

        self._t = None

        self._sub_target = None # Mixin, Subtypeのターゲット
        if mixinto is not None:
            self.bits |= TYPE_MIXIN
            self._sub_target = mixinto
        if subtypeof is not None:
            self.bits |= TYPE_SUBTYPE
            self._sub_target = subtypeof
        
        self._mixins = [] # Mixinされるクラス
    
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

    def get_value_type_qualname(self):
        if self.value_type is None:
            return self.describer.get_full_qualname()
        elif isinstance(self.value_type, str):
            return self.value_type
        else:
            raise ValueError("Cannot resolve value_type qualname")

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

    def get_loaded(self):
        return self._t

    def is_subtype(self):
        return self.bits & TYPE_SUBTYPE > 0

    def is_mixin(self):
        return self.bits & TYPE_MIXIN > 0

    def get_sub_target(self):
        return self._sub_target

    def proto_define(self, typemodule):
        """ 型を登録する時点での処理 
        Returns:
            Str: 登録名. Noneなら登録しない
        """
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
            self.value_type = _SubtypeBaseValueType # 代入しておかないと補完されてエラーになる

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
            params=self.params,
            doc=self.doc,
            scope=self.scope,
            bits=self.bits
        )
        try:
            self._t.load()
        except Exception as e:
            raise BadTypeDeclaration(self.typename) from e

        for name, row in self.memberaliases:
            self._t.add_member_alias(name, row)

        for mx in self._mixins:
            self._t.mixin_load(mx)

        return self._t

    def mixin_load(self, describer):
        if self._t is not None:
            self._t.mixin_load(describer)
        else:
            self._mixins.append(describer)
    
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

            # 全てオプショナル引数にする
            flags &= ~PARAMETER_REQUIRED 
            if typename == "Type":
                default = TypeAny() # 型引数のデフォルトはAny
            else:
                default = None

            p = MethodParameter(name, typedecl, doc, default, flags)
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
class _SubtypeBaseValueType:
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
CORE_SCOPE = ""
TYPECODE_TYPENAME = 1
TYPECODE_VALUETYPE = 2

#
# 型取得インターフェース
#
class TypeModule():
    def __init__(self):
        self.scopename = None
        self.parent = None
        self._lib_typename: Dict[str, Type] = {}
        self._lib_describer: Dict[str, str] = {}
        self._lib_valuetype: Dict[str, str] = {}
        self._subtype_rels: Dict[str, Dict[str, Type]] = {}
        self._loading_mixins: Dict[str, List[TypeDefinition]] = {}
        #
        self._children: Dict[str, TypeModule] = {} 

    #
    @property
    def root(self):
        if self.parent is None:
            return self
        else:
            return self.parent

    def count(self):
        """ このモジュールにある型定義の数を返す
        Returns:
            Int:
        """
        return len(self._lib_typename)
    
    #
    def _load_type(self, t: Union[Type, TypeDefinition]) -> Type:
        """ 型定義をロードする """
        if isinstance(t, TypeDefinition):
            ti = t.load_type()
        else:
            ti = t
        return ti
    
    def _select(self, value:str, code:int, *, noload=False) -> Optional[Type]:
        """ このライブラリから型定義を取り出す """
        libt = None
        if code == TYPECODE_TYPENAME:
            libt = self._lib_typename.get(value)
        elif code == TYPECODE_VALUETYPE:
            tn = self._lib_valuetype.get(value)
            if tn is not None:
                libt = self._lib_typename[tn]
        if libt is None:
            return None
        if noload:
            return libt
        else:
            return self._load_type(libt)

    def _select_scoped(self, scopename, typename):
        """ スコープから型を検索する """
        scope = self.get_scope(scopename)
        if scope is not None:
            target = scope._select(typename, TYPECODE_TYPENAME, noload=True)
            if target is not None:
                return target
        return None


    #
    # 型を取得する
    #
    def find(self, typename: str, *, code=TYPECODE_TYPENAME, scope=None) -> Optional[Type]:
        """ 定義を探索する 
        Params:
            typename(str): 型名
            code?(int): 検索対象
            scope?(str): スコープ名
        Returns:
            Optional[Type]:
        """
        t = None
        if scope is None:
            # 自分自身を探索する
            t = self._select(typename, code)
            if t is not None:
                return t

            # すべての子モジュールを探索
            for ch in self._children.values():
                t = ch.find(typename, code=code)
                if t is not None:
                    return t
        else:
            # 特定のモジュールを探索
            mod = self.get_scope(scope)
            if mod is None:
                raise TypeModuleError("スコープ'{}'は子モジュールのなかに見つかりません".format(scope))
            return mod._select(typename, code)
    
    def get(self, typecode: Any, *, scope=None) -> Optional[TypeProxy]:
        """ 色々なデータから定義を探索する 
        Params:
            typecode(Any): str=型名 | Type=型定義そのもの | <class>=型の値型
            scope?(str): スコープ名
        Returns:
            Optional[Type]:
        """
        if isinstance(typecode, TypeProxy):
            return typecode

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
        elif isinstance(typecode, type):
            t = self.find(full_qualified_name(t), code=TYPECODE_VALUETYPE, scope=scope)
        else:
            raise TypeError("未対応のtypecodeです: {}".format(typecode))

        if t is None:
            return None

        return t

    def _enum_types(self, lib, geterror):
        for name, t in lib.items():
            if geterror:
                try:
                    yield name, self._load_type(t), None
                except Exception as e:
                    from machaon.types.stacktrace import ErrorObject
                    yield name, None, ErrorObject(e)
            else:
                yield name, self._load_type(t)

    def enum(self, *, geterror=False) -> Generator[Type, None, None]:
        """ すべての型をロードし、取得する
        Params:
            geterror(bool): 発生したエラーを取得する
        """
        yield from self._enum_types(self._lib_typename, geterror)
        
        for chi in self._children.values():
            yield from chi.enum(geterror=geterror)

    def deduce(self, value_type) -> Optional[TypeProxy]:
        """ 値型に適合する型を取得する
        Params:
            value_type(type):
        Returns:
            Optional[TypeProxy]: 
        """
        if not isinstance(value_type, type):
            raise TypeError("value_type must be type instance, not value")

        # ビルトイン型に対応する
        if hasattr(value_type, "__name__"): 
            typename = value_type.__name__
            if typename in PythonBuiltinTypenames.literals: # 基本型
                return self.get(typename.capitalize())
            elif typename in PythonBuiltinTypenames.dictionaries: # 辞書型
                return self.get("ObjectCollection")
            elif typename in PythonBuiltinTypenames.iterables: # イテラブル型
                return self.get("Tuple")
        
        # 値型で検索する
        t = self.find(full_qualified_name(value_type), code=TYPECODE_VALUETYPE)
        if t is not None:
            return t

        # 見つからなかった
        return None

    #
    # サブタイプを取得する
    #
    def _select_subtype(self, basekey, typename):
        """ このモジュールで型名とサブタイプ名の関係を解決する 
        Params:
            basekey(str): 元の型名
            typename(str): サブタイプ名
        Returns:
            Optional[TypeProxy]
        """
        bag = self._subtype_rels.get(basekey)
        if bag is not None:
            td = self._subtype_rels[basekey].get(typename)
            if td is not None:
                return self._load_type(td)
        return None
        
    def find_subtype(self, basekey, typename, scope=None):
        """ findと同様にサブタイプを探索する
        Params:
            basekey(str): 元の型名
            typename(str): サブタイプ名
            scope?(str): スコープ名
        Returns:
            Optional[TypeProxy]
        """
        if scope is None:
            # 自分自身の定義を探索
            t = self._select_subtype(basekey, typename)
            if t is not None:
                return t

            # 子モジュールをすべて探索
            for ch in self._children.values():
                tt = ch.find_subtype(basekey, typename)
                if tt is not None:
                    return tt
        else:
            # 特定のモジュールを探索
            if scope not in self._children:
                raise TypeModuleError("スコープ'{}'は子モジュールのなかに見つかりません".format(scope))
            mod = self._children[scope]
            return mod._select_subtype(basekey, typename)
    
    def get_subtype(self, basetypecode: Any, typename: str, *, scope=None):
        """ サブタイプを探索する
        Params:
            basetypecode(Any): getで使用できるすべての値
            typename(str): サブタイプ名
            scope?(str): スコープ名
        Returns:
            Optional[TypeProxy]
        """
        basetype = self.get(basetypecode, scope=scope)
        if basetype is None:
            return None
        
        subtype = self.find_subtype(basetype.get_typename(), typename, scope=scope)
        if subtype is None:
            # 総称型のものを探す
            if basetypecode == SUBTYPE_BASE_ANY: 
                return None
            subtype = self.find_subtype(SUBTYPE_BASE_ANY, typename, scope=scope)

        return subtype

    def enum_subtypes_of(self, basetypecode, *, scope=None, geterror=False):
        """ ある型のすべてのサブタイプをロードし、取得する
        Params:
            geterror(bool): 発生したエラーを取得する
        Yields:
            Tuple[Str, Str, Type, Error]: scopename, typename, type, error
        """
        basetype = self.get(basetypecode, scope=scope)
        if basetype is None:
            return None
        basekey = basetype.get_typename()

        # 子モジュールを全て探索する
        def _enum(mod):
            types = mod._subtype_rels.get(basekey, {})
            for name, t, err in self._enum_types(types, geterror):
                yield (mod.scopename, "{}:{}".format(basekey,name), t, err)
                
            for ch in mod._children.values():
                yield from _enum(ch)
        
        yield from _enum(self)

    def enum_all_subtypes(self, *, geterror=False):
        """ 全てのサブタイプを取得する。 
        Yields:
            Tuple[Str, Str, Type, Error]: scopename, typename, type, error
        """
        def _enum(mod):
            for base, types in mod._subtype_rels.items():
                for name, t, err in self._enum_types(types, geterror):
                    yield (mod.scopename, "{}:{}".format(base,name), t, err)
                
            for ch in mod._children.values():
                yield from _enum(ch)

        yield from _enum(self)



    #
    # 型を定義する
    #
    def define(self, 
        describer: Any = None,
        *,
        typename = None, 
        value_type = None,
        doc = "",
        bits = 0
    ) -> Type:
        # 登録処理
        t: Any = None # 型オブジェクトのインスタンス
        if describer is None:
            # 実質文字列型
            t = Type({"ValueType":str})
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
            raise TypeModuleError("TypeModule.defineは'{}'による型定義に対応していません：".format(type(describer).__name__))
        
        if isinstance(t, Type):
            # 定義をロードする
            t.describe(
                typename=typename, value_type=value_type, 
                doc=doc, bits=bits
            ).load()
            key = t.get_typename()
            if key is None:
                raise TypeModuleError("No typename is set: {}".format(describer))

            self._add_type(key, t)
        elif isinstance(t, TypeDefinition):
            if t.is_mixin():
                # mixinを登録するか読み込む
                basename, basescope = parse_scoped_typename(t.get_sub_target())
                self._load_mixin(basename, basescope, t, reserve=True)
            else:
                # 定義を型名に紐づけて配置する
                typename = t.proto_define(self)
                if t.is_subtype():
                    basename, basescope = parse_scoped_typename(t.get_sub_target())
                    self._add_subtype(basename, typename, t)
                else:
                    self._add_type(typename, t)
        else:
            raise TypeModuleError("Unknown result value of TypeModule.define: {}".format(t))

        return t

    def _add_type(self, typename, type):
        """ 型をモジュールに追加する """
        describername = type.get_describer_qualname()
        valuetypename = type.get_value_type_qualname()

        # 型名の辞書をチェックする
        if typename in self._lib_typename:
            dest = self._lib_typename[typename]
            if dest.get_describer_qualname() == describername:
                return # 同じものが登録済み
            else:
                o = dest.get_describer_qualname()
                n = describername
                raise TypeModuleError("型'{}'はこのモジュールに既に存在します\n  旧= {}\n  新= {}".format(typename, o, n))
        
        # デスクライバクラスをチェックする
        if describername is not None:
            if describername in self._lib_describer:
                return # 登録済み

        self._lib_typename[typename] = type
        self._lib_describer[describername] = typename

        # 値型は最初に登録されたものを優先する
        if valuetypename not in self._lib_valuetype:
            self._lib_valuetype[valuetypename] = typename

        # スコープモジュールを登録する
        type.scope = self

        # 予約済みのmixinロードを実行する
        self._load_reserved_mixin(typename, self.scopename, type)

        return type

    def _add_subtype(self, basename, typename, t):
        """ サブタイプ定義を追加する """
        if basename == "Any":
            basename = SUBTYPE_BASE_ANY
        base = self._subtype_rels.setdefault(basename, {})
        base[typename] = t
        
    def load_definition(self, describer, classname=None) -> TypeDefinition:
        """ ただちに型定義をロードする """
        if not isinstance(describer, (str, ClassDescriber)):
            describer = ClassDescriber(describer)
        td = TypeDefinition(describer, classname)
        if not td.load_docstring():
            raise TypeModuleError("Fail to load declaration")
        return self.define(td)

    def _load_mixin(self, basename, basescope, t, *, reserve=False):
        """ mixin定義を追加する """
        basescope = basescope or CORE_SCOPE
        target = self._select_scoped(basescope, basename)
        if target is not None:
            # 定義を追加、もしくは追加を予約する
            target.mixin_load(t.get_describer())
            return

        # 型やスコープの定義がまだ無かった
        # トップレベルのモジュールで予約する
        if reserve:
            li = self.root._loading_mixins.setdefault((basename, basescope), [])
            li.append(t)

    def _load_reserved_mixin(self, typename, scopename, target):
        """  """
        mi = self.root._loading_mixins.get((typename, scopename))
        if mi:
            for mt in mi:
                target.mixin_load(mt.get_describer())
            mi.clear()

    def _load_reserved_mixin_all(self):
        """  """
        for (name, scope), mts in self._loading_mixins.items():
            target = self._select_scoped(scope, name)
            if target is None:
                continue
            for mt in mts:
                target.mixin_load(mt.get_describer())
            mts.clear()

    #
    # 子モジュールを操作する
    #
    def get_scope(self, scopename):
        """ 取得する
        Returns:
            TypeModule:
        """
        return self._children.get(scopename)

    def add_scope(self, scopename, other):
        """ 追加する 
        Params:
            scopename(str): 
            other(TypeModule):
        """
        return self.update_scope(scopename, other, addonly=True)
    
    def update_scope(self, scopename, other, *, addonly=False):
        """ 追加する 
        Params:
            scopename(str): 
            other(TypeModule):
        """
        if scopename in self._children:
            if addonly:
                raise TypeModuleError("スコープ'{}'はこのモジュールに既に存在します".format(scopename)) 
            self._children[scopename].update(other)
        else:
            self.set_parent(other, scopename)
            self._children[scopename] = other
        
    def add_fundamentals(self):
        """ 基本型を追加する """
        from machaon.types.fundamental import fundamental_types
        self.add_scope(CORE_SCOPE, fundamental_types())
    
    def add_default_modules(self):
        """ 標準モジュールの型を追加する """
        from machaon.core.symbol import DefaultModuleNames
        from machaon.package.package import create_package
        for module in DefaultModuleNames:
            pkg = create_package("module-{}".format(module), "module:machaon.{}".format(module))
            mod = pkg.load_type_module()
            self.update_scope(CORE_SCOPE, mod)

    def remove_scope(self, scope):
        """ 削除する 
        Params:
            scope(str):
        """
        if scope in self._children:
            del self._children[scope]
        else:
            raise TypeModuleError("スコープ'{}'はこのモジュールに見つかりません".format(scope))

    def set_parent(self, other, scopename):
        """ 親モジュールを設定する """
        other.parent = self
        other.scopename = scopename
        # mixinを引き継ぎ、解決する
        self._loading_mixins.update(other._loading_mixins)
        other._loading_mixins.clear()
        self._load_reserved_mixin_all()

    def update(self, other):
        """ 
        二つのモジュールを一つに結合する。
        新モジュールの値が優先される
        Params:
            other(TypeModule):
        """
        other.scopename = self.scopename
        other.parent = self.parent
        self._lib_typename.update(other._lib_typename)
        self._lib_describer.update(other._lib_describer)
        self._lib_valuetype.update(other._lib_valuetype)
        self._subtype_rels.update(other._subtype_rels)
        self._loading_mixins.update(other._loading_mixins)
        self._children.update(other._children)

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


def parse_scoped_typename(name):
    n, sep, s = name.partition(SIGIL_SCOPE_RESOLUTION)
    if sep:
        return n, s
    else:
        return name, None

def get_scoped_typename(name, scope=None):
    if scope is not None:
        return name + SIGIL_SCOPE_RESOLUTION + scope
    else:
        return name
    
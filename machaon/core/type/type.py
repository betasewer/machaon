from collections import defaultdict

from typing import Any, Sequence, Union, Callable, ItemsView, Optional, Generator, DefaultDict, List, Dict, Tuple
from machaon.core.object import Object

from machaon.core.symbol import (
    BadTypename, normalize_typename, BadMethodName, PythonBuiltinTypenames, 
    full_qualified_name, is_valid_typename, summary_escape, normalize_method_name,
    get_scoped_typename
)
from machaon.core.type.basic import (
    TypeProxy, 
    METHODS_BOUND_TYPE_TRAIT_INSTANCE,
    METHODS_BOUND_TYPE_INSTANCE, 
    instantiate_args
)
from machaon.core.type.instance import (
    TypeInstance, UnspecifiedTypeParam,
)
from machaon.core.method import (
    PARAMETER_REQUIRED, BadMethodDeclaration, UnloadedMethod, MethodLoadError, BadMetaMethod, 
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

#
#
#
class Type(TypeProxy):
    def __init__(self, describer=None, name=None, value_type=None, params=None, *, doc="", scope=None, bits=0):
        self.typename: str = normalize_typename(name) if name else None
        self.doc: str = doc
        self.flags = bits
        self.value_type: Callable = value_type
        self.scope = scope # TypeModule
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

    def get_all_describers(self):
        return [self._describer, *self._mixin]

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
        targs = instantiate_args(self, self.instantiate_params(), context, args)
        return TypeInstance(self, targs)

    def instantiate_params(self):
        """ 後ろに続く再束縛引数 """
        return self.get_type_params() # 型引数と同じ

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
    
    def default_pprint(self, value, app, *args):
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

    @classmethod
    def new(cls, describer, classname=None):
        """ クラス定義から即座に型定義を読み込み型インスタンスを作成する """
        if isinstance(describer, tuple):
            from machaon.core.type.extend import SubType
            basetype = cls.new(describer[0])
            subtype = cls.new(describer[1], classname)
            return SubType(basetype, subtype)
        else:    
            from machaon.core.type.typedef import TypeDefinition
            td = TypeDefinition.new(describer, classname)
            td.proto_define()
            return td.load_type()



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
        


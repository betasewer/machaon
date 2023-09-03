from collections import defaultdict

from typing import Any, Sequence, Union, Callable, ItemsView, Optional, Generator, DefaultDict, List, Dict, Tuple

from machaon.core.symbol import (
    BadTypename, normalize_typename, BadMethodName, PythonBuiltinTypenames, normalize_typename,
    full_qualified_name, is_valid_typename, summary_escape, normalize_method_name, QualTypename
)
from machaon.core.importer import attribute_loader
from machaon.core.type.basic import (
    TypeProxy, 
    METHODS_BOUND_TYPE_TRAIT_INSTANCE,
    METHODS_BOUND_TYPE_INSTANCE, 
    BadTypeDeclaration,
    BadMethodDelegation,
    BadMemberDeclaration,
)
from machaon.core.type.describer import (
    TypeDescriber
)
from machaon.core.type.instance import (
    TypeInstance, UnspecifiedTypeParam,
)
from machaon.core.method import (
    PARAMETER_REQUIRED, BadMethodDeclaration, UnloadedMethod, MethodLoadError, BadMetaMethod, 
    meta_method_prototypes, 
    Method, MetaMethod, MethodParameter,
)

TYPE_LOADED                 = 0x0100
TYPE_LOADED_METHODS         = 0x0200
TYPE_TYPETRAIT_DESCRIBER    = 0x1000
TYPE_VALUETYPE_DESCRIBER    = 0x2000
TYPE_USE_INSTANCE_METHOD    = 0x4000
TYPE_DELAY_LOAD_METHODS     = 0x8000

#
#
#
class Type(TypeProxy):
    def __init__(self, describer, name=None, value_type=None, params=None, *, doc="", bits=0):
        if not isinstance(describer, TypeDescriber):
            raise TypeError("'describer' must be an instance of TypeDescriber")
        self.typename: str = normalize_typename(name) if name else None
        self.doc: str = doc
        self.flags = bits
        self.value_type: Callable = value_type
        self._methods: Dict[str, Method] = {}
        self._methodalias: Dict[str, List[TypeMemberAlias]] = defaultdict(list)
        self._metamethods: Dict[str, MetaMethod] = {}
        self._params: List[MethodParameter] = params or []
        self._describers: List[TypeDescriber] = [describer]
    
    def __str__(self):
        return "<Type '{}'>".format(self.typename)
    
    def get_typename(self):
        return self.typename
    
    def get_qual_typename(self):
        return QualTypename(self.typename, self.get_describer_qualname())

    def get_conversion(self):
        return self.get_qual_typename().stringify()
        
    def get_value_type(self):
        return self.value_type
    
    def get_value_type_qualname(self):
        return full_qualified_name(self.value_type)

    def get_describer(self, index=None) -> TypeDescriber:
        return self._describers[index or 0]

    def get_all_describers(self):
        return self._describers

    def get_document(self):
        return self.doc

    #
    def is_loaded(self):
        return self.flags & TYPE_LOADED > 0
    
    def copy(self):
        t = Type()
        t.typename = self.typename
        t.doc = self.doc
        t.flags = self.flags
        t.value_type = self.value_type
        t._methods = self._methods.copy()
        t._methodalias = self._methodalias.copy()
        t._metamethods = self._metamethods.copy()
        t._params = self._params.copy()
        t._describers = self._describers.copy()
        return t

    def instantiate_params(self):
        """ 後ろに続く再束縛引数 """
        return self.get_type_params() # 型引数と同じ

    def instantiate(self, context, args):
        """ 型引数を型変換し、束縛したインスタンスを生成する """
        targs = self.instantiate_args(context, args)
        return TypeInstance(self, targs)

    #
    #
    #
    def get_typedef(self):
        return self
    
    def check_type_instance(self, type):
        return self is type

    def check_value_type(self, valtype):
        return issubclass(valtype, self.value_type)

    # 
    # メソッド呼び出し
    #
    def get_method(self, name) -> Optional[Method]:
        """ エイリアスは参照せず、ロードされていなければエラー """
        if self.flags & TYPE_LOADED_METHODS == 0:
            raise UnloadedMethod()
        meth = self._methods.get(name, None)
        if meth and not meth.is_loaded():
            raise UnloadedMethod()
        return meth

    def resolve_method(self, name):
        """ メソッドを検索する """
        self.load_method_prototypes() # メソッド一覧をロードする
        name = normalize_method_name(name)
        meth = self._methods.get(name, None)
        if meth is None:
            name2 = self.get_member_alias(name)
            if name2 is not None:
                meth = self._methods.get(name2)
        return meth
    
    def select_method(self, name) -> Optional[Method]:
        """ エイリアスも参照して探し、ロードされていなければロードする """
        meth = self.resolve_method(name)
        if meth:
            try:
                meth.load_from_type(self)
            except Exception as e:
                raise MethodLoadError(e, meth.name).with_traceback(e.__traceback__)
        return meth

    def is_selectable_method(self, name) -> bool:
        """ エイリアスも参照して探し、存在すればTrue """
        meth = self.resolve_method(name)
        return meth is not None
    
    def enum_methods(self):
        """ すべてのメソッドをロードしつつ列挙する
        Yields:
            Tuple[List[str], Method|Exception]:
        """
        self.load_method_prototypes()
        for name, meth in self._methods.items():
            try:
                meth.load_from_type(self)
            except Exception as e:
                yield [name], MethodLoadError(e, name)
            else:
                names = self.get_member_identical_names(name)
                yield names, meth
    
    def add_method(self, method, aliasnames=None):
        name = method.name
        if name in self._methods:
            raise BadMethodDeclaration("{}: メソッド名が重複しています".format(name))
        self._methods[name] = method

        if aliasnames is not None: # エイリアスを同時に追加する
            for aliasname in aliasnames:
                self.add_member_alias(aliasname, name)

    @property
    def describer(self):
        return self._describers[0]

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
    # 型引数
    #
    def get_type_params(self):
        return self._params
    
    def add_type_param(self, name, typedecl, doc, flags):
        """ 型引数を追加する """
        # 全てオプショナル引数となる
        flags &= ~PARAMETER_REQUIRED
        # デフォルト値
        if typedecl.typename == "Type":
            default = UnspecifiedTypeParam # 型引数のデフォルト値 = Any
        else:
            default = None # 非型引数はNone
        
        p = MethodParameter(name, typedecl, doc, default, flags)
        self._params.append(p)

    #
    # 特殊メソッド
    #
    def get_meta_method(self, name):
        """ メタメソッドの定義を取得する """
        fn = self._metamethods.get(name)
        if fn is None:
            fn = meta_method_prototypes[name]
        return fn
    
    def add_meta_method(self, method):
        """ メタメソッドの定義を追加する """
        name = method.get_type()
        self._metamethods[name] = method

    def resolve_meta_method(self, name, context, args, typeargs=None, *, nodefault=False):
        """ メソッドと引数の並びを解決する """
        self.load_method_prototypes() # メソッド定義を読み込む
        fn = self.get_meta_method(name)

        if typeargs is None:
            typeargs = self.instantiate_args(context, ()) # デフォルト型引数を生成する
        argpre, argpost = fn.prepare_invoke_args(context, args, typeargs)
        
        action = self.get_describer().get_metamethod_attribute(fn.get_action_target())
        if nodefault and action is None:
            return None
        elif action is None:
            action = getattr(self, "default_"+fn.get_action_target())
        else:
            # メタメソッドの指定によって引数を調整する
            if fn.is_type_bound():
                args = (self, *argpre, *argpost)
            elif self.get_methods_bound_type() == METHODS_BOUND_TYPE_TRAIT_INSTANCE:
                args = (self, *argpre, *argpost)
            else:
                selfval = argpost[0]
                args = (selfval, *argpre, *argpost[1:])
        return (fn, action, *args)

    def invoke_meta_method(self, method, action, *args):
        """ 
        内部実装で使うメソッドを実行する
        Returns:
            Any: 実行したメソッドの返り値
        """
        try:
            return action(*args)
        except Exception as e:
            raise BadMetaMethod(e, self, method) from e

    def constructor(self, context, args, typeargs=None):
        """ 
        コンストラクタ。
        実装メソッド:
            constructor
        """
        fns = self.resolve_meta_method("constructor", context, args, typeargs)
        return self.invoke_meta_method(*fns)

    def stringify_value(self, value, typeargs=None) -> str:
        """ 
        値を文字列に変換する。
        実装メソッド:
            stringify
        """
        fns = self.resolve_meta_method("stringify", None, (value,), typeargs)
        s = self.invoke_meta_method(*fns)
        if not isinstance(s, str):
            raise TypeError("stringifyの返り値が文字列ではありません:{}".format(s))
        return s

    def summarize_value(self, value, typeargs=None):
        """ 
        値を短い文字列に変換する。
        実装メソッド:
            summarize
        """
        fns = self.resolve_meta_method("summarize", None, (value,), typeargs)
        s = self.invoke_meta_method(*fns)
        if not isinstance(s, str):
            raise TypeError("summarizeの返り値が文字列ではありません:{}".format(s))
        return s

    def pprint_value(self, app, value, typeargs=None):
        """ 
        値を画面に表示する。
        実装メソッド:
            pprint
        """
        fns = self.resolve_meta_method("pprint", None, (value,app), typeargs)
        try:
            self.invoke_meta_method(*fns)
        except Exception as e:
            app.post("error", "オブジェクトの表示中にエラーが発生:")
            app.post("message", e)

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

    def get_constructor(self) -> Method:
        """ コンストラクタメソッドを返す """
        self.load_method_prototypes() # メソッド定義を読み込む
        fns = self.get_meta_method("constructor")
        return fns.get_method()

    #
    # 型定義構文用のメソッド
    #
    def load(self, *, 
        typename=None,
        value_type=None,
        doc=None,
        bits=0,
        nodescribe=False,
    ):
        """
        型定義のみをロードする
        """
        if self.is_loaded():
            return

        #　型の情報を定義させる
        if not nodescribe:
            self.describer.describe_type(self)

        # 値を後からセットする
        if typename is not None:
            self.set_typename(typename)
        if value_type is not None:
            self.set_value_type(value_type)
        if doc is not None:
            self.set_document(doc)
        if bits:
            self.flags |= bits

        # 値を補完する
        # value_type
        if self.value_type is None:
            raise BadTypeDeclaration("{}: no value_type is specified".format(self.describer.get_full_qualname()))

        # typename
        if not self.typename:
            raise BadTypeDeclaration("{}: 型名を指定してください".format(self.describer.get_full_qualname()))

        if self.typename[0].islower():
            raise BadTypeDeclaration("{}: 型名は大文字で始めてください".format(self.typename))

        # doc
        if not self.doc:
            self.doc = "<no document>"
        
        # フラグの整合性をチェックする
        descvalue = self.describer.get_value()
        if isinstance(descvalue, type):
            if self.flags & TYPE_TYPETRAIT_DESCRIBER:
                if descvalue is self.value_type:
                    raise BadTypeDeclaration("trait実装が明示的に指定されましたが、型が値型と同じです")
            
            # TYPE_XXX_DESCRIBERフラグを推定する
            if self.flags & (TYPE_TYPETRAIT_DESCRIBER|TYPE_VALUETYPE_DESCRIBER) == 0:
                if descvalue is not self.value_type: 
                    # 別の値型が定義されているならTYPETRAIT
                    self.flags |= TYPE_TYPETRAIT_DESCRIBER
                else: 
                    # describerを値型とする
                    self.flags |= TYPE_VALUETYPE_DESCRIBER
                    self.value_type = descvalue
            
            # 値型をtypemodule.getで識別子として使用可能にする
            setattr(descvalue, "Type_typename", self.get_typename()) 

        # ロード完了
        self.flags |= TYPE_LOADED

        return self
    
    def load_method_prototypes(self):
        """ メソッド定義を読み込む """
        if self.flags & TYPE_LOADED_METHODS > 0:
            return
        self.describer.describe_methods(self, 0)
        self.flags |= TYPE_LOADED_METHODS
    
    def mixin_method_prototypes(self, describer):
        """ ミキシンのメソッド定義を読み込む """
        # mixinクラスにIDを発行する
        self._describers.append(describer)
        index = len(self._describers)-1
        # メソッド属性のみを読み込む
        describer.describe_methods(self, index)

    #
    # load前に値を設定する。describe_typeから呼ばれる
    #
    def set_value_type(self, v):
        if isinstance(v, str):
            v = attribute_loader(v)()
        self.value_type = v

    def set_typename(self, n):
        self.typename = normalize_typename(n)

    def set_document(self, doc):
        self.doc = doc

    def use_instance_method(self):
        self.flags |= TYPE_USE_INSTANCE_METHOD

    def use_typetrait_describer(self):
        self.flags |= TYPE_TYPETRAIT_DESCRIBER

    def delay_load_methods(self):
        self.flags |= TYPE_DELAY_LOAD_METHODS

    @classmethod
    def new(cls, describer, typename=None, **kwargs):
        """ クラス定義から即座に型定義を読み込み型インスタンスを作成する """
        from machaon.core.type.describer import create_type_describer
        desc = create_type_describer(describer)
        t = cls(desc)
        t.load(typename=typename, **kwargs)
        return t

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
        




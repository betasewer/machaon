import os
import re
from inspect import signature

from typing import Any, Sequence, List, Dict, Union, Callable, ItemsView, Optional

from machaon.object.method import Method, method_declaration_chain

# imported from...
# desktop
# object
# formula
# dataset
#

#
class BadTypename(Exception):
    pass
#
class BadMethodName(Exception):
    pass
#
class BadMethodDelegation(Exception):
    pass


#
#
#
class TypeTraits():
    __mark = True
    value_type: Callable = str
    class NONAME:
        pass

    def __init__(self, typename=NONAME, doc="", flags=0, value_type=None):
        self.typename: str = typename
        self.doc: str = doc
        self.flags = flags
        self.value_type = value_type
        self._methods: Dict[str, Method] = {}
        self._methodalias: Dict[str, TypeMethodAlias] = {}
    
    def __str__(self):
        return "<TypeTraits '{}'>".format(self.typename)

    def get_value_type(self):
        if self.value_type is None:
            return str # デフォルトでは文字列型とする
        return self.value_type
    
    def copy(self):
        t = TypeTraits(self.typename, self.doc, self.flags)
        t._methods = self._methods.copy()
        t._methodalias = self._methodalias.copy()
        return t

    #
    #
    #
    def convert_from_string(self, arg: str):
        m = self.get_method_delegation("from_string")
        return m(arg)

    def convert_to_string(self, v: Any):
        m = self.get_method_delegation("to_string")
        return m(v)

    # デフォルトの動作
    def from_string(self, arg: str):
        return self.get_value_type()(arg)

    def to_string(self, v: Any):
        if v is None:
            return ""
        else:
            return str(v)
    
    def make_summary(self, v):
        return self.convert_to_string(v)

    # 
    # メソッド呼び出し
    #
    def get_method(self, name) -> Optional[Method]:
        meth = self._methods.get(name, None)
        return meth

    def enum_methods(self, arity=None):
        for meth in self._methods.values():
            if arity is not None and meth.arity != arity:
                continue
            yield meth
    
    def add_method(self, method):
        name = method.name
        if name in self._methods:
            raise BadMethodName("重複しています")
        self._methods[name] = method
    
    # メソッドの実装を解決する
    def get_method_delegation(self, attrname):
        m = getattr(self, attrname, None)
        if m is None:
            raise BadMethodDelegation(attrname)
        return m

    #
    # メソッド名のエイリアスを取得する
    #
    def get_method_alias(self, name) -> Optional[str]:
        a = self._methodalias.get(name, None)
        if a:
            return a.get_destination()
        return None

    def enum_method_alias(self):
        for meth in self._methodalias.values():
            yield meth
    
    def new_method_alias(self, name, dest):
        self._methodalias[name] = TypeMethodAlias(name, dest)

    #
    # 型定義構文用のメソッド
    #
    def describe(self, 
        typename = "",
        doc = "",
        value_type = None,
    ):
        if typename:
            self.typename = typename
        if doc:
            self.doc = doc
        if value_type:
            self.value_type = value_type
        return self 
    
    # 個別のメンバを表明する
    def __getitem__(self, declaration):
        if not isinstance(declaration, str):
            raise TypeError("declaration")
        
        declaration = declaration.lstrip()
        if declaration.startswith("alias"):
            _head, _, tail = declaration.partition(" ")
            origname = tail.strip()
            def alias_(name):
                self.new_method_alias(origname, name)
                return self
            return alias_
        else:
            return method_declaration_chain(self, declaration)

    # describeの中で使用できる
    def describe_method(self, **kwargs):
        return Method(**kwargs)
    
    def make_described(self, describer):
        if not hasattr(describer, "describe_object"):
            raise ValueError("クラスメソッド 'describe_object' が型定義のために必要です")
        describer.describe_object(self) # type: ignore
        setattr(describer, "type_traits_typename", self.typename) # getで使用可能にする
        return self

#
#
class TypeTraitsDelegation(TypeTraits):
    def __init__(self, klass: Any):
        typename = klass.__name__
        super().__init__(typename, typename)
        self.klass = klass
        self._inst = None
        
    def copy(self):
        t = super().copy()
        t.klass = self.klass
        # _inst は自分で生成させる
        return t
    
    def get_value_type(self):
        if self.value_type is None:
            return self.klass
        return self.value_type
    
    def get_method_delegation(self, attrname):
        fn = getattr(self.klass, attrname, None)
        if fn is None:
            # TypeTraitsクラスのデフォルト定義を用いる
            fn = super().get_method_delegation(attrname)
        return fn

#
# 型取得インターフェース
#
class TypeModule():
    def __init__(self):
        self._typelib: Dict[str, TypeTraits] = {}
        self._ancestors: List[TypeModule] = [] 
    
    #
    def normalize_typename(self, name: str) -> str:
        return name.replace("_","-")
        
    #
    def exists(self, typename: str) -> bool:
        return typename in self._typelib
    
    def find(self, typename: str) -> Optional[TypeTraits]:
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
    def get(self, typecode: Any = None, fallback = False) -> Optional[TypeTraits]:
        if self._typelib is None:
            raise ValueError("No type library set up")
        if typecode is None:
            t = self.find("str")
        elif isinstance(typecode, str):
            typename = self.normalize_typename(typecode)
            t = self.find(typename)
        elif isinstance(typecode, TypeTraits):
            t = typecode
        else:
            if hasattr(typecode, "type_traits_typename"):
                typename = typecode.type_traits_typename
            else:
                typename = self.normalize_typename(typecode.__name__)
            t = self.find(typename)
        
        if t is None and not fallback:
            raise BadTypename(typecode)
        return t

    # objtypes[<typename>] -> TypeTraits
    def __getitem__(self, typecode) -> Optional[TypeTraits]:
        return self.get(typecode)

    # objtypes.<typename> -> TypeTraits
    def __getattr__(self, name) -> Optional[TypeTraits]:
        typename = self.normalize_typename(name)
        return self.get(typename)
    
    #
    # 取得し、無ければ定義する
    #
    def new(self, typecode):
        tt = self.get(typecode, fallback=True)
        if tt is None:
            if hasattr(tt, "describe_object"):
                tt = self.define(tt)
            else:
                # 実質は文字列と同一の新しい型を作成
                if isinstance(tt, str):
                    typename = tt
                else:
                    typename = tt.__name__
                tt = self.define(typename=typename, doc="<Prototype {}>".format(typename))
        return tt

    #
    # 型を定義する
    #
    def define(self, 
        traits: Any = None,
        *,
        typename = None, 
        doc = "",
    ) -> TypeTraits:
        # 登録処理
        t: Any = None # 型オブジェクトのインスタンス
        if traits is None:
            # 一時的な型：振る舞いはすべてデフォルト、値の生成は不可
            t = TypeTraits(typename, doc)
        elif isinstance(traits, TypeTraits):
            # Traitsまたは派生型のインスタンスが渡された
            t = traits.copy()
        elif isinstance(traits, type):
            if hasattr(traits, "_TypeTraits__mark"):
                # Traitsまたは派生型の型が渡された
                t = traits(traits.__name__)
            else:
                # 実装移譲先のクラス型が渡された
                t = TypeTraitsDelegation(traits)
            # describe_object
            t.make_described(traits)
        else:
            raise TypeError("TypeModule.defineの引数型が間違っています：{}".format(type(traits).__init__))

        if typename is not None:
            t.typename = typename

        if t.typename in self._typelib:
            raise ValueError("型'{}'は既に定義されています".format(t.typename))
        self._typelib[t.typename] = t

        return t
    
    # デコレータ用
    def definition(self, traits):
        return self.define(traits=traits)

    #
    #
    #
    def add_ancestor(self, other): # type: (TypeModule) -> None
        self._ancestors.append(other)
    
    def add_fundamental_types(self):
        from machaon.object.fundamental import fundamental_type
        self.add_ancestor(fundamental_type)




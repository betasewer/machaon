import os
import re
from inspect import signature

from typing import Any, Sequence, List, Dict, Union, Callable, ItemsView, Optional

#
#
#
#
#
TYPE_SIMPLEX = 0x01
TYPE_SEQUENCE = 0x04

#
#
#
class TypeTraits():
    __mark = True
    value_type: Callable = str

    def __init__(self, typename, description, flags=TYPE_SIMPLEX):
        self.typename: str = typename
        self.description: str = description
        self.flags = flags
        
    def is_simplex_type(self):
        return (self.flags & TYPE_SIMPLEX) == TYPE_SIMPLEX
    
    def is_sequence_type(self):
        return (self.flags & TYPE_SEQUENCE) == TYPE_SEQUENCE
    
    #
    def get_value_type(self):
        return type(self).value_type
        
    def convert_from_string(self, arg: str):
        return self.get_value_type()(arg)

    def convert_to_string(self, v: Any):
        if v is None:
            return ""
        else:
            return str(v)

    def get_operator(self, name):
        return get_type_operator(self, name)

    def enum_operators(self):
        return enum_type_operators(self)

#
#
#
class TypeTraitsDelegation(TypeTraits):
    class InstantiateError(Exception):
        pass

    def __init__(self, klass, typename, description, flags):
        super().__init__(typename, description, flags)
        self.klass = klass
        self._inst = None
    
    def delegate(self, fnname, *fnargs):
        if self._inst is None:
            try:
                self._inst = self.klass()
            except Exception as e:
                raise TypeTraitsDelegation.InstantiateError(self.typename, e)
        
        fn = getattr(self._inst, fnname, None)
        if fn is None:
            # TypeTraitsクラスのデフォルト定義を用いる
            return getattr(super(), fnname)(*fnargs)
        return fn(*fnargs)
    
    def get_value_type(self):
        return self.klass.value_type
    
    def convert_from_string(self, arg: str):
        return self.delegate("convert_from_string", arg)
    
    def convert_to_string(self, arg: Any):
        return self.delegate("convert_to_string", arg)
    
    def get_operator(self, name):
        return get_type_operator(self.klass, name)

    def enum_operators(self):
        return enum_type_operators(self.klass)

    #def create_prompt(self, arg, spirit):
    #    # クラス：インスタンスを生成してから実行
    #    ins = self.klass(*self.args, **self.kwargs)
    #    ins.prompt(arg, spirit)

#
class BadTypenameError(Exception):
    pass

#
# 名前を登録して型を検索する
#
class TypeLibrary:
    def __init__(self):
        self._types: Dict[str, TypeTraits] = {}
    
    def define(self, typename: str, typeobj) -> TypeTraits:
        if typename in self._types:
            raise ValueError("型'{}'は既に定義されています".format(typename))
        self._types[typename] = typeobj
        return typeobj
    
    def exists(self, typename:str) -> bool:
        return typename in self._types
    
    def get(self, typename: str, fallback=False) -> Optional[TypeTraits]:
        if typename not in self._types:
            if fallback:
                return None
            raise BadTypenameError(typename)
        return self._types[typename]
    
    def types(self) -> ItemsView[str, TypeTraits]:
        return self._types.items()

#
# 型取得インターフェース
#
class TypeModule():
    def __init__(self):
        self._typelib: TypeLibrary = TypeLibrary()
        self._define_flags_typebit = 0
    
    #
    def normalize_typename(self, name: str) -> str:
        return name.replace("_","-")

    #
    # 型を取得する
    #
    def get(self, typecode: Union[None, str, type, TypeTraits] = None, fallback = False) -> Optional[TypeTraits]:
        if self._typelib is None:
            raise ValueError("No type library set up")
        if typecode is None:
            return self._typelib.get("str")
        elif isinstance(typecode, str):
            typename = self.normalize_typename(typecode)
            return self._typelib.get(typename, fallback)
        elif isinstance(typecode, type):
            typename = self.normalize_typename(typecode.__name__)
            return self._typelib.get(typename, fallback)
        elif isinstance(typecode, TypeTraits):
            return typecode
        else:
            raise BadTypenameError("No match type exists with '{}'".format(typecode))
    
    # objtypes[<typename>] -> TypeTraits
    def __getitem__(self, typecode) -> TypeTraits:
        return self.get(typecode)

    # objtypes.<typename> -> TypeTraits
    def __getattr__(self, name) -> TypeTraits:
        typename = self.normalize_typename(name)
        return self._typelib.get(typename)

    #
    # 型を定義する
    #
    def define(self, 
        name = None, 
        description = "",
        flags = 0,
        traits = None,
    ):
        # デコレータになる
        if traits is None:
            def _bound(traits_):
                return self.define(name, description, flags, traits_)
            return _bound

        # フラグ
        flags = self._define_flags_typebit + (flags & 0xFFF0)

        # 登録処理
        t: Any = None # 型オブジェクトのインスタンス
        if isinstance(traits, TypeTraits):
            # Traitsまたは派生型のインスタンスが渡された
            if name is None:
                name = traits.typename
            t = traits
        else:
            if name is None:
                name = traits.__name__
            if hasattr(traits, "_TypeTraits__mark"):
                # Traitsまたは派生型の型が渡された
                t = traits(name, description, flags)
            else:
                # 実装移譲先のクラス型が渡された
                t = TypeTraitsDelegation(traits, name, description, flags)
        
        if self._typelib:
            # 登録
            self._typelib.define(name, t)
        
        self._define_flags_typebit = TYPE_SIMPLEX
        return t

    @property
    def sequence(self):
        self._define_flags_typebit = TYPE_SEQUENCE
        return self
    
    #
    #
    #
    def move(self, other): # type: (TypeModule) -> None
        for name, typetraits in other._typelib.types():
            self._typelib.define(name, typetraits)
        del other


#
# 演算子の列挙
#
def get_type_operator(obj, name):
    return getattr(obj, "operator_{}".format(name), None)

def enum_type_operators(obj):
    for name in dir(obj):
        if name.startswith("operator_"):
            yield name, getattr(obj, name)




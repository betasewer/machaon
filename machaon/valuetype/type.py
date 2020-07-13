import os
import re
from inspect import signature

from typing import Any, Sequence, List, Dict, Union, Callable

#
#
#
#
#
TYPE_SIMPLEX = 0x01
TYPE_COMPLEX = 0x02
TYPE_SEQUENCE = TYPE_COMPLEX | 0x04
TYPE_CONVKLASS = 0x10
TYPE_CONVWITHSPIRIT = 0x20

#
#
#
class type_traits():
    __mark = True
    value_type: Callable = str

    def __init__(self, typename, description, args, kwargs, flags):
        self.typename: str = typename
        self.description: str = description
        self.args = args
        self.kwargs = kwargs
        self.flags = flags
        
    def __call__(self, *args, **kwargs): # type: (*Any, **Any) -> type_traits
        return self.rebind_arguments(args, kwargs)
    
    def is_simplex_type(self):
        return (self.flags & TYPE_SIMPLEX) == TYPE_SIMPLEX
    
    def is_compound_type(self):
        return (self.flags & TYPE_COMPLEX) == TYPE_COMPLEX

    def is_sequence_type(self):
        return (self.flags & TYPE_SEQUENCE) == TYPE_SEQUENCE
    
    def _ctor_args(self, args, kwargs):
        return (self.typename, self.description, args, kwargs, self.flags)
        
    #
    def rebind_arguments(self, args, kwargs):
        return type_traits(*self._ctor_args(args, kwargs))

    def get_value_type(self):
        return type(self).value_type
        
    def convert_from_string(self, arg: str, spirit=None):
        return self.get_value_type()(arg)

    def convert_to_string(self, v: Any, spirit=None):
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
class type_traits_delegation(type_traits):
    class InstantiateError(Exception):
        pass

    def __init__(self, klass, typename, description, args, kwargs, flags):
        super().__init__(typename, description, args, kwargs, flags)
        self.klass = klass
        if getattr(self.klass, "with_spirit", False):
            self.flags += TYPE_CONVWITHSPIRIT
        self._inst = None
    
    def delegate(self, fnname, *fnargs, spirit=None):
        if self._inst is None:
            try:
                self._inst = self.klass(*self.args, **self.kwargs)
            except Exception as e:
                raise type_traits_delegation.InstantiateError(self.typename, e)
        
        fn = getattr(self._inst, fnname, None)
        if fn is None:
            return getattr(super(), fnname)(*fnargs)
        elif spirit and self.flags & TYPE_CONVWITHSPIRIT:
            return fn(*fnargs, spirit)
        else:
            return fn(*fnargs)
    
    def rebind_arguments(self, args, kwargs):
        return type_traits_delegation(self.klass, *self._ctor_args(args, kwargs))
    
    def get_value_type(self):
        return self.klass.value_type
    
    def convert_from_string(self, arg: str, spirit=None):
        return self.delegate("convert_from_string", arg, spirit=spirit)
    
    def convert_to_string(self, arg: Any, spirit=None):
        return self.delegate("convert_to_string", arg, spirit=spirit)
    
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
class type_traits_library:
    def __init__(self):
        self._types: Dict[str, type_traits] = {}
    
    def define(self, typename: str, typeobj) -> type_traits:
        if typename in self._types:
            raise ValueError("型'{}'は既に定義されています".format(typename))
        self._types[typename] = typeobj
        return typeobj
    
    def exists(self, typename:str) -> bool:
        return typename in self._types
    
    def get(self, typename: str) -> type_traits:
        if typename not in self._types:
            raise BadTypenameError(typename)
        return self._types[typename]

#
#
#
class type_definer():
    def __init__(self, typelib=None):
        self._lib = typelib
        self._type = TYPE_SIMPLEX

    def define(self, traits_or_class, typename, description, args, kwargs, flags):
        flags = self._type + (flags & 0xFFF0)

        t: Any = None # 型オブジェクトのインスタンス
        if isinstance(traits_or_class, type_traits):
            if typename is None:
                typename = traits_or_class.typename
            t = traits_or_class
        else:
            if typename is None:
                typename = traits_or_class.__name__
            if hasattr(traits_or_class, "_type_traits__mark"):
                t = traits_or_class(typename, description, args, kwargs, flags)
            else:
                t = type_traits_delegation(traits_or_class, typename, description, args, kwargs, flags)
        
        if self._lib:
            self._lib.define(typename, t)
        
        self._type = TYPE_SIMPLEX
        return t

    def __call__(self,
        name = None, 
        description = "",
        args = (), kwargs = {},
        flags = 0,
        traits = None,
    ):
        if traits is not None:
            return self.define(traits, name, description, args, kwargs, flags)
        else:
            def _deco(target):
                return self.define(target, name, description, args, kwargs, flags)
            return _deco
    
    @property
    def compound(self):
        self._type = TYPE_COMPLEX
        return self

    @property
    def sequence(self):
        self._type = TYPE_SEQUENCE
        return self

#
# 型名から型定義を取得する
#
class type_generator():
    def __init__(self, typelib):
        self._typelib: type_traits_library = typelib

    def __getitem__(self, typecode: Union[None, str, type, type_traits] = None) -> type_traits:
        if typecode is None:
            return self._typelib.get("str")
        elif isinstance(typecode, str):
            return self._typelib.get(typecode)
        elif isinstance(typecode, type):
            if self._typelib.exists(typecode.__name__):
                return self._typelib.get(typecode.__name__)
            else:
                return self._typelib.get("constant")(typecode)
        elif isinstance(typecode, type_traits):
            return typecode
        else:
            raise ValueError("No match type exists with '{}'".format(typecode))

    def __getattr__(self, name) -> type_traits:
        return self[name.replace("_","-")]

#
# 演算子の列挙
#
def get_type_operator(obj, name):
    return getattr(obj, "operator_{}".format(name), None)

def enum_type_operators(obj):
    for name in dir(obj):
        if name.startswith("operator_"):
            yield name, getattr(obj, name)




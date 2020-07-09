import os
import re
from inspect import signature

from typing import Any, Sequence, List, Dict, Union

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

    def __init__(self, typename, description, args, kwargs, flags):
        self.typename: str = typename
        self.description: str = description
        self.args = args
        self.kwargs = kwargs
        self.flags = flags
    
    def is_simplex_type(self):
        return (self.flags & TYPE_SIMPLEX) == TYPE_SIMPLEX
    
    def is_compound_type(self):
        return (self.flags & TYPE_COMPLEX) == TYPE_COMPLEX

    def is_sequence_type(self):
        return (self.flags & TYPE_SEQUENCE) == TYPE_SEQUENCE
    
    def _ctor_args(self, args, kwargs):
        return (self.typename, self.description, args, kwargs, self.flags)
        
    #
    def rebind_args(self, args, kwargs):
        raise NotImplementedError()

    def get_value_type(self):
        raise NotImplementedError()
        
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
        
        fn = getattr(self._inst, fnname)
        if spirit and self.flags & TYPE_CONVWITHSPIRIT:
            return fn(*fnargs, spirit)
        else:
            return fn(*fnargs)
    
    def rebind_args(self, args, kwargs):
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
    
    def define(self, typename: str, traits: Any, description: str, args, kwargs, flags: int) -> type_traits:
        if typename in self._types:
            raise ValueError("型'{}'は既に定義されています".format(typename))
        t: Any = None
        if hasattr(traits, "_type_traits__mark"):
            t = traits(typename, description, args, kwargs, flags)
        else:
            t = type_traits_delegation(traits, typename, description, args, kwargs, flags)
        self._types[typename] = t
        return t
    
    def exists(self, typename:str) -> bool:
        return typename in self._types
    
    def generate(self, typename: str, args, kwargs) -> type_traits:
        if typename not in self._types:
            raise BadTypenameError(typename)
        if args:
            return self._types[typename].rebind_args(args, kwargs)
        else:
            return self._types[typename]

#
#
#
class type_define_decolator():
    def __init__(self, typelib):
        self._lib = typelib
        self._type = TYPE_SIMPLEX

    def define(self, function_or_class, name, description, args, kwargs, flags):
        if name is None:
            name = function_or_class.__name__
        flags = self._type + (flags & 0xFFF0)

        self._lib.define(name, function_or_class, description, args, kwargs, flags)
        
        self._type = TYPE_SIMPLEX
        return function_or_class

    def __call__(self,
        name = None, 
        description = "",
        args = (), kwargs = {},
        flags = 0,
        traits = None,
    ):
        if traits is not None:
            self.define(traits, name, description, args, kwargs, flags)
        else:
            def _deco(target):
                self.define(target, name, description, args, kwargs, flags)
                return target
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
class type_generate():
    def __init__(self, typelib):
        self.typelib: type_traits_library = typelib

    def __call__(self, typecode: Union[None, str, type, type_traits] = None, *args, **kwargs) -> type_traits:
        if typecode is None:
            return self.typelib.generate("str", (), {})
        elif isinstance(typecode, str):
            return self.typelib.generate(typecode, args, kwargs)
        elif isinstance(typecode, type):
            if self.typelib.exists(typecode.__name__):
                return self.typelib.generate(typecode.__name__, args, kwargs)
            else:
                return self.typelib.generate("constant", (typecode,), {})
        elif isinstance(typecode, type_traits):
            return typecode
        else:
            raise ValueError("No match type exists with '{}'".format(typecode))

#
# 演算子の列挙
#
def get_type_operator(obj, name):
    return getattr(obj, "operator_{}".format(name), None)

def enum_type_operators(obj):
    for name in dir(obj):
        if name.startswith("operator_"):
            yield name, getattr(obj, name)




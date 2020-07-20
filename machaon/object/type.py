import os
import re
from inspect import signature

from typing import Any, Sequence, List, Dict, Union, Callable, ItemsView, Optional

#
#
#
#
#

#
#
#
class TypeMember():
    class PRINTER():
        pass
    class UNDEFINED():
        pass

    def __init__(self, name, typecode, help="", method=None):
        self.name = name
        self.typecode = typecode
        self.help = help
        self.method = method or TypeMember.UNDEFINED
    
    def get_name(self):
        return self.name
    
    def get_typecode(self):
        return self.typecode

    def is_printer(self):
        return self.typecode is TypeMember.PRINTER
        
    #
    def get_value(self, obj):
        if self.is_printer():
            return TypeMember.PRINTER
        else:
            return self.method(obj.value)
    
    def get_print(self, obj, spirit):
        if self.is_printer():
            self.method(obj.value, spirit)
        else:
            spirit.message(self.get_value(obj.value))

#
#
#
class TypeOperator:
    class UNDEFINED():
        pass

    def __init__(self, name, typecode, help="", method=None):
        self.name = name
        self.rtypecode = typecode
        self.help = help
        self.method = method or TypeOperator.UNDEFINED
    
    def get_name(self):
        return self.name
    
    def get_result_typecode(self):
        return self.rtypecode

    #
    def operate(self, *objects):
        args = [x.value for x in objects]
        return self.method(*args)

#
#
#
class TypeAlias:
    def __init__(self, name, dest):
        self.name = name
        self.dest = dest
    
    def get_name(self):
        return self.name
    
    def get_destination(self):
        return self.dest

#
class MethodCall():
    def __init__(self, name):
        self.name = name

    def __call__(self, *args):
        if len(args)==0:
            raise ValueError("Not enough argument")
        return getattr(args[0], self.name)(*args[1:])

#
#
#
class TypeTraits():
    __mark = True
    value_type: Callable = str

    def __init__(self, typename, description="", flags=0):
        self.typename: str = typename
        self.description: str = description
        self.flags = flags
        self._members: Dict[str, Any] = {}

    def get_value_type(self):
        return type(self).value_type
        
    def convert_from_string(self, arg: str):
        return self.get_value_type()(arg)

    def convert_to_string(self, v: Any):
        if v is None:
            return ""
        else:
            return str(v)
    
    # 
    #
    #
    def get_element(self, elemprefix, name):
        meth = self._members.get("{}_{}".format(elemprefix, name), None)
        if meth:
            return meth

    def enum_elements(self, elemprefix):
        prefix = elemprefix + "_"
        for name in self._members.keys():
            if name.startswith(prefix):
                yield self._members[name]
                
    def get_member(self, name):
        return self.get_element("member", name)
    
    def enum_members(self, name):
        return self.enum_elements("member")
    
    def new_member(self, names, type=None, help="", method=None):
        top, *aliass = names
        self._members["member_"+top] = TypeMember(top, type, help, method)
        for a in aliass:
            self.new_alias(a, top)
            
    def get_operator(self, name):
        return self.get_element("operator", name)

    def enum_operators(self):
        return self.enum_elements("operator")
        
    def new_operator(self, names, return_type=None, help="", method=None):
        top, *aliass = names
        self._members["operator_"+top] = TypeOperator(top, return_type, help, method)
        for a in aliass:
            self.new_alias(a, top)
        
    def get_alias(self, name):
        return self.get_element("memberalias", name)

    def enum_alias(self):
        return self.enum_elements("memberalias")
    
    def new_alias(self, name, dest):
        self._members["memberalias_"+name] = TypeAlias(name, dest)

    #
    # 型定義構文用のメソッド
    #
    #
    def describe(self, 
        typename,
        description = "",
    ):
        self.typename = typename
        self.description = description
        return self 
    
    def __getitem__(self, declaration):
        if not isinstance(declaration, str):
            raise TypeError("declaration")
        
        head, tail = declaration.split(maxsplit=1)
        if head == "member":
            names = tail.split()
            def member_(**kwargs):
                self.new_member(*names, **kwargs)
                return self
            return member_

        elif head == "alias":
            origname = tail.strip()
            def alias_(*names):
                self.new_alias(origname, names)
                return self
            return alias_

        elif head == "operator":
            names = tail.split()
            def opr_(**kwargs):
                self.new_operator(*names, **kwargs)
                return self
            return opr_

        else:
            raise ValueError("Unknown declaration type '{}'".format(head))
#
#
#
class TypeTraitsDelegation(TypeTraits):
    class InstantiationError(Exception):
        pass

    def __init__(self, klass: Any):
        typename = klass.__name__
        super().__init__(typename, typename)
        self.klass = klass
        self._inst = None
        

        # describe
        if not hasattr(self.klass, "describe_type"):
            raise ValueError("クラスメソッド 'describe_type' が型定義のために必要です")
        
        self.klass.describe_type(self)
    
    def delegate(self, fnname, *fnargs):
        if self._inst is None:
            try:
                self._inst = self.klass()
            except Exception as e:
                raise TypeTraitsDelegation.InstantiationError(self.typename, e)
        
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
    def __getitem__(self, typecode) -> Optional[TypeTraits]:
        return self.get(typecode)

    # objtypes.<typename> -> TypeTraits
    def __getattr__(self, name) -> Optional[TypeTraits]:
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
                t = TypeTraitsDelegation(traits)
        
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




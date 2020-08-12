from typing import Any, Optional, List, Sequence

from machaon.object.type import TypeTraits

# imported from...
# desktop
# 
#
#

#
#
#
class ObjectValue():
    def __init__(self, typecode, value):
        self.typecode = typecode
        self.value = value

#
#
#
class Object():
    def __init__(self, name, type, value): # デフォルトは空文字列
        self.value: Any = value
        self.name: str = name
        self.type: TypeTraits = type
        if not isinstance(self.name, str):
            raise TypeError("'name' must be str")
        if not isinstance(self.type, TypeTraits):
            raise TypeError("'type' must be TypeTraits instance")

    def __repr__(self):
        return "<Object {} '{}' = {}>".format(self.type.typename, self.name, self.value)
    
    def get_typename(self):
        return self.type.typename
    
    # メソッド名を解決する
    """
    def resolve_method(self, method_name):
        return ObjectOperator(method_name, self.type)

    # メソッド名を解決し呼び出す
    def call_method(self, method_name, *args, printer=False) -> ObjectValue:
        method = self.resolve_method(method_name)
        if printer:
            spirit = args[0]
            method(self.value, spirit, *args[1:])
            return ObjectValue(None, None)
        else:
            ret = method(self.value, *args)
            return ObjectValue(type(ret), ret)
    """
    
    #
    def to_string(self) -> str:
        return self.type.convert_to_string(self.value)
    
    def get_summary(self) -> str:
        return self.type.make_summary(self.value)

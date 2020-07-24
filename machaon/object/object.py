from typing import Any, Optional, List, Sequence

from machaon.object.type import TypeTraits

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

    def __repr__(self):
        return "<Object {} '{}' = {}>".format(self.type.typename, self.name, self.value)
    
    # メソッド名を解決する
    def resolve_method(self, method_name, *, printer=False):
        # 型に定義されたメソッド
        typemethod = self.type.get_method(method_name)
        if typemethod:
            if printer:
                return ObjectPrintTypeMethod(typemethod)
            else:
                return ObjectTypeMethod(typemethod)
        
        # 値に定義された標準のメソッド
        instmethod = None
        if typemethod is None:
            instmethod = getattr(self.value, method_name, None)
            if instmethod:
                return ObjectInstanceMethod(instmethod)
        
        return None

    # メソッド名を解決し呼び出す
    def call_method(self, method_name, *args, printer=False) -> ObjectValue:
        method = self.resolve_method(method_name, printer=printer)
        if method:
            return method(self, *args)
        else:
            raise ValueError("メンバ'{}'の定義が見つかりません".format(method_name))
    
    #
    def to_string(self) -> str:
        return self.type.convert_to_string(self.value)

#
# オブジェクトのメンバ関数
#
class ObjectMethod:
    def __call__(self, obj, *args):
        raise NotImplementedError()

    def get_name(self):
        raise NotImplementedError()

class ObjectTypeMethod(ObjectMethod):
    def __init__(self, typemethod):
        self.method = typemethod
    
    def __call__(self, obj, *args):
        ret = self.method.call(obj.type, obj.value, *args)
        return ObjectValue(self.method.get_result_typecode(), ret)
    
    def get_name(self):
        return self.method.get_name()

class ObjectPrintTypeMethod(ObjectTypeMethod):
    def __call__(self, obj, spirit, *args):
        self.method.print(obj.type, spirit, obj.value, *args[1:])
        return None

class ObjectInstanceMethod(ObjectMethod):
    def __init__(self, method):
        self.meth = method
    
    def __call__(self, _obj, *args):
        ret = self.meth(*args)
        return ObjectValue(type(ret), ret)
        
    def get_name(self):
        return "{}.{}".format(self.meth.__module__, self.meth.__name__)

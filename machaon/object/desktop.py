from typing import Dict, Any, Optional, DefaultDict, List
from collections import defaultdict

from machaon.object.object import Object, ObjectValue
from machaon.object.type import TypeModule, TypeTraits

#
#
#
class ObjectDesktop():
    def __init__(self):
        self._objects: Dict[str, Object] = {}
        self._objtypemap: DefaultDict[str, List[str]] = defaultdict(list)
        self._types: TypeModule = TypeModule()
    
    # 対応するオブジェクト型を設定する
    def add_types(self, types: TypeModule):
        self._types.add_ancestor(types)
    
    def add_fundamental_types(self):
        from machaon.object.fundamental import fundamental_type
        self.add_types(fundamental_type)
    
    # 型オブジェクトを得る
    def get_type(self, typecode):
        tt = self._types.get(typecode, fallback=True)
        if tt is None:
            tt = self.new_type(typecode) # 存在しなければ作成する
        return tt
    
    # 新しい型を定義する
    def new_type(self, typetraits): # str | TypeTraitsKlass
        if hasattr(typetraits, "describe_type"):
            tt = self._types.define(typetraits)
        else:
            # 実質は文字列と同一の新しい型を作成
            if isinstance(typetraits, str):
                typename = typetraits
            else:
                typename = typetraits.__name__
            tt = self._types.define(typename=typename, description="<Temporal string type {}>".format(typename))
        return tt

    # オブジェクトを新規生成し、追加
    def new(self, name, typecode, *args, **kwargs):
        # ObjectValueからの生成
        if isinstance(typecode, ObjectValue):
            args = (typecode.value,)
            typecode = typecode.typecode

        # 型を決定する
        tt = self._types.get(typecode, fallback=True)
        if tt is None:
            tt = self.new_type(typecode)
        
        # オブジェクトを構築
        value_type = tt.get_value_type()
        if len(args)==1 and isinstance(args[0], value_type):
            value = args[0]
        else:
            value = value_type(*args, **kwargs)
        return Object(name, tt, value)

    # オブジェクトを追加
    def push(self, obj_or_name, *newargs, **newkwargs) -> Object:
        if len(newargs)>0:
            objname = obj_or_name
            obj = self.new(objname, newargs[0], *newargs[1:], **newkwargs)
        else:
            obj = obj_or_name

        if obj.name in self._objects:
            raise ValueError()
        self._objects[obj.name] = obj
        self._objtypemap[obj.type.typename].append(obj.name)
        return obj

    # 名前で検索する
    def pick(self, name) -> Optional[Object]:
        o = self._objects.get(name, None)
        return o

    # 指定された型のうち、最も新しいオブジェクトを取りだす
    def pick_by_type(self, typename) -> Optional[Object]:
        names = self._objtypemap[typename]
        if names:
            return self._objects[names[-1]]
        return None


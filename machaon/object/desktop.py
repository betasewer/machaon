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
        self._typemap: DefaultDict[str, List[str]] = defaultdict(list)
        self._types: TypeModule = TypeModule()
    
    # 対応するオブジェクト型を設定する
    def add_types(self, types: TypeModule):
        self._types.add_ancestor(types)
    
    # オブジェクトを新規生成し、追加
    def new(self, name, typecode, value=None):
        # ObjectValueからの生成
        if isinstance(typecode, ObjectValue) and value is None:
            value = typecode.value
            typecode = typecode.typecode

        # 型を決定する
        tt = self._types.get(typecode, fallback=True)
        if tt is None:
            # 新しい型なら定義する
            if hasattr(typecode, "describe_type"):
                tt = self._types.define(typecode)
            else:
                if not isinstance(typecode, str):
                    typecode = typecode.__name__
                tt = self._types.define(typename=typecode, description="<Temporal type {}>".format(typecode))
        
        # オブジェクトを構築
        return Object(name, tt, value)

    # オブジェクトを追加
    def push(self, obj_or_name, *newargs) -> Object:
        if len(newargs)>0:
            objname = obj_or_name
            obj = self.new(objname, newargs[0], *newargs[1:])
        else:
            obj = obj_or_name

        if obj.name in self._objects:
            raise ValueError()
        self._objects[obj.name] = obj
        self._typemap[obj.type.typename].append(obj.name)
        return obj

    # 名前で検索する
    def pick(self, name) -> Optional[Object]:
        o = self._objects.get(name, None)
        return o

    # 指定された型のうち、最も新しいオブジェクトを取りだす
    def pick_by_type(self, typename) -> Optional[Object]:
        names = self._typemap[typename]
        if names:
            return self._objects[names[-1]]
        return None


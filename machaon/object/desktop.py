from typing import Dict, Any, Optional, DefaultDict, List
from collections import defaultdict

from machaon.object import types
from machaon.object.type import TypeTraits

#
class Object():
    def __init__(self, name, typecode=None, value=""): # デフォルトは空文字列
        self.value: Any = value
        self.name: str = name
        self.type: TypeTraits = types.get(typecode, fallback=True)
        
        if self.type is None:
            if isinstance(typecode, str):
                self.type = TypeTraits(typecode, "<Temporal type {}>".format(typecode))
            elif isinstance(typecode, type) and hasattr(typecode, "describe_type"):
                t = TypeTraitsBuilder()
                typecode.describe_type(t)
                self.type = t.build()
            else:
                raise ValueError("Invalid Type '{}'".format(type))
        
    def __repr__(self):
        return "<Object {} '{}' = {}>".format(self.type.typename, self.name, self.value)

#
class ObjectDesktop():
    def __init__(self):
        self._objects: Dict[str, Object] = {}
        self._typemap: DefaultDict[str, List[str]] = defaultdict(list)

    # オブジェクトを追加
    def push(self, obj):
        if obj.name in self._objects:
            raise ValueError()
        self._objects[obj.name] = obj
        self._typemap[obj.type.typename].append(obj.name)

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


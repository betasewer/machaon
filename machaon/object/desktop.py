from typing import Dict, Any, Optional, DefaultDict, List, Set
from collections import defaultdict

from machaon.object.object import Object, ObjectValue
from machaon.object.type import TypeModule, TypeTraits

# imported from...
# action
# dataset
# 
#

#
#
#
class ObjectDesktop():
    def __init__(self):
        self._objects: Dict[str, Object] = {}
        self._objtypemap: DefaultDict[str, List[str]] = defaultdict(list)
        self._selection: Set[str] = set()
    
    # 型の一覧を取得
    def get_types(self) -> TypeModule:
        raise NotImplementedError()

    # オブジェクトを新規生成し、追加
    def new(self, name, typecode, *args, **kwargs):
        # ObjectValueからの生成
        if isinstance(typecode, ObjectValue):
            args = (typecode.value,)
            typecode = typecode.typecode

        # 型を決定する
        if isinstance(typecode, TypeTraits):
            tt = typecode
        else:
            tt = self.get_types().new(typecode)
        
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
            raise ValueError("オブジェクト名'{}'は重複しています".format(obj.name))

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
    
    # 列挙する
    def enumerates(self):
        for _, o in sorted(self._objects.items(), key=lambda x:x[0]):
            yield o

    # 選択する
    def select(self, name, select=True):
        if select:
            self._selection.add(name)
        else:
            self._selection.remove(name)

    def is_selected(self, name):
        return name in self._selection
    
    # 新しい空のデスクトップを作る
    def spawn(self):
        # 型のみ引き継ぐ
        desk = ObjectDesktop()
        desk._types = self._types
        return desk

    

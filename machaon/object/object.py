from typing import Any, Optional, List, Sequence, Dict, DefaultDict, Generator
from collections import OrderedDict, defaultdict

from machaon.object.type import TypeTraits

# imported from...
# desktop
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
    def __init__(self, type, value): # デフォルトは空文字列
        self.value: Any = value
        self.type: TypeTraits = type
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

#
#
#
class ObjectCollectionItem:
    def __init__(self, ident, name, obj):
        self.ident: int = ident
        self.name: Optional[str] = name
        self.selected = False
        self.object = obj
        if self.object is None:
            raise ValueError("object must be None")
    
    @property
    def value(self):
        return self.object.value
        
    @property
    def type(self):
        return self.object.type
    
    @property
    def typename(self):
        return self.object.get_typename()

    #
    def select(self, select=True):
        self.selected = select

#
#
#
class ObjectCollection():
    def __init__(self):
        self._items: Dict[int, ObjectCollectionItem] = {}
        self._namemap: DefaultDict[str, List[int]] = defaultdict(list)
        self._typemap: DefaultDict[str, List[int]] = defaultdict(list)
    
    # コンストラクタを実行しつつオブジェクトを新規作成
    def new(self, name: str, type: TypeTraits, *args, **kwargs) -> ObjectCollectionItem:
        if not isinstance(name, str) or not isinstance(type, TypeTraits):
            raise TypeError()
        value_type = type.get_value_type()
        if len(args)==1 and len(kwargs)==0 and isinstance(args[0], value_type):
            value = args[0]
        else:
            value = value_type(*args, **kwargs)
        o = Object(type, value)
        return self.push(name, o)

    # オブジェクトを追加
    def push(self, name: str, obj: Object) -> ObjectCollectionItem:
        if not isinstance(name, str) or not isinstance(obj, Object):
            raise TypeError()
        newident = len(self._items)
        item = ObjectCollectionItem(newident, name, obj)
        self._items[newident] = item
        self._namemap[name].append(newident)
        self._typemap[obj.get_typename()].append(newident)
        return item

    # 名前で検索する
    def pick_by_name(self, name) -> Generator[ObjectCollectionItem, None, None]:
        for ident in self._namemap[name]:
            yield self._items[ident]
    
    def get_by_name(self, name) -> Optional[ObjectCollectionItem]:
        li = list(self.pick_by_name(name))
        return li[-1] if li else None

    # 型名で検索する
    def pick_by_type(self, typename) -> Generator[ObjectCollectionItem, None, None]:
        for ident in self._typemap[typename]:
            yield self._items[ident]
            
    def get_by_type(self, name) -> Optional[ObjectCollectionItem]:
        li = list(self.pick_by_type(name))
        return li[-1] if li else None
    
    # 全てのオブジェクトを取得
    def pick_all(self) -> Generator[ObjectCollectionItem, None, None]:
        for item in self._items.values():
            yield item
    

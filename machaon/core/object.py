from typing import Any, Optional, List, Sequence, Dict, DefaultDict, Generator
from collections import OrderedDict, defaultdict
from copy import copy

from machaon.core.type import Type
from machaon.core.symbol import normalize_typename

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


class EMPTY_OBJECT:
    pass

#
#
#
class Object():
    def __init__(self, type, value=EMPTY_OBJECT):
        self.value: Any = value
        self.type: Type = type
        if not isinstance(self.type, Type):
            raise TypeError("'type' must be Type instance")

    def __repr__(self):
        return "<Object {1} [{0}]>".format(self.type.typename, repr(self.value))
    
    def __str__(self):
        return "{1} [{0}]".format(self.type.typename, self.summary())
    
    def get_typename(self):
        return self.type.typename
    
    def get_value(self):
        if self.is_pretty_view():
            return self.value.object.value
        else:
            return self.value
    
    def copy(self):
        return Object(self.type, copy(self.get_value()))
    
    def to_string(self) -> str:
        return self.type.convert_to_string(self.get_value())

    def summary(self) -> str:
        return self.type.summarize_value(self.get_value())

    def pprint(self, spirit):
        self.type.pprint_value(spirit, self.get_value())
    
    def pretty_view(self):
        return Object(self.type, ObjectPrettyView(self))
    
    def is_pretty_view(self):
        return isinstance(self.value, ObjectPrettyView)
    
    def is_error(self):
        from machaon.process import ProcessError
        return isinstance(self.get_value(), ProcessError)
    
    def is_truth(self):
        return self.get_value() and not self.is_error()

#
class ObjectPrettyView():
    def __init__(self, o):
        self.object = o
    
    def get_object(self):
        return self.object

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
            raise ValueError("object must be not None")
    
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


class ObjectCollection():
    """ @type
    オブジェクトを文字列によるキーで集めた辞書。
    メソッド名がそのままメンバ参照になる。
    """
    def __init__(self):
        self._items: Dict[int, ObjectCollectionItem] = {}
        self._namemap: DefaultDict[str, List[int]] = defaultdict(list)

    # コンストラクタを実行しつつオブジェクトを新規作成
    def new(self, name: str, type: Type, *args, **kwargs) -> ObjectCollectionItem:
        if not isinstance(name, str) or not isinstance(type, Type):
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
        return item

    # 名前で検索する
    def pick(self, name) -> Generator[ObjectCollectionItem, None, None]:
        for ident in self._namemap[name]:
            yield self._items[ident]
    
    def get(self, name) -> Optional[ObjectCollectionItem]:
        li = list(self.pick(name))
        return li[-1] if li else None

    # 全てのオブジェクトを取得
    def pick_all(self) -> Generator[ObjectCollectionItem, None, None]:
        for item in self._items.values():
            yield item
    
    #
    #
    #
    def construct(self, s):
        pass

    def conversion_construct(self, context, value, *_args):
        if isinstance(value, dict):
            col = ObjectCollection()
            for k, v in value.items():
                if not isinstance(v, Object):
                    v = context.new_object(v)
                col.push(k, v)
            return col
        else:
            raise ValueError("'{}'からの型変換は定義されていません".format(type(value).__name__))

    def summarize(self):
        heads = []
        trail = ""
        for name, _ids in self._namemap.items():
            heads.append(name)
            if len(heads) > 4:
                trail = "..."
                break
        return ", ".join(heads) + trail

    def pprint(self, app):
        pass
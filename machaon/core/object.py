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
        self._value: Any = value
        self.type: Type = type
        if not isinstance(self.type, Type):
            raise TypeError("'type' must be Type instance")

    def __repr__(self):
        return "<Object {1} [{0}]>".format(self.type.typename, repr(self._value))
    
    def __str__(self):
        return "{1} [{0}]".format(self.type.typename, self.summary())
    
    @property
    def value(self):
        if self.is_pretty_view():
            return self._value.object._value
        else:
            return self._value
    
    def get_typename(self):
        return self.type.typename
    
    def copy(self):
        return Object(self.type, copy(self.value))
    
    def to_string(self) -> str:
        return self.type.convert_to_string(self.value)

    def summary(self) -> str:
        return self.type.summarize_value(self.value)

    def pprint(self, spirit):
        self.type.pprint_value(spirit, self.value)
    
    def pretty_view(self):
        return Object(self.type, ObjectPrettyView(self))
    
    def is_pretty_view(self):
        return isinstance(self._value, ObjectPrettyView)
    
    def is_error(self):
        from machaon.process import ProcessError
        return isinstance(self.value, ProcessError)
    
    def is_truth(self):
        return self.value and not self.is_error()

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
        if name not in self._namemap:
            return
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
        for name, ids in self._namemap.items():
            if not ids:
                continue
            heads.append(name)
            if len(heads) > 4:
                trail = "..."
                break
        return ", ".join(heads) + trail

    def pprint(self, app):
        if len(self._items) == 0:
            text = "空です" + "\n"
            app.post("message", text)
        else:
            context = app.get_process().get_last_invocation_context() # 実行中のコンテキスト
            rows_ = []
            columns = ["名前", "値", "型"]
            columnwidths = [8, 8, 8]
            for name, ids in self._namemap.items():
                for i in ids:
                    o = self._items[i].object
                    columnwidths[0] = max(columnwidths[0], len(name))
                    sm = o.summary()
                    columnwidths[1] = max(columnwidths[1], len(sm))
                    tn = o.get_typename()
                    columnwidths[2] = max(columnwidths[2], len(tn))
                    rows_.append([name, sm, tn])
            rows = [(i,x) for i,x in enumerate(rows_)]
            app.post("object-sheetview", rows=rows, columns=columns, columnwidths=columnwidths, context=context)


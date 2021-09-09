from typing import Any, Optional, List, Sequence, Dict, DefaultDict, Generator
from collections import OrderedDict, defaultdict
from copy import copy

from machaon.core.typedecl import TypeProxy
from machaon.core.symbol import normalize_typename, full_qualified_name

# imported from...
# desktop
# 
#

class EMPTY_OBJECT:
    pass

#
#
#
class Object():
    def __init__(self, type, value=EMPTY_OBJECT):
        self.value: Any = value
        self.type: TypeProxy = type
        if not isinstance(self.type, TypeProxy):
            raise TypeError("'type' must be TypeInstance")
        if isinstance(self.value, Object):
            raise ValueError("An attempt to assign Object to another Object")

    def __repr__(self):
        return "<Object {1} [{0}]>".format(self.type.typename, repr(self.value))
    
    def __str__(self):
        return "{1} [{0}]".format(self.type.typename, self.summarize())
    
    def value_dstr(self):
        v = self.value
        t = type(v)
        if t.__str__ is object.__str__:
            ds = "0x{:0X}".format(id(v))
        else:
            ds = str(v)
        if self.type.is_any():
            return "{}({})".format(ds, full_qualified_name(t))
        elif not self.type.check_value_type(t):
            return "{}(!!{})".format(ds, full_qualified_name(t))
        else:
            return ds
    
    def get_typename(self):
        return self.type.get_typename()
    
    def get_conversion(self):
        return self.type.get_conversion()
    
    def copy(self):
        return Object(self.type, copy(self.value))
    
    def stringify(self) -> str:
        return self.type.stringify_value(self.value)

    def summarize(self) -> str:
        return self.type.summarize_value(self.value)

    def pprint(self, spirit):
        self.type.pprint_value(spirit, self.value)
    
    def to_pretty(self):
        return PrettyObject(self.type, self.value)
    
    def is_pretty(self):
        return False
    
    def is_error(self):
        from machaon.process import ProcessError
        return isinstance(self.value, ProcessError)
    
    def is_truth(self):
        if self.is_error():
            return False
        return bool(self.value)

    def test_truth(self):
        if self.is_error():
            raise self.value.error
        return self.value

#
class PrettyObject(Object):
    def is_pretty(self):
        return True

    def __repr__(self):
        return "<PrettyObject {1} [{0}]>".format(self.type.typename, repr(self.value))

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
    """
    オブジェクトを文字列によるキーで集めた辞書。
    メソッド名がそのままメンバ参照になる。
    """
    def __init__(self):
        self._items: Dict[int, ObjectCollectionItem] = {}
        self._namemap: DefaultDict[str, List[int]] = defaultdict(list)
    
    def __contains__(self, key):
        return key in self._namemap
    
    def __len__(self):
        return len(self._items)

    def __getitem__(self, key):
        item = self.get(key)
        if item is not None:
            return item.value
        return None

    # オブジェクトを新規作成
    def new(self, name: str, type: TypeProxy, value: Any) -> ObjectCollectionItem:
        if not isinstance(name, str) or not isinstance(type, TypeProxy):
            raise TypeError()
        o = Object(type, value)
        return self.push(name, o)

    def push(self, name: str, obj: Object) -> ObjectCollectionItem:
        # オブジェクトを追加
        if not isinstance(name, str) or not isinstance(obj, Object):
            raise TypeError()
        newident = len(self._items)
        item = ObjectCollectionItem(newident, name, obj)
        self._items[newident] = item
        self._namemap[name].append(newident)
        return item
    
    def store(self, name: str, obj: Object) -> ObjectCollectionItem:
        # オブジェクトを代入
        if not isinstance(name, str) or not isinstance(obj, Object):
            raise TypeError()
        if name not in self._namemap:
            raise ValueError("{} is not found".format(name))
        idents = self._namemap[name]
        ident = idents[0]
        item = ObjectCollectionItem(ident, name, obj)
        self._items[ident] = item
        for delident in idents[1:]:
            del self._items[delident]
        return item

    def pick(self, name) -> Generator[ObjectCollectionItem, None, None]:
        # 名前で検索する
        if name not in self._namemap:
            return
        for ident in self._namemap[name]:
            yield self._items[ident]
    
    def get(self, name) -> Optional[ObjectCollectionItem]:
        li = list(self.pick(name))
        return li[-1] if li else None

    def pick_all(self) -> Generator[ObjectCollectionItem, None, None]:
        # 全てのオブジェクトを取得
        for item in self._items.values():
            yield item
    
    def delete(self, name):
        if name not in self._namemap:
            return
        for ident in self._namemap[name]:
            del self._items[ident]
        del self._namemap[name]
    
    def get_delegation(self):        
        # 移譲先のオブジェクトを返す
        delgate_point = self.get("#delegate")
        if delgate_point is None:
            return None
        return delgate_point.object
    
    def set_delegation(self, o):
        if o is None:
            self.delete("#delegate")
        else:
            self.push("#delegate", o)

    #
    #
    #
    def asdict(self, context):
        """ @method context alias-name [=dict]
        Pythonの辞書に変換する。
        Returns:
            Any:
        """
        d = {}
        for name, ids in self._namemap.items():
            id = ids[-1]
            item = self._items[id]
            d[item.name] = item.value 
        return context.get_type("Any").new_object(d)

    def constructor(self, context, value):
        """ @meta """
        col = ObjectCollection()
        for k, v in value.items():
            if not isinstance(v, Object):
                v = context.new_object(v)
            col.push(k, v)
        return col

    def summarize(self):
        """ @meta """
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
        """ @meta """
        if len(self._items) == 0:
            text = "空です" + "\n"
            app.post("message", text)
        else:
            context = app.get_process().get_last_invocation_context() # 実行中のコンテキスト
            rows_ = []
            columns = ["名前", "値", "型"]
            for name, ids in self._namemap.items():
                for i in ids:
                    o = self._items[i].object
                    sm = o.summarize()
                    tn = o.get_typename()
                    rows_.append([name, sm, tn])
            rows = [(i,x) for i,x in enumerate(rows_)]
            app.post("object-sheetview", rows=rows, columns=columns, context=context)


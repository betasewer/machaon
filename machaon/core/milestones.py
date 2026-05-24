from typing import (
    Union, TypeGuard, dataclass_transform, 
    Type, Any, TypeVar, get_type_hints, get_origin, get_args,
    Callable
)
from dataclasses import dataclass
from types import MethodType, UnionType


class _MilestoneAutoId:
    value = 1000

    @classmethod
    def publish(cls):
        cls.value += 1
        return cls.value

def _get_milestone_id(t: type) -> int:
    if not hasattr(t, "milestone_id__"):
        raise ValueError("{}はマイルストーン型ではありません".format(t))
    return getattr(t, "milestone_id__")

def _set_milestone_id(t: type, nid: int):
    setattr(t, "milestone_id__", nid)

MilestoneType = int | Any

#
# マイルストーンをハンドラにディスパッチする
#
DispatchTag = type | int

class MilestoneDispatcher:
    def __init__(self):
        self._handlers: dict[int, tuple[Callable, int]] = {}
    
    def match(self, arg=None):
        if not isinstance(arg, DispatchTag|None):
            raise TypeError("matchの引数は型、整数、Noneのいずれかでなければなりません")
        def decorator(fn):
            self._add_handler(fn, arg)
            return fn
        return decorator

    def _add_handler(self, fn, event: DispatchTag|None = None):
        """ ハンドラーを追加する """
        # ハンドラのタグを決定する
        tags = []
        if event is not None:
            tags.append(event)
        else:
            # ハンドラの第一引数の型をタグにする
            hint = _get_first_param_hint(fn)
            if hint is None:
                raise ValueError("第一引数の型アノテーションが必要です")
            for t in _iter_union_types(hint):
                tags.append(t)
        
        # タグが整数であれば引数なし、そうでなければ引数ありのハンドラーとして登録する
        for t in tags:
            if isinstance(t, int):
                self._handlers[t] = (fn, 0)
            else:
                code = _get_milestone_id(t)
                self._handlers[code] = (fn, 1)
    
    def __call__(self, event: MilestoneType):
        """ イベントをディスパッチしてハンドラを起動する """
        if isinstance(event, int):
            code = event
        else:
            code = _get_milestone_id(type(event))
        
        if code not in self._handlers:
            return NOT_DISPATCHED # スルーする
        
        fn, arity = self._handlers[code]
        if arity == 0:
            return fn()
        else:
            return fn(event)

class NOT_DISPATCHED:
    """ ディスパッチされなかったことを表す値 """
    pass

def _iter_union_types(hint):
    """A | B や Union[A, B] を展開してイテレートする。単一型はそのまま返す。"""
    if get_origin(hint) is Union:
        # typing.Union[A, B]
        yield from get_args(hint)
        return
    if isinstance(hint, UnionType):
        # A | B (Python 3.10+)
        yield from get_args(hint)
        return
    yield hint


def _get_first_param_hint(fn, *, class_member=False) -> type | None:
    """
    関数の最初の実引数の型ヒントを返す。
    classmethod デスクリプタとバインドメソッドは型で判定し cls/self をスキップする。
    型ヒントがない場合は None を返す。
    """
    skip_first = False
    if class_member:
        if isinstance(fn, classmethod):
            # classmethod デスクリプタ: __func__ に切り替えて cls をスキップ
            fn = fn.__func__
            skip_first = True
        elif isinstance(fn, staticmethod):
            # staticmethod デスクリプタ: __func__ に切り替えるだけ
            fn = fn.__func__
        else:
            skip_first = True # プレーンなメソッド: self をスキップ
    else:
        pass # 何もしない

    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = getattr(fn, "__annotations__", {})

    import inspect
    target = None
    for paramname in inspect.signature(fn).parameters.keys():
        if skip_first:
            skip_first = False
            continue
        target = paramname
        break
    
    if target is None:
        return None
    elif target not in hints:
        return None
    return hints[target]

#
# エントリポイントのクラス
#
class _MilestoneUtil:
    def __call__(self) -> int:
        # 定数タイプのマイルストーン
        nid = _MilestoneAutoId.publish()
        return nid
    
    @staticmethod
    @dataclass_transform()
    def dataclass(klass):
        # データクラスのマイルストーン
        nid = _MilestoneAutoId.publish()
        _set_milestone_id(klass, nid)
        return dataclass(klass)
    
    def match(self, event: MilestoneType, t: DispatchTag) -> bool:
        """ eventとタグの一致を判定する """
        if isinstance(t, int):
            rcode = t
        else:
            rcode = _get_milestone_id(t)
        if isinstance(event, int):
            lcode = event
        else: 
            lcode = _get_milestone_id(type(event))
        return lcode == rcode

    T = TypeVar("T")
    def match_type(self, event: MilestoneType, t: Type[T]) -> TypeGuard[T]:
        """ 型ガード付きのマッチ判定 """
        if isinstance(t, int):
            raise TypeError("match_typeのタグは型でなければなりません")
        if isinstance(event, int):
            return False
        l = _get_milestone_id(type(event))
        r = _get_milestone_id(t)
        return l == r
        
    def dispatch(self, **kwargs) -> MilestoneDispatcher:
        """ ディスパッチ関数を作成する 
        Params:
            allow_default: ハンドラにマッチしないイベントを許可するかどうか（デフォルトはFalse）
        """
        return MilestoneDispatcher(**kwargs)


milestone = _MilestoneUtil()


"""        
import milestone as miles

class PackageManag:
    BEGIN = miles.milestone()

    @milestone.dataclass
    class DOWNLOAD_START:
        total: int
        url: str

    END = milestone()

    
def testmain():
    t = PackageManag.DOWNLOAD_START(total=100, url="http://gogogo")
    t.total

    print(PackageManag.BEGIN)
    id = getattr(PackageManag.DOWNLOAD_START, "milestone_id__")
    print(id)
    print(PackageManag.END)


def matchtest(event):
    if milestone.match(event, PackageManag.BEGIN):
        print("BEGIN", event)
    elif milestone.match(event, PackageManag.DOWNLOAD_START):
        print("DWSTART {}, {}".format(event.total, event.url))
    else:
        print("other: {}".format(event))



handle_event = milestone.dispatch()

@handle_event.add
def on_begin(event: PackageManag.BEGIN):
    print("BEGIN", event)

@handle_event.add
def on_download_start(event: PackageManag.DOWNLOAD_START):
    print("DWSTART {}, {}".format(event.total, event.url))

handle_event(PackageManag.BEGIN)
handle_event(PackageManag.DOWNLOAD_START(total=100, url="http://gogogo"))

"""
if __name__ == "__main__":
    class PackageManag:
        BEGIN = milestone()

        @milestone.dataclass
        class DOWNLOAD_START:
            total: int
            url: str

        END = milestone()

    handle_event = milestone.dispatch()
    @handle_event.match(PackageManag.BEGIN)
    def on_begin():
        print("BEGIN")

    @handle_event.match()
    def on_download_start(event: PackageManag.DOWNLOAD_START):
        print("DWSTART {}, {}".format(event.total, event.url))
    
    @handle_event.match(PackageManag.END)
    def on_end():
        print("END")

    evs = [
        PackageManag.BEGIN, 
        PackageManag.DOWNLOAD_START(total=100, url="http://gogogo"), 
        PackageManag.END
    ]
    for ev in evs:
        handle_event(ev)

    for ev in evs:
        if milestone.match(ev, PackageManag.BEGIN):
            print(ev)
        elif milestone.match_type(ev, PackageManag.DOWNLOAD_START):
            print(ev)

    def pr(fn):
        print("pr: {} = {} method={}".format(fn.__name__, type(fn), isinstance(fn, MethodType)))
        print(" first param hint: {}".format(_get_first_param_hint(fn)))
        return fn 
    
    class TEST:
        @pr
        @classmethod
        def classss(cls, event: PackageManag.DOWNLOAD_START):
            pass
        @pr
        @staticmethod
        def statss(event: PackageManag.DOWNLOAD_START):
            pass

        @pr
        def methodss(self, event: PackageManag.DOWNLOAD_START):
            pass

        def not_a_handler(self, event: PackageManag.DOWNLOAD_START):
            pass
    
    @pr
    def funcss(event: PackageManag.DOWNLOAD_START):
        pass

    pr(TEST.classss)
    pr(TEST.statss)
    pr(TEST.methodss)
    pr(TEST.not_a_handler)
    pr(TEST().methodss)


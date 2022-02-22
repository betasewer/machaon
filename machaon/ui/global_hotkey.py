
import importlib
if importlib.util.find_spec("pynput") is not None:
    from pynput.keyboard import Listener, HotKey
    available = True
else:
    available = False


class GlobalHotkey:
    available = available

    """
    グローバルなホットキーを設定する。
    """
    def __init__(self):
        self.spi = None
        self.hotkeys = [] 
        self.listener = None
        self._keys = []
                
    def add(self, label, key, fn):
        """
        Params:
            key(str): <ctrl>+<cmd>+h のように指定
            fn(str|Function):
        """
        if isinstance(fn, str):
            message = fn
        else:
            message = fn.get_message()
        self.hotkeys.append((label, key, message, fn))

    def enum(self):
        """ 
        Returns:
            List[Tuple[str, str]]: キーとメッセージ
        """
        return [(x, y) for x,_,y in self.hotkeys]
        
    def on_press(self, k):
        for hk in self._keys:
            hk.press(self.listener.canonical(k))
        
    def on_release(self, k):
        for hk in self._keys:
            hk.release(self.listener.canonical(k))

    def handler(self, label, key, fn):
        def _handler():
            if self.spi is None:
                raise ValueError("spirit is not set")
            try:
                self.spi.root.post_stray_message("message", "{} -> {}".format(key, label))
                ret = fn.run(self.spi.get_last_context())
            except Exception as e:
                from machaon.types.stacktrace import ErrorObject, verbose_display_traceback
                self.spi.root.post_stray_message("error", ErrorObject(e).short_display())
                self.spi.root.post_stray_message("message", verbose_display_traceback(e, 0xFFFFFF))
        return _handler
        
    def start(self, app):
        """ @method spirit
        リスナースレッドを開始する
        """
        if not self.hotkeys:
            return
        if not available:
            raise ValueError("pynputがありません")
        
        self._keys.clear()
        for label, key, fn, _msg in self.hotkeys:
            if isinstance(fn, str):
                from machaon.core.message import parse_sequential_function
                fn = parse_sequential_function(fn, app.get_last_context())
            hk = HotKey(HotKey.parse(key), self.handler(label, key, fn))
            self._keys.append(hk)        

        self.spi = app
        self.listener = Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()
        app.post("message", "入力リスナーを立ち上げました")
        
    def stop(self, app):
        """ @method spirit
        リスナースレッドを開始する
        """
        self.listener.stop()
        self.listener.join()
        app.post("message", "入力リスナーを停止しました")
    
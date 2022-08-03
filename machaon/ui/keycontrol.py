
from machaon.platforms.common import exists_external_module
if exists_external_module("pynput"):
    from pynput.keyboard import Listener, HotKey, Controller
    available = True
else:
    available = False

class GlobalHotkeyError(Exception):
    pass


class HotkeyFunction:
    def __init__(self, label, key, function):
        """
        Params:
            label(str): ホットキーを識別するためのラベル
            key(str): キーの組み合わせ
            message(str): メッセージ
            fn(Function()[seq]): 関数オブジェクト
        """
        self.label = label
        self.key = key
        self.function = function
        if isinstance(function, str):
            self.message = function
        else:
            self.message = function.get_message()

    def get_label(self):
        return self.label

    def get_message(self):
        return self.message

    def get_key(self):
        return self.key

    def create_hotkey(self, listener):
        """ pynput.Hotkeyオブジェクトを作成 """
        if isinstance(self.function, str):
            from machaon.core.function import parse_function
            self.function = parse_function(self.function)

        keys = HotKey.parse(self.key)
        def handler():
            self.fire(listener)
        return HotKey(keys, handler)

    def fire(self, listener):
        """ キーが押された """
        # 押されたキーを全て放す
        for key in HotKey.parse(self.key):
            listener.release(key)

        # ハンドラを実行する
        error = None
        context = listener.root.create_root_context() # コンテキストを作成
        try:
            listener.must_be_started()
            if isinstance(self.function, str):
                raise GlobalHotkeyError("関数が初期化されていません")
            listener.root.post_stray_message("message", "{} -> {}".format(self.key, self.label))
            ret = self.function.run_here(context)
            error = context.get_last_exception()
        except Exception as e:
            error = e

        # エラーが発生したら表示して終わる
        if error:
            from machaon.types.stacktrace import ErrorObject, verbose_display_traceback
            listener.root.post_stray_message("error", ErrorObject(error).short_display())
            listener.root.post_stray_message("message", verbose_display_traceback(error, 0xFFFFFF))
        else:
            listener.root.post_stray_message("message", "  return {}".format(ret))



class KeyController:
    available = available

    """
    グローバルなホットキーを設定する。
    """
    def __init__(self):
        self.root = None
        self.hotkeys = [] 
        self.listener = None
        self._keys = []
        self._controller = None

    def must_be_started(self):
        if self.root is None or self._controller is None:
            raise GlobalHotkeyError("スレッドが開始していません")

    def add_hotkey(self, label, key, fn):
        """
        Params:
            key(str): <ctrl>+<cmd>+h のように指定
            fn(str|Function):
        """
        self.hotkeys.append(HotkeyFunction(label, key, fn))

    def enum_hotkeys(self):
        """ 
        Returns:
            List[HotkeyFunction]: ラベル、キー、メッセージ
        """
        return self.hotkeys

    def push(self, k):
        codes = HotKey.parse(k)
        if len(codes) == 1:
            self._controller.tap(codes[0])
        elif len(codes) == 2:
            with self._controller.pressed(codes[0]):
                self._controller.tap(codes[1])
            #print(codes)
        elif len(codes) == 3:
            with self._controller.pressed(codes[0]):
                with self._controller.pressed(codes[1]):
                    self._controller.tap(codes[2])
        elif len(codes) == 4:
            with self._controller.pressed(codes[0]):
                with self._controller.pressed(codes[1]):
                    with self._controller.pressed(codes[2]):
                        self._controller.tap(codes[3])
        else:
            raise GlobalHotkeyError("too many meta keys")

    def press(self, k):
        self.must_be_started()
        self._controller.press(k)

    def release(self, k):
        self.must_be_started()
        self._controller.release(k)
        
    def on_press(self, k):
        for hk in self._keys:
            hk.press(self.listener.canonical(k))
        
    def on_release(self, k):
        for hk in self._keys:
            hk.release(self.listener.canonical(k))

    def start(self, app):
        """ @method spirit
        リスナースレッドを開始する
        """
        if not available:
            raise GlobalHotkeyError("pynputがインストールされていません")

        self.root = app.root
        self._controller = Controller()
        
        # ホットキーを準備する
        if not self.hotkeys:
            return
        self._keys.clear()
        for hkey in self.hotkeys:
            hk = hkey.create_hotkey(self)
            self._keys.append(hk)        

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


#
# まとめてキーを追加する
#
class HotkeySet:
    def __init__(self):
        self.entries = []
        self._newkey = None

    def __getitem__(self, key):
        self._newkey = key
        return self

    def __call__(self, label, message):
        if self._newkey is None:
            raise ValueError("")
        self.entries.append((label, self._newkey, message))
        return self
    
    def install(self, root, ignition_key):
        for label, k, message in self.entries:
            key = ignition_key + "+" + k
            root.add_hotkey(label, key, message)

    
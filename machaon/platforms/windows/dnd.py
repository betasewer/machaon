import ctypes
from machaon.platforms.windows.ctypesx import Symbols

WM_DROPFILES = 0x0233
GWL_WNDPROC = -4
GWL_USERDATA = -21

@Symbols
def Win(self):
    LONG = ctypes.c_long
    HWND = ctypes.wintypes.HWND
    UINT = ctypes.wintypes.UINT
    WPARAM = ctypes.wintypes.WPARAM
    LPARAM = ctypes.wintypes.LPARAM

    try: 
        self.SetWindowLong = ctypes.windll.user32.SetWindowLongPtrW
        self.GetWindowLong = ctypes.windll.user32.GetWindowLongPtrW
    except AttributeError: 
        self.SetWindowLong = ctypes.windll.user32.SetWindowLongW
        self.GetWindowLong = ctypes.windll.user32.GetWindowLongW
    
    self.CallWindowProc = ctypes.windll.user32.CallWindowProcW
    self.DragAcceptFiles = ctypes.windll.shell32.DragAcceptFiles
    self.DragQueryFile = ctypes.windll.shell32.DragQueryFileW
    self.DragFinish = ctypes.windll.shell32.DragFinish
    self.WNDPROC = ctypes.WINFUNCTYPE(LONG, HWND, UINT, WPARAM, LPARAM)


class DND:
    """
    ウィンドウプロシージャをドラッグ＆ドロップ対応のものにすり替える
    """
    def __init__(self):
        Win._load()
        self._dropped = []
        self._defproc = None
        self._newproc_entry = Win.WNDPROC(DND.winproc_entry)

    @staticmethod
    def winproc_entry(hwnd, message, wParam, lParam):
        ptr = Win.GetWindowLong(hwnd, GWL_USERDATA)
        this = ctypes.cast(ptr, ctypes.py_object)
        return this.value.dnd_proc(hwnd, message, wParam, lParam)

    def dnd_proc(self, hwnd, msg, wp, lp):
        """
        メッセージを処理し、ドロップされたファイルのパスを保存する。
        """
        if msg == WM_DROPFILES:
            drops = []
            count = Win.DragQueryFile(wp, -1, None, None)
            for i in range(count):
                length = Win.DragQueryFile(wp, i, None, None)
                szFile = ctypes.create_unicode_buffer(length)
                Win.DragQueryFile(wp, i, szFile, ctypes.sizeof(szFile))
                drops.append(szFile.value)
            self._dropped.append(drops)
            Win.DragFinish(wp)
        return Win.CallWindowProc(self._defproc, hwnd, msg, wp, lp)

    def enter(self, hwnd):
        """ 起動する """
        Win.DragAcceptFiles(hwnd, True)
        # ウィンドウプロシージャを置き換える
        self._defproc = Win.SetWindowLong(hwnd, GWL_WNDPROC, self._newproc_entry)
        Win.SetWindowLong(hwnd, GWL_USERDATA, ctypes.py_object(self))
    
    def update(self):
        """ 毎回の更新 """
        if self._dropped:
            drops = self._dropped.pop()
            return drops
        return None


class TkDND(DND):
    def enter(self, window):
        super().enter(window.winfo_id()) # hwndを得られる


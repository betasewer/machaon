import ctypes
import ctypes.wintypes as w
from machaon.platforms.windows.ctypesx import Symbols

GHND = 0x0042
CF_UNICODETEXT = 13

@Symbols
def Win(self):
    self.GlobalAlloc = ctypes.windll.kernel32.GlobalAlloc
    self.GlobalLock = ctypes.windll.kernel32.GlobalLock
    self.GlobalLock.restype = ctypes.c_void_p
    self.GlobalUnlock = ctypes.windll.kernel32.GlobalUnlock
    self.GlobalSize = ctypes.windll.kernel32.GlobalSize
    self.memcpy = ctypes.cdll.msvcrt.memcpy
    
    self.OpenClipboard = ctypes.windll.user32.OpenClipboard
    self.EmptyClipboard = ctypes.windll.user32.EmptyClipboard
    self.SetClipboardData = ctypes.windll.user32.SetClipboardData
    self.CloseClipboard = ctypes.windll.user32.CloseClipboard

    self.IsClipboardFormatAvailable = ctypes.windll.user32.IsClipboardFormatAvailable
    self.GetClipboardData = ctypes.windll.user32.GetClipboardData


class Exports:
    @staticmethod
    def clipboard_copy(text):
        """ クリップボードにテキストをコピーする """
        Win._load()
        # メモリに書き込む
        bufferSize = (len(text)+1)*2 # 2バイト単位で終端ヌル文字がつく
        hGlobalMem = Win.GlobalAlloc(ctypes.c_int(GHND), ctypes.c_int(bufferSize))
        lpGlobalMem = Win.GlobalLock(ctypes.c_int(hGlobalMem))
        Win.memcpy(lpGlobalMem, ctypes.c_wchar_p(text), ctypes.c_int(bufferSize))
        Win.GlobalUnlock(ctypes.c_int(hGlobalMem))
        # クリップボードに転送
        if Win.OpenClipboard(0):
            Win.EmptyClipboard()
            Win.SetClipboardData(ctypes.c_int(CF_UNICODETEXT), ctypes.c_int(hGlobalMem))
            Win.CloseClipboard()

    @staticmethod
    def clipboard_paste():
        """ クリップボードからテキストをはり付ける """
        Win._load()
        # クリップボードを開く
        text = None
        if Win.OpenClipboard(0):
            hData = Win.GetClipboardData(ctypes.c_int(CF_UNICODETEXT))
            if hData:
                dataSize = Win.GlobalSize(hData)
                lpClip = Win.GlobalLock(hData)
                textbuf = ctypes.create_unicode_buffer(int(dataSize/2))
                Win.memcpy(textbuf, lpClip, dataSize)
                Win.GlobalUnlock(hData)
                text = textbuf.value
            Win.CloseClipboard()
        return text

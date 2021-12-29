import sys
import ctypes
import ctypes.wintypes as w

GHND = 0x0042
CF_UNICODETEXT = 13

@Symbols
def Win(self):
    self.GlobalAlloc = ctypes.windll.kernel32.GlobalAlloc
    self.GlobalLock = ctypes.windll.kernel32.GlobalLock
    self.GlobalLock.restype = ctypes.c_void_p
    self.GlobalUnlock = ctypes.windll.kernel32.GlobalUnlock
    self.memcpy = ctypes.cdll.msvcrt.memcpy
    
    self.OpenClipboard = ctypes.windll.user32.OpenClipboard
    self.EmptyClipboard = ctypes.windll.user32.EmptyClipboard
    self.SetClipboardData = ctypes.windll.user32.SetClipboardData
    self.CloseClipboard = ctypes.windll.user32.CloseClipboard


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

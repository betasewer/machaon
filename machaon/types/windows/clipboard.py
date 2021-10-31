import sys
import ctypes
import ctypes.wintypes as w

GHND = 0x0042
ctypes.windll.kernel32.GlobalLock.restype = ctypes.c_void_p

CF_UNICODETEXT = 13

def clipboard_copy(text):
    """ クリップボードにテキストをコピーする """
    # メモリに書き込む
    bufferSize = (len(text)+1)*2 # 2バイト単位で終端ヌル文字がつく
    hGlobalMem = ctypes.windll.kernel32.GlobalAlloc(ctypes.c_int(GHND), ctypes.c_int(bufferSize))
    lpGlobalMem = ctypes.windll.kernel32.GlobalLock(ctypes.c_int(hGlobalMem))
    ctypes.cdll.msvcrt.memcpy(lpGlobalMem, ctypes.c_wchar_p(text), ctypes.c_int(bufferSize))
    ctypes.windll.kernel32.GlobalUnlock(ctypes.c_int(hGlobalMem))
    # クリップボードに転送
    if ctypes.windll.user32.OpenClipboard(0):
        ctypes.windll.user32.EmptyClipboard()
        ctypes.windll.user32.SetClipboardData(ctypes.c_int(CF_UNICODETEXT), ctypes.c_int(hGlobalMem))
        ctypes.windll.user32.CloseClipboard()

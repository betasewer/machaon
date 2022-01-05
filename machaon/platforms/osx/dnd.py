import objc
from AppKit import (
    NSApp, NSFilenamesPboardType, NSWindow, NSObject,
    NSDragOperationNone, NSDragOperationCopy,
    NSTitledWindowMask, NSClosableWindowMask, NSResizableWindowMask,
    NSWindowStyleMaskHUDWindow, NSMiniaturizableWindowMask,
    NSApplication, NSTextField,
    NSColor, NSArray
)
import queue

TypeFileURL = NSFilenamesPboardType
OpNone = NSDragOperationNone
OpCopy = NSDragOperationCopy


PAD_OPENED = 1
PAD_CLOSED = 2

class DNDPad(NSWindow):
    dropped = objc.ivar("dropped")

    def init(self):
        frame = ((200.0, 300.0), (250.0, 500.0))    
        self.initWithContentRect_styleMask_backing_defer_(
            frame, NSClosableWindowMask | NSTitledWindowMask | NSResizableWindowMask,
            2, False
        )
        self.setLevel_(3)
        self.setTitle_ ('')
        self.registerForDraggedTypes_([TypeFileURL, None])

        label = NSTextField.alloc()
        label.initWithFrame_(((50.0, 130.0), (200.0, 150.0)))
        label.setStringValue_("ここにドラッグ＆ドロップ")
        label.setDrawsBackground_(False)
        label.setBordered_(False)
        label.setSelectable_(True)
        label.setEditable_(False)
        self.contentView().addSubview_(label)
        
        self.setBackgroundColor_(None)

        self.dropped = []
        self.isopened = False
        self.openmsgs = queue.Queue()
        
        return self

    def draggingEntered_(self, sender):
        pboard = sender.draggingPasteboard()
        types = pboard.types()
        opType = OpNone
        if TypeFileURL in types:
            opType = OpCopy
            self.setBackgroundColor_(NSColor.selectedTextBackgroundColor())
        return opType

    def draggingExited_(self, sender):
        self.setBackgroundColor_(None)

    def performDragOperation_(self, sender):
        pboard = sender.draggingPasteboard()
        if TypeFileURL in pboard.types():
            valarray = pboard.propertyListForType_(TypeFileURL)
            for item in valarray:
                self.dropped.append(item)
            self.setBackgroundColor_(None)
            return True
        return False

    def keyDown_(self, event):
        print(event.characters())
        if event.characters() == "d":
            self.toggle_show(True)
        else:
            array = NSArray.arrayWithObject_(event)
            self.interpretKeyEvents_(array)

    @objc.python_method
    def toggle_show(self, toggle=None):
        if toggle is not None: self.isopened=toggle
        if self.isopened:
            self.orderOut_(None)
            self.openmsgs.put(PAD_CLOSED)
        else:
            self.makeKeyAndOrderFront_(NSApp)
            self.openmsgs.put(PAD_OPENED)
        self.isopened = not self.isopened

    @objc.python_method
    def update_dropped(self):
        if not self.dropped:
            return None
        return [self.dropped.pop()]

    @objc.python_method
    def update_openstatus(self):
        try:
            return self.openmsgs.get_nowait()
        except queue.Empty:
            return None
        

class DNDPadDelegate(NSObject):
    def windowShouldClose_(self, wnd):
        wnd.toggle_show()
        return False # 隠すだけで閉じない


def get_tk_ns_window(fallback=False):
    # 最前面のtkのビューを取得し、machaonの画面とみなす 
    for wnd in reversed(NSApp.windows()):
        print(type(wnd).__name__)
        if type(wnd).__name__.endswith("TKWindow"):
            return wnd
    if not fallback:
        raise ValueError("Tkのウィンドウが見つかりません")
    return None


class TkDND:
    """
    ドラッグ＆ドロップ専用のウィンドウを別に表示する
    """
    def __init__(self):
        self._pad = None
        self._paddelegate = None
        self._switchbutton = None
        self._mainwindow = None
        
    def enter(self, root):
        """ 起動する """
        # 可能ならフォーカス用にメインウィンドウを取得する
        self._mainwindow = get_tk_ns_window(fallback=True)
        # ウィンドウを作成する
        self._paddelegate = DNDPadDelegate.alloc().init()
        self._pad = DNDPad.alloc().init() 
        self._pad.setDelegate_(self._paddelegate)
        self._switchbutton = root.add_toggle_for_DND_pad(self._pad.toggle_show) # 表示切り替えボタンを設定
        self._pad.toggle_show(True) # 非表示にする

    def update(self):
        """ 毎回の更新 """
        p = self._pad.update_dropped()
        if p is not None:
            self._pad.toggle_show(True) # ドロップされたら閉じる

        m = self._pad.update_openstatus()
        if m is not None:
            if m == PAD_OPENED:
                self._switchbutton["text"] = "ドラッグ＆ドロップパネルを閉じる"
            elif m == PAD_CLOSED:
                self._switchbutton["text"] = "ドラッグ＆ドロップパネルを開く"
                if self._mainwindow:
                    self._mainwindow.makeKeyAndOrderFront_(NSApp) # メインウィンドウをキーウィンドウに戻す
        return p



if __name__ == "__main__":

    import tkinter
    root = tkinter.Tk()
    root.geometry("300x300")
    root.title("main window")

    delg = DNDPadDelegate.alloc().init()
    dnd = DNDPad.alloc().init()
    dnd.setDelegate_(delg)

    button = tkinter.Button(root, text="open DND pad", command=lambda:dnd.toggle_show())
    button.pack(fill=tkinter.X)

    class WindowQuitter:
        def __init__(self, wnd) -> None:
            self._quit = False
            self._wnd = wnd

        def quit(self):
            self._quit = True
            self._wnd.destroy()
        
        def isquit(self):
            return self._quit

    q = WindowQuitter(root)
    root.protocol("WM_DELETE_WINDOW", q.quit)

    while not q.isquit():
        root.update()
        p = dnd.update_dropped()
        if p is not None:
            print("dropped: " + ", ".join(p))
    


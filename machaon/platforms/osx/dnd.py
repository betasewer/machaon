from Foundation import (
    NSWindow, NSPasteboard
)
from objc import (
    IBOutlet
)
from AppKit import (
    NSApp, NSFilenamesPboardType,
    NSDragOperationNone, NSDragOperationCopy
)

TypeFileURL = NSFilenamesPboardType
OpNone = NSDragOperationNone
OpCopy = NSDragOperationCopy

def install_dnd(self):
    def draggingEntered_(sender):
        print('dragging entered doctor who')
        pboard = sender.draggingPasteboard()
        types = pboard.types()
        opType = OpNone
        if TypeFileURL in types:
            opType = OpCopy
        return opType

    def performDragOperation_(sender):
        print('preform drag operation')
        pboard = sender.draggingPasteboard()
        successful = False
        if TypeFileURL in pboard.types():
            fileAStr = pboard.propertyListForType_(TypeFileURL)[0]
            print(fileAStr.encode('utf-8'))
            successful = True
        print(self.form_file)
        return successful
        
    self.form_file = IBOutlet()
    self.mainWindow = IBOutlet()
    self.draggingEntered_ = draggingEntered_
    self.performDragOperation_ = performDragOperation_
    
    self.registerForDraggedTypes_([NS_PasteboardFileURL, None])
    return self


class Controller(NSWindow):
    
    #File to encode or decode
    form_file = IBOutlet()
    mainWindow = IBOutlet()

    #drag and drop ability
    def awakeFromNib(self):
        self.registerForDraggedTypes_([NSFilenamesPboardType, None])
        print("registerd drag type")

    def draggingEntered_(self, sender):
        print('dragging entered doctor who')
        pboard = sender.draggingPasteboard()
        types = pboard.types()
        opType = NSDragOperationNone
        if NSFilenamesPboardType in types:
            opType = NSDragOperationCopy
        return opType

    def performDragOperation_(self,sender):
        print('preform drag operation')
        pboard = sender.draggingPasteboard()
        successful = False
        if NSFilenamesPboardType in pboard.types():
            print('my actions finally working')
            fileAStr = pboard.propertyListForType_(NSFilenamesPboardType)[0]
            print(type(fileAStr.encode('utf-8')))
            successful = True
        print(self.form_file)
        return successful


def get_ns_view():
    view = NSApp.windows()[-1].contentView()
    return view


class DND:
    def __init__(self):
        self._dropped = []
        
    def enter(self, hwnd):
        """ 起動する """
        print('registerd drag type')

    def update(self, tw=None):
        """ 毎回の更新 """
        if self._dropped:
            drops = self._dropped.pop()
            drops.insert(0, "dropped:")
            if tw:
                tw.delete(1.0, "end")
                tw.insert(1.0, "\n".join(drops))
        return None


if __name__ == "__main__":
    app = tkinter.Tk()
    app.title("DnD test")
    app.geometry("300x300")

    class Quit:
        def __init__(self, w):
            self.value = False
            self.w = w
        def __call__(self):
            self.value = True
            self.w.destroy()
    quitted = Quit(app)
    app.protocol("WM_DELETE_WINDOW", quitted)
    
    tw = tkinter.Text(app, width=30, height=16)
    tw.pack(fill='both', expand=1)

    dnd = DND()
    dnd.enter(app.winfo_id())
    
    while not quitted.value:
        dnd.update(tw)
        app.update()



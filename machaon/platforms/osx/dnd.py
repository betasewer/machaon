

class DND:
    def __init__(self):
        self._dropped = []
        
    def enter(self, hwnd):
        """ 起動する """
        
        
        
    
    def update(self, tw):
        """ 毎回の更新 """
        if self._dropped:
            drops = self._dropped.pop()
            drops.insert(0, "dropped:")
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




class Symbols:
    def __init__(self, initer):
        self._s_symbols = {}
        self._s_initer = initer
        self._s_loaded = False

    def _load(self):
        if self._s_loaded:
            return
        self._s_initer(self)
        self._s_loaded = True
        
    def __getattr__(self, name):
        if name not in self._s_symbols:
            raise KeyError("Unloaded: " + name)
        return self._s_symbols[name]
        
    def __setattr__(self, name, value):
        if name.startswith("_s_"):
            super().__setattr__(name, value)
        else:
            self._s_symbols[name] = value
        return self
  

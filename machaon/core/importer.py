import importlib
import builtins
import inspect

#
#
#
def attribute_loader(expr, *, attr=None, location=None):
    if attr is None:
        mod, _, member = expr.rpartition(".")
        if not member:
            member = expr
            mod = None
    else:
        member = attr
        mod = expr
    if location:
        return PyModuleFileAttributeLoader(mod, location, member)
    else:
        return PyModuleAttributeLoader(mod, member)

def module_loader(expr, *, location=None):
    if location:
        return PyModuleFileAttributeLoader(expr, location)
    else:
        return PyModuleAttributeLoader(expr)


class PyAttributeLoader:
    def __init__(self, member = None):
        self.membername = member
        self._m = None
    
    def load(self):
        if self._m is None:
            self._m = self.load_module()
        return self._m
        
    def load_module(self):
        raise NotImplementedError()
    
    def __call__(self, *, fallback=False):
        mod = self.load()
        loaded = getattr(mod, self.membername, None)
        if loaded is None and not fallback:
            raise ValueError("ターゲット'{}'はモジュール'{}'に存在しません".format(self.membername, mod.__name__))
        return loaded
    
    def enum_type_describers(self):
        """型を定義しているクラスをモジュールから列挙する"""
        mod = self.load()
        for _name, value in inspect.getmembers(mod, inspect.isclass):
            if value.__module__ != mod.__name__: # インポートされた要素を無視する
                continue
            doc = getattr(value, "__doc__", None)
            if doc is None:
                continue
            doc = doc.lstrip()
            if doc.startswith("@type"):
                yield value

#
# Pythonのモジュールからロードする
#
class PyModuleAttributeLoader(PyAttributeLoader):
    def __init__(self, module, member = None):
        super().__init__(member)
        self.modulespec = module
    
    def load_module(self):
        if self.modulespec:
            mod = importlib.import_module(self.modulespec)
        else:
            mod = builtins
        return mod
    
    def __str__(self) -> str:
        parts= []
        if self.modulespec:
            parts.append(self.modulespec)
        if self.membername:
            parts.append(self.membername)
        return ".".join(parts)

#
# Pythonのファイルからロードする
#
class PyModuleFileAttributeLoader(PyAttributeLoader):
    def __init__(self, name, path, member = None):
        super().__init__(member)
        self.name = name
        self.filepath = path
    
    def load_module(self):
        spec = importlib.util.spec_from_file_location(self.name, self.filepath)
        if spec is None:
            raise FileNotFoundError(self.filepath)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def __str__(self) -> str:
        parts= []
        parts.append("{}[{}]".format(self.name, self.filepath))
        if self.membername:
            parts.append(self.membername)
        return ".".join(parts)


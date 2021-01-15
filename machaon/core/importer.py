import importlib
import builtins
import inspect

#
#
#
def attribute_loader(expr):
    mod, _, member = expr.rpartition(".")
    if not member:
        member = expr
        mod = None
    return PyAttributeLoader(mod, member)

def module_loader(expr):
    return PyAttributeLoader(expr)

#
# Pythonのモジュールからロードする
#
class PyAttributeLoader:
    def __init__(self, module, member = None):
        self.modulespec = module
        self.membername = member
    
    def entrypoint(self) -> str:
        parts= []
        if self.modulespec:
            parts.append(self.modulespec)
        if self.membername:
            parts.append(self.membername)
        return ".".join(parts)

    def load_module(self):
        if self.modulespec:
            mod = importlib.import_module(self.modulespec)
        else:
            mod = builtins
        return mod

    def __call__(self, *, fallback=False):
        mod = self.load_module()
        loaded = getattr(mod, self.membername, None)
        if loaded is None and not fallback:
            raise ValueError("ターゲット'{}'はモジュール'{}'に存在しません".format(self.membername, self.modulespec))
        return loaded
    
    def enum_type_describers(self):
        """型を定義しているクラスをモジュールから列挙する"""
        mod = self.load_module()
        for _name, value in inspect.getmembers(mod, inspect.isclass):
            doc = getattr(value, "__doc__", "").lstrip()
            if doc.startswith("@type"):
                yield value

#
#
#

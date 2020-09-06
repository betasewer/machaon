import importlib
import builtins

SIGILS_IMPORT_TARGET = "<>"

#
#
#
def attribute_loader(expr, *, implicit_syntax=False):
    if implicit_syntax:
        mod, _, member = expr.rpartition(".")
        if not member:
            member = expr
            mod = None
    else:
        if not expr.startswith(SIGILS_IMPORT_TARGET[0]) or not expr.endswith(SIGILS_IMPORT_TARGET[1]):
            return None
        mod, _, member = expr[1:-1].strip().rpartition(".")
        if not member:
            member = mod
            mod = None

    return PyAttributeLoader(mod, member)

#
# Pythonのモジュールからロードする
#
class PyAttributeLoader:
    def __init__(self, module, member):
        self.modulespec = module
        self.membername = member

    def __call__(self, *, fallback=False):
        if self.modulespec:
            mod = importlib.import_module(self.modulespec)
        else:
            mod = builtins
        loaded = getattr(mod, self.membername, None)
        if loaded is None and not fallback:
            raise ValueError("ターゲット'{}'はモジュール'{}'に存在しません".format(self.membername, self.modulespec))
        return loaded

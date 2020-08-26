import importlib

SIGILS_IMPORT_TARGET = "<>" 

#
#
#
def get_importer(expr, *, no_implicit=False):
    if expr.startswith(SIGILS_IMPORT_TARGET[0]) and expr.endswith(SIGILS_IMPORT_TARGET[1]):
        return PyModuleImporter(expr[1:-1].strip())
    if not no_implicit and "." in expr:
        return PyModuleImporter(expr)
    return None

#
# Pythonのモジュールからロードする
#
class PyModuleImporter:
    def __init__(self, target):
        self.modulespec, _, self.membername = target.rpartition(".")

    def __call__(self, *, fallback=False):
        mod = importlib.import_module(self.modulespec)
        loaded = getattr(mod, self.membername, None)
        if loaded is None and not fallback:
            raise ValueError("ターゲット'{}'はモジュール'{}'に存在しません".format(membername, modulespec))
        return loaded

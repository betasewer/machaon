import importlib

#
#
#
def maybe_import_target(expr):
    return "." in expr

#
# Pythonのモジュールからロードする
#
def import_member(name, *, fallback=False):
    modulespec, _, membername = name.rpartition(".")
    mod = importlib.import_module(modulespec)
    loaded = getattr(mod, membername, None)
    if loaded is None and not fallback:
        raise ValueError("ターゲット'{}'はモジュール'{}'に存在しません".format(membername, modulespec))
    return loaded

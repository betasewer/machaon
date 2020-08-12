
#
#
#
def maybe_import_target(expr):
    return "." in expr

#
#
#
def import_member(name):
    # Pythonのモジュールからロードする
    import importlib
    modulespec, _, membername = name.rpartition(".")
    mod = importlib.import_module(modulespec)
    loaded = getattr(mod, membername, None)
    if loaded is None:
        raise ValueError("ターゲット'{}'はモジュール'{}'に存在しません".format(membername, modulespec))
    return loaded

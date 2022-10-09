#
# shell
#

common_known_names = [
    "home", "desktop", "documents", "downloads", 
    "pictures", "musics", "videos", 
    "applications", "programs", "system",
    "fonts", 
]

class Unsupported(Exception):
    pass

class NotSupportedAttrs:
    """ サポートされない機能。属性にアクセスすると例外を投げる """
    def __getattribute__(self, name):
        raise Unsupported(name)


def exists_external_module(*ps):
    import importlib.util
    for p in ps:
        if None is importlib.util.find_spec(p):
            return False
    return True

def import_external_module(p):
    import importlib.util
    spec = importlib.util.find_spec(p)
    if spec is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def fallback_generic(name):
    import importlib
    mod = importlib.import_module("machaon.platforms.generic.{}".format(name))
    return getattr(mod, "Exports", None)


class EmptyMixin:
    pass

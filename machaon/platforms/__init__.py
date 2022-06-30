#
#
# プラットフォームごとの実装を呼び出す
#
#
def get_platform():
    import sys
    return sys.platform

def is_windows():
    return get_platform() == "win32"

def is_osx():
    return get_platform() == "darwin"


def _import_platform_module(name):
    system = get_platform()
    if system == "win32":
        pltdir = "windows"
    elif system == "darwin":
        pltdir = "osx"
    elif system == "linux":
        pltdir = "linux"
    else:
        pltdir = "generic"
        
    import importlib
    import importlib.util
    spec = importlib.util.find_spec("machaon.platforms.{}.{}".format(pltdir, name))
    if spec is None:
        mod = importlib.import_module("machaon.platforms.generic.{}".format(name))
    else:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    from machaon.platforms.common import NotSupportedAttrs
    return getattr(mod, "Exports", NotSupportedAttrs())


def shellpath():
    """
    パス関連
    """
    return _import_platform_module("path")

def clipboard():
    """
    クリップボード
    """
    return _import_platform_module("clipboard")

def ui():
    """
    コンソール
    """
    return _import_platform_module("ui")
    
def draganddrop():
    """
    ドラッグアンドドロップの実装
    """
    return _import_platform_module("dnd")


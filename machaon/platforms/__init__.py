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
    else:
        raise ValueError("Unsupported system: "+system)
    
    import importlib
    return importlib.import_module("machaon.platforms.{}.{}".format(pltdir, name))


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

def console():
    """
    コンソール
    """
    return _import_platform_module("console")
    
def draganddrop():
    """
    ドラッグアンドドロップの実装
    """
    return _import_platform_module("dnd")


    
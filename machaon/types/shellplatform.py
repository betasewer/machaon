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

#
# shell
#
common_known_names = [
    "home", "desktop", "documents", "downloads", 
    "pictures", "musics", "videos", 
    "applications", "programs", "system",
    "fonts", 
]

def shellpath():
    """
    パス関連のモジュール
    """
    module = None 
    system = get_platform()
    if system == "win32":
        import machaon.types.windows.path as module
    elif system == "darwin":
        import machaon.types.osx.path as module
    else:
        raise ValueError("Unsupported system: "+system)
    return module
    

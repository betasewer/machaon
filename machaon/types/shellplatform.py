#
#
# プラットフォームごとの実装を呼び出す
#
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
    import sys
    system = sys.platform
    if system == "win32":
        import machaon.types.windows.path as module
    elif system == "darwin":
        import machaon.types.osx.path as module
    else:
        raise ValueError("Unsupported system: "+system)
    return module
    

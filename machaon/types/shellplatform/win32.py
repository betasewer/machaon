import os

def location_name_to_path(name: str, param: str = ""):
    """
    特殊なフォルダ・ファイルの名前からパスを得る。
    """
    # windows
    home = os.environ['USERPROFILE']
    if name == "home":
        return home
    elif name == "desktop":
        return os.path.join(home, "Desktop")
    elif name == "documents":
        return os.path.join(home, "Documents")
    elif name == "downloads":
        return os.path.join(home, "Downloads")
    elif name == "pictures":
        return os.path.join(home, "Pictures")
    elif name == "musics":
        return os.path.join(home, "Musics")
    elif name == "videos":
        return os.path.join(home, "Videos")
    elif name == "applications" or name == "programs":
        if param == "32":
            return os.environ["PROGRAMFILES(X86)"]
        else:
            return os.environ["PROGRAMFILES"]
    elif name == "windows":
        win = os.environ["WINDIR"]
        return win
    elif name == "system":
        win = os.environ["WINDIR"]
        if param == "32":
            return os.path.join(win, "SysWOW64")
        else:
            return os.path.join(win, "System32")
    else:
        # 環境変数ならそのまま返す
        envname = name.upper()
        if envname in os.environ:
            return os.environ[envname]

    return None
    
    
def start_file(path, operation=None):
    """
    デフォルトの方法でパスを開く。
    """
    os.startfile(path, operation or "open")


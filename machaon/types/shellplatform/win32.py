import os

def location_name_to_path(name: str):
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
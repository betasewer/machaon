import os
from machaon.platforms.common import common_known_names

def get_known_path(name: str, param: str = "", approot = None):
    """
    特殊なフォルダ・ファイルの名前からパスを得る。
    """
    # mac
    home = os.path.expanduser("~")
    if name == "home":
        return home
    elif name == "desktop":
        return os.path.join(home, "Desktop")
    elif name == "documents":
        return os.path.join(home, "Documents")
    elif name == "downloads":
        return os.path.join(home, "Downloads")
    elif name == "applications" or name == "programs":
        return os.path.join(home, "Applications")
    elif name == "pictures":
        return os.path.join(home, "Pictures")
    elif name == "musics":
        return os.path.join(home, "Music")
    elif name == "videos":
        return os.path.join(home, "Movies")
    elif name == "library":
        return os.path.join(home, "Library")
    elif name == "python":
        p = which_path("python3")
        if p is None:
            p = which_path("python")
        return p
    else:
        # 環境変数ならそのまま返す
        envname = name.upper()
        if envname in os.environ:
            return os.environ[envname]
            
    return None
    
def known_paths(_approot):
    """
    定義済みのパスのリスト
    """
    for x in common_known_names:
        yield x, get_known_path(x)
    
def start_file(path, operation=None):
    """
    デフォルトの方法でパスを開く。
    """
    import subprocess
    if operation is None:
        subprocess.run(["open", path])
    elif operation == "explore":
        subprocess.run(["open", path])
    else:
        raise ValueError("Unsupported")

def has_hidden_attribute(path):
    """
    隠し属性がついているファイルか。
    """
    import importlib.util
    spec = importlib.util.find_spec("Foundation")
    if spec is None:
        return False
    from Foundation import NSURL, NSURLIsHiddenKey
    url = NSURL.fileURLWithPath_(path)
    result = url.getResourceValue_forKey_error_(None, NSURLIsHiddenKey, None)
    return result[1]
    
def which_path(name):
    """
    whichコマンドを呼ぶ。
    """
    from machaon.shellpopen import popen_capture
    p = ""
    for msg in popen_capture(["which", name]):
        if msg.is_output():
            p += msg.text
    p = p.strip()
    if p:
        return p    
    return None 
    

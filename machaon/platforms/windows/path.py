import os
import stat
from ctypes import (
    windll, c_wchar_p, byref, wintypes, POINTER
)
from machaon.platforms.common import common_known_names
from machaon.platforms.windows.guid import GUID, parse_guid, guid_entries

def shell_get_known_folder_path(SHGetKnownFolderPath, guid):
    """
    SHGetKnownFolderPathを実行する
    """
    SHGetKnownFolderPath.argtypes = [POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, POINTER(c_wchar_p)]
    pathptr = c_wchar_p()
    SHGetKnownFolderPath(byref(guid), 0, None, byref(pathptr))
    return pathptr.value

def get_GUID_names_file(approot=None):
    """ デフォルトのGUIDリストを取得する """
    if approot is not None:
        p = approot.get_GUID_names_file()
        if p is not None:
            return p
    p = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../configs", "guid.ini"))
    if not os.path.exists(p):
        raise ValueError("Default guid.init does not exist")
    return p

class KnownPaths():
    def __init__(self, approot):
        self.SHGetKnownFolderPath = None
        self.guid_db_path = get_GUID_names_file(approot)

    def _load_apis(self):
        self.SHGetKnownFolderPath = windll.shell32.SHGetKnownFolderPath

    def _known_dir(self, name):
        guid = parse_guid("FOLDERID." + name, self.guid_db_path)
        return self._get_path(guid)
    
    def _get_path(self, guid):
        return shell_get_known_folder_path(self.SHGetKnownFolderPath, guid)

    # ユーザーフォルダ
    def home(self):
        return self._known_dir("profile")

    def desktop(self):
        return self._known_dir("desktop")

    def documents(self):
        return self._known_dir("documents")

    def downloads(self):
        return self._known_dir("downloads")
    
    def pictures(self):
        return self._known_dir("pictures")
        
    def musics(self):
        return self._known_dir("music")

    def videos(self):
        return self._known_dir("videos")

    # システム
    def applications(self, param=None):
        if param == "32":
            return self._known_dir("ProgramFilesX86")
        elif param == "64":
            return self._known_dir("ProgramFilesX64")
        else:
            return self._known_dir("ProgramFiles")
    
    def programs(self, param=None):
        return self.applications(param)
    
    def fonts(self):
        return self._known_dir("fonts")

    def system(self, param=None):
        if param == "32":
            return self._known_dir("SystemX86")
        else:
            return self._known_dir("System")

    # windows
    def windows(self):
        return self._known_dir("windows")

    # デフォルト
    def fallback(self, name):
        return self._known_dir(name)
    
    def special_locations(self):
        for k, v in guid_entries(self.guid_db_path, "FOLDERID"):
            yield k, self._get_path(parse_guid(v))


class EnvPaths():
    def __init__(self):
        self._home = os.environ['USERPROFILE']
    
    def _user(self, tail):
        return os.path.join(self._home, tail)
    
    # ユーザーフォルダ
    def home(self):
        return self.home

    def desktop(self):
        return self._user("Desktop")

    def documents(self):
        return self._user("Documents")

    def downloads(self):
        return self._user("Downloads")
    
    def pictures(self):
        return self._user("Pictures")
        
    def musics(self):
        return self._user("Musics")

    def videos(self):
        return self._user("Videos")

    # システム
    def applications(self, param=None):
        if param == "32":
            return os.environ["PROGRAMFILES(X86)"]
        else:
            return os.environ["PROGRAMFILES"]
    
    def fonts(self):
        return self._known_dir("fonts")

    def system(self, param=None):
        win = os.environ["WINDIR"]
        if param == "32":
            return os.path.join(win, "SysWOW64")
        else:
            return os.path.join(win, "System32")

    # windows
    def windows(self):
        return os.environ["WINDIR"]

    # デフォルト
    def fallback(self, name):
        return None
    
    def special_locations(self):
        return []


#
#
#
#
#
def get_known_path(name: str, param: str = "", approot = None):
    """
    特殊なフォルダ・ファイルの名前からパスを得る。
    """
    paths = KnownPaths(approot)
    try:
        paths._load_apis()
    except AttributeError:
        paths = EnvPaths() # type: ignore

    # それぞれの実装から返す
    key = name.lower()
    if key == "fallback":
        raise ValueError("不正な名前です")
    access = getattr(paths, key, None)
    if access:
        path = access(param) if param else access()
    else:
        path = paths.fallback(key)
    if path:
        return path

    # 環境変数から探して返す
    envname = name.upper()
    if envname in os.environ:
        return os.environ[envname]

    return None

def known_paths(approot):
    names = common_known_names + [
        # platform spec
        "windows",
    ]
    common_names = set(names)

    paths = KnownPaths(approot)
    try:
        paths._load_apis()
    except AttributeError:
        paths = EnvPaths() # type: ignore
    
    for k in names:
        yield k, getattr(paths, k)()
    
    for k, v in paths.special_locations():
        if not k in common_names:
            yield k, v

def start_command_powershell(path, operation=None):
    ps = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    if not os.path.isfile(ps):
        return None
    cmds = []
    cmds.append(ps)
    cmds.append("-NonInteractive")
    cmds.append("-NoLogo")
    if operation:
        starter = """ -Command "Start-Process '{}' -Verb {}" """.format(path, operation)
    else:
        starter = """ -Command "Start-Process '{}'" """.format(path)
    cmds.append(starter)
    return cmds

def start_file(path, operation=None):
    """
    デフォルトの方法でパスを開く。
    """
    os.startfile(path, operation or "open")

def has_hidden_attribute(path):
    """
    隠し属性がついているファイルか。
    """
    if os.stat(path).st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN:
        return True
    return False

def open_by_system_text_editor(path, line=None, column=None):
    """
    メモ帳でファイルを開く。
    """
    import subprocess
    args = []
    args.append("notepad.exe")
    args.append(path)
    subprocess.Popen(args)



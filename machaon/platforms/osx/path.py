import os
from machaon.platforms.common import exists_external_module
from machaon.platforms.unix.unixpath import UnixPath

import machaon.platforms.generic.path
Basic = machaon.platforms.generic.path.Exports


class OSXPath(UnixPath):
    """ osx独自のパス機能 """
    def realsize(self, f):
        """ @method
        ファイルの実際のサイズ
        Returns:
            Int:
        """
        return f.stat.st_rsize
        
    def creator(self, f):
        """ @method
        ファイルの作成者
        Returns:
            Str:
        """
        return f.stat.st_creator

    def osfiletype(self, f):
        """ @method
        ファイルタイプ
        Returns:
            Str:
        """
        return f.stat.st_type


class Exports(Basic):
    @staticmethod
    def get_known_path(name: str, param: str = "", approot = None):
        """
        特殊なフォルダ・ファイルの名前からパスを得る。
        """
        # mac
        home = os.path.expanduser("~")
        if name == "desktop":
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
        else:
            return Basic.get_known_path(name, param, approot)

    @staticmethod
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

    @staticmethod
    def has_hidden_attribute(path):
        """
        隠し属性がついているファイルか。
        """
        if not exists_external_module("Foundation"):
            return False
        import Foundation # import_関数では正しくインポートできない
        url = Foundation.NSURL.fileURLWithPath_(path)
        result = url.getResourceValue_forKey_error_(None, Foundation.NSURLIsHiddenKey, None)
        return result[1]
    
    PlatformPath = OSXPath


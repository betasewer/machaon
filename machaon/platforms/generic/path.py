import os
from machaon.platforms.common import common_known_names, Unsupported

class Exports:
    @staticmethod
    def get_known_path(name: str, param: str = "", approot = None):
        """
        特殊なフォルダ・ファイルの名前からパスを得る。
        """
        # mac
        home = os.path.expanduser("~")
        if name == "home":
            return home
        elif name == "python":
            p = Exports.which_path("python3")
            if p is None:
                p = Exports.which_path("python")
            return p
        else:
            # 環境変数ならそのまま返す
            envname = name.upper()
            if envname in os.environ:
                return os.environ[envname]
        
        return None
        
    @staticmethod
    def known_paths(_approot):
        """
        定義済みのパスのリスト
        """
        for x in common_known_names:
            yield x, Exports.get_known_path(x)
        
    @staticmethod
    def start_file(path, operation=None):
        """
        デフォルトの方法でパスを開く。
        """
        raise Unsupported("start_file")

    @staticmethod
    def has_hidden_attribute(path):
        """
        隠し属性がついているファイルか。
        """
        return False
        
    @staticmethod
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
    

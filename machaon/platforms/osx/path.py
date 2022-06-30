import os
from machaon.platforms.common import common_known_names
import machaon.platforms.generic as generic

class Exports(generic.path.Exports):
    @staticmethod
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
    
    

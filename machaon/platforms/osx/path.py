import os
from machaon.platforms.common import import_external_module
import machaon.platforms.generic.path

class Exports(machaon.platforms.generic.path.Exports):
    @staticmethod
    def has_hidden_attribute(path):
        """
        隠し属性がついているファイルか。
        """
        Foundation = import_external_module("Foundation")
        if Foundation is None:
            return False
        url = Foundation.NSURL.fileURLWithPath_(path)
        result = url.getResourceValue_forKey_error_(None, Foundation.NSURLIsHiddenKey, None)
        return result[1]
    
    

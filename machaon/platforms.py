import subprocess

#
# OSごとの設定
#
#
class _Windows:
    preferred_fontname = "Consolas"
    preferred_fontsize = 10

    @classmethod
    def openfile(cls, path):
        subprocess.run(["start", path], shell=True)
        
#
class _Macintosh:
    preferred_fontname = "Menlo"
    preferred_fontsize = 16

    @classmethod
    def openfile(cls, path):
        subprocess.run(["open", path], check=True)
        
#
class _Unix:
    preferred_fontname = "Verdana"
    preferred_fontsize = 10
    
    @classmethod
    def openfile(cls, path):
        subprocess.run(["open", path], check=True)


#
#
#
current = _Unix

import platform
_platform = platform.system()
if _platform == 'Windows':
    current = _Windows
elif _platform == 'Darwin':
    current = _Macintosh
del _platform

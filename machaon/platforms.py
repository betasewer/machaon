import os
import subprocess
from typing import Any


#
# OSごとの設定
#
#
class _Windows:
    name = "win"

    preferred_fontname = "ＭＳ ゴシック"
    preferred_fontsize = 10

    default_encoding = "cp932"

    @classmethod
    def openfile(cls, path):
        subprocess.run(["start", path], shell=True)
    
    @classmethod
    def shell_ui(cls):
        from machaon.ui.shell import WinShellUI
        return WinShellUI()
        
#
class _Macintosh:
    name = "mac"

    preferred_fontname = "Menlo"
    preferred_fontsize = 14
    
    default_encoding = "shift-jis"

    @classmethod
    def openfile(cls, path):
        subprocess.run(["open", path], check=True)
        
    @classmethod
    def shell_ui(cls):
        from machaon.ui.shell import ShellUI
        return ShellUI("utf-8")

#
class _Linux:
    name = "linux"

    preferred_fontname = "Verdana"
    preferred_fontsize = 10
    
    default_encoding = "utf-8"

    @classmethod
    def openfile(cls, path):
        subprocess.run(["open", path], check=True)

    @classmethod
    def shell_ui(cls):
        from machaon.ui.shell import ShellUI
        return ShellUI("utf-8")

#
#
#
current: Any = _Linux

import platform
_platform = platform.system()
if _platform == 'Windows':
    current = _Windows
elif _platform == 'Darwin':
    current = _Macintosh
del _platform


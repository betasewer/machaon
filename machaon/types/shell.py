import os
import shutil
import stat
import re
import time
import datetime
import math
from collections import defaultdict

from typing import Optional

from machaon.shellpopen import popen_capture

#
#
#
_specname_path = {
    "desktop" : ""
}
def _special_name_to_path(name: str):
    name = name.lower()
    if os.name == "nt":
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

    raise ValueError("Unknwon spec name")

def special_name_to_path(name: str):
    """
    特殊なフォルダ・ファイルの名前からパスを得る。
    """
    p = _special_name_to_path(name)
    return Path(p)


#
#
#
class Path():
    """ @type
    ファイル・フォルダのパス
    Typename: Path
    """
    def __init__(self, path):
        self._path = path
        self._isdir = None
        self._stat = None
    
    def __str__(self):
        return self._path
    
    @property
    def stat(self):
        if self._stat is None:
            self._stat = os.stat(self._path)
        return self._stat

    #
    #
    #
    def path(self):
        """ @method
        パス
        Returns:
            Str:
        """
        return self._path

    def name(self):
        """ @method
        ファイル・フォルダ名
        Returns:
            Str:
        """
        return os.path.basename(self._path)
    
    def stemname(self):
        """ @method
        拡張子なしのファイル名
        Returns:
            Str:
        """
        n, _ext = os.path.splitext(os.path.basename(self._path))
        return n
    
    def extension(self):
        """ @method
        拡張子
        Returns:
            Str:
        """
        _n, ext = os.path.splitext(self._path)
        return ext
    
    def hasext(self, names):
        """ @method
        いずれかの拡張子を持っているか
        Params:
            names(Tuple):
        Returns:
            Bool:
        """
        if self.isdir():
            return False
        ext = self.extension().lstrip(".")
        for name in names:
            if ext == name.lstrip("."):
                return True
        return False
    
    def isdir(self):
        """ @method
        フォルダのパスかどうか
        Returns:
            Bool:
        """
        if self._isdir is None:
            self._isdir = os.path.isdir(self._path)
        return self._isdir
    
    def modtime(self):
        """ @method
        変更日時
        Returns:
            Datetime:
        """
        return datetime.datetime.fromtimestamp(os.path.getmtime(self._path))
    
    def size(self):
        """ @method
        ファイルサイズ
        Returns:
            Number[Byte]:
        """
        if self.isdir():
            return 0
        return os.path.getsize(self._path)
        #if size_bytes == 0:
        #    return "0B"
        #i = int(math.floor(math.log(size_bytes, 1024)))
        #p = math.pow(1024, i)
        #s = round(size_bytes / p, 2)
        #size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        #return "{:.0F} {}".format(s, size_name[i])
    
    def mode(self):
        """ @method
        ファイルモードを示す文字列
        Returns:
            Str:
        """
        return stat.filemode(self.stat.st_mode)
    
    #
    # シェル機能
    #
    def dir(self):
        """ @method [ls]
        ディレクトリに含まれるファイルとサブディレクトリの一覧を返す。
        Returns:
            Set[Path]: (name, extension, modtime, size)
        """
        if not self.isdir():
            return [Path(self._path)]
        items = [Path(os.path.join(self._path,x)) for x in os.listdir(self._path)]
        return items
    
    def exec(self, app, params=None, shell=False):
        """ @method spirit
        ファイルを実行する。
        Params:
            params(Tuple): *コマンド引数文字列のタプル
            shell(Bool): *シェル上で実行する
        """
        if self.isdir():
            raise ValueError("このパスは実行できません")

        proc = popen_capture(params, shell=shell)
        for msg in proc:
            if msg.is_waiting_input():
                if not app.interruption_point(noexception=True):
                    msg.send_kill(proc)
                    app.post("warn", "実行中のプロセスを強制終了しました")
                    app.raise_interruption()
                continue
                #inp = spi.get_input()
                #if inp == 'q':
                #    msg.end_input(proc)
                #elif inp:
                #    msg.send_input(proc, inp)
                #else:
                #    msg.skip_input(proc)
            
            if msg.is_output():
                app.post("message", msg.text)
            
            if msg.is_finished():
                app.post("message-em", "プロセスはコード={}で終了しました".format(msg.returncode))
    
    #
    # 型の振る舞い
    #
    def __truediv__(self, right):
        """ パスの結合 """
        if isinstance(right, Path):
            r = right._path
        elif isinstance(right, str):
            r = right
        else:
            raise TypeError("right")

        return Path(os.path.join(self._path, r))
    
    def construct(self, s):
        return Path(s)
    
    def conversion_construct(self, context, v):
        return Path(str(v))
    
    def stringify(self):
        return self._path    


#
"""
def walk_path(dirpath, level):
    items = [(x,os.path.join(dirpath,x)) for x in os.listdir(dirpath)]
    for fname, fpath in items:
        # フィルタ
        if pattern is not None:
            if pattern == "|d" and not os.path.isdir(fpath):
                continue
            elif pattern == "|f" and not os.path.isfile(fpath):
                continue
            elif not re.search(pattern, fname):
                continue

        paths.append(FilePath(fpath))
        
        if recurse>level and os.path.isdir(fpath):
            walk(fpath, level+1)
"""

# desktop location ls filter "@ hasext txt"

#
#
#
class TextFile(Path):
    """ @type
    テキストファイルのパス。
    Typename: TextFile    
    """
    def __init__(self, p):
        super().__init__(p)

    def detect_encoding(self):
        """ @method
        文字エンコーディング形式を取得する。
        Returns:
            Str: 文字エンコーディングの名前
        """
        encoding = detect_text_encoding(self._path)
        return encoding

    #
    def construct(self, s):
        return TextFile(s)
    
    def conversion_construct(self, context, v):
        return TextFile(str(v))
    
    def stringify(self):
        return self._path    

def get_text_content(app, target, encoding=None, head=0, tail=0, all=False):
    if all:
        head, tail = 0, 0
    pth = app.abspath(target)

    app.message-em("ファイル名：[%1%]", embed=[
        app.hyperlink.msg(pth)
    ])

    if encoding is None:
        # 自動検出
        encoding = detect_text_encoding(pth)

    app.message-em("エンコーディング：%1%", embed=[
        app.message.msg(encoding or "unknown")
    ])
    app.message-em("--------------------")

    tails = []
    with open(pth, "r", encoding=encoding) as fi:
        for i, line in enumerate(fi):
            if head and i >= head:
                break
            if tail:
                tails.append(line)
            else:
                app.message(line, nobreak=True)

        if tail and tails:
            for l in tails[-tail:]:
                app.message(l, nobreak=True)
    
    app.message-em("\n--------------------")

#
def detect_text_encoding(fpath):
    from machaon.platforms import current
    
    encset = ["utf-8", "utf_8_sig", "utf-16", "shift-jis"]
    if current.default_encoding not in encset:
        encset.insert(0, current.default_encoding)

    cands = set(encset)
    size = 256
    badterminated = False
    with open(fpath, "rb") as fi:
        heads = fi.read(size)

        for i in range(4):
            if i>0:
                bit = fi.read(1)
                if bit is None:
                    break
                heads += bit

            for encoding in encset:
                if encoding not in cands:
                    continue
                try:
                    heads.decode(encoding)
                except UnicodeDecodeError as e:
                    if (size+i - e.end) < 4:
                        badterminated = True
                        continue
                    cands.remove(encoding)
                        
            if not cands:
                return None
            
            if not badterminated:
                break

    return next(x for x in encset if x in cands)

#
#
#
def get_binary_content(app, target, size=128, width=16):
    app.message-em("ファイル名：[%1%]", embed=[
        app.hyperlink.msg(target)
    ])
    app.message-em("--------------------")
    with open(app.abspath(target), "rb") as fi:
        bits = fi.read(size)
    j = 0
    app.message-em("        |" + " ".join(["{:0>2X}".format(x) for x in range(width)]))
    for i, bit in enumerate(bits):
        if i % width == 0:
            app.message-em("00000{:02X}0|".format(j), nobreak=True)
        app.message("{:02X} ".format(bit), nobreak=True)
        if i % width == width-1:
            app.message("")
            j += 1
    app.message-em("\n--------------------")

#
#
#
def unzip(app, path, out=None, win=False):
    path = app.abspath(path)

    from zipfile import ZipFile
    if out is None:
        out, _ = os.path.splitext(path)
    if not os.path.isdir(out):
        os.mkdir(out)

    memberdict = defaultdict(dict)
    with ZipFile(path) as zf:
        for membername in zf.namelist():
            zf.extract(membername, out)
            node = memberdict
            # リネーム用にパスをツリー構造で記録する
            if win:
                for part in membername.split("/"):
                    if not part:
                        continue
                    if part not in node:
                        node[part] = {}
                    node = node[part]
    
    # 文字化けしたファイル名をすべてリネーム
    if win:
        stack = [(out, memberdict, x) for x in memberdict.keys()]
        while stack:
            cd, d, memberpath = stack.pop()
            oldpath = os.path.join(cd, memberpath)
            newpath = os.path.join(cd, memberpath.encode("cp437").decode("utf-8"))
            os.rename(oldpath, newpath)
            stack.extend([(newpath, d[memberpath], x) for x in d[memberpath]])



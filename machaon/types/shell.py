import os
import shutil
import stat
import re
import time
import datetime
import math
import sys
from collections import defaultdict

from typing import Optional

from machaon.shellpopen import popen_capture
from machaon.types.fundamental import NotFound

#
#
#
def shell_platform():
    """
    プラットフォームごとの実装を呼び出す
    """
    module = None 
    system = sys.platform
    if system == "win32":
        import machaon.types.shellplatform.win32 as module
    elif system == "darwin":
        import machaon.types.shellplatform.darwin as module
    else:
        raise ValueError("Unsupported system: "+system)
    return module

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
    
    def get(self):
        return self._path
    
    @classmethod
    def from_location_name(cls, name):
        p = shell_platform().location_name_to_path(*name.split(":",maxsplit=1))
        if p is None:
            raise ValueError("不明なフォルダ名："+name)
        return cls(p)
    
    @property
    def stat(self):
        if self._stat is None:
            self._stat = os.stat(self._path)
        return self._stat

    #
    # 要素を調査する
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
    
    def filetype(self):
        """ @method
        ファイルタイプ名（フォルダまたは拡張子）
        Returns:
            Str:
        """
        if self.isdir():
            return "<DIR>"
        else:
            return self.extension().lstrip(".")
    
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
    
    def isfile(self):
        """ @method
        ファイルのパスかどうか
        Returns:
            Bool:
        """
        return os.path.isfile(self._path)
    
    def exists(self):
        """ @method
        ファイル・フォルダとして存在するか
        Returns:
            Bool:
        """
        return os.path.exists(self._path)
    
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
    # パス操作
    #
    def dir(self):
        """ @method
        ファイルならそのディレクトリを返す。ディレクトリはそのまま。
        Returns:
            Path:
        """
        if self.isfile():
            return self.up()
        return self

    def up(self):
        """ @method
        一つ上のディレクトリを返す。
        Returns:
            Path:
        """
        up, _basename = os.path.split(self._path)
        return Path(up)
    
    def append(self, path):
        """ @method
        パスを付け足す。
        Params:
            path(Path):
        Returns:
            Path:
        """
        p = os.path.join(self._path, path._path)
        return Path(p)
    
    def with_name(self, name):
        """ @method
        ファイル・ディレクトリ名だけ変更する。
        Params:
            name(str):
        Returns:
            Path:
        """
        up, _basename = os.path.split(self._path)
        return Path(os.path.join(up, name))
    
    def with_ext(self, extension):
        """ @method
        拡張子だけ変更する。
        Params:
            extension(str):
        Returns:
            Path:
        """
        up, _ext = os.path.splitext(self._path)
        if not extension.startswith("."):
            extension = "." + extension
        return Path(up + extension)
    
    def with_basename_format(self, format, *args):
        """ 書式に基づいて名前のみ変更する。（内部利用）"""
        head, basename = os.path.split(self._path)
        filename, fext = os.path.splitext(basename)
        newpath = os.path.join(head, format.format(filename, *args) + fext)
        return Path(newpath)

    #
    # シェル機能
    #
    def listdir(self):
        """ @method [ls]
        ディレクトリに含まれるファイルとサブディレクトリの一覧を返す。
        Returns:
            Sheet[Path]: (name, filetype, modtime, size)
        """
        if not self.isdir():
            return [Path(self._path)]
        items = [Path(os.path.join(self._path,x)) for x in os.listdir(self._path)]
        return items
    
    def dialog(self):
        """ @method [dlg]
        ファイル・フォルダダイアログを開く。
        Returns:
            PathDialog:
        """
        return self
    
    def search(self, context, app, predicate, depth=3):
        """ @method task context
        ファイルを再帰的に検索する。
        Params:
            predicate(Function): 述語関数
            depth(int): 探索する階層の限界
        Returns:
            Sheet[Path]: (name, extension, modtime, size)
        """
        basedir = self.dir().path()
        for dirpath, dirname, filenames in os.walk(basedir):
            for filename in filenames:
                filepath = os.path.join(basedir, dirpath, filename)
                path = context.new_object(filepath, type="Path")
                if predicate.run_function(path, context).is_truth():
                    return path
        raise NotFound()
    
    def run(self, app, params=None):
        """ @task
        ファイルを実行し、終わるまで待つ。
        Params:
            params(Tuple): *コマンド引数文字列のタプル
        """
        if self.isdir():
            raise ValueError("ディレクトリは実行できません")

        pa = []
        pa.append(self._path)
        pa.extend(params or [])

        proc = popen_capture(pa)
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
    
    def start(self, operation=None):
        """ @method
        ファイル・フォルダをデフォルトの方法で開く。
        Params:
            operation(str): *動作のカテゴリ。[open|print|edit|explore|find|...]
        """
        shell_platform().start_file(self._path, operation)
    
    def explore(self):
        """ @method
        ファイル・フォルダをエクスプローラで開く。
        """
        p = self.dir()
        shell_platform().start_file(p._path, "explore")

    def print(self):
        """ @method
        ファイル・フォルダを印刷する。
        """
        if self.isdir():
            raise ValueError("Unsupported")
        shell_platform().start_file(self._path, "print")
    
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
#
#
class PathDialog:
    """ @type
    パスを選択するダイアログ。
    """
    def __init__(self, p):
        self.p = p
        self._filter = None
    
    def file(self, app):
        """ @method spirit
        一つのファイルを選択する。
        Returns:
            Path:
        """
        p = app.open_pathdialog("f", self.p.dir(), filters=self._filter)
        return p

    def files(self, app):
        """ @method spirit
        複数のファイルを選択する。
        Returns:
            Tuple:
        """
        p = app.open_pathdialog("f", self.p.dir(), filters=self._filter, multiple=True)
        return p

    def dir(self, app):
        """ @method spirit
        一つのディレクトリを選択する。
        Returns:
            Path:
        """
        p = app.open_pathdialog("d", self.p.dir())
        return p

    def dirs(self, app):
        """ @method spirit
        複数のディレクトリを選択する。
        Returns:
            Tuple:
        """
        p = app.open_pathdialog("d", self.p.dir(), multiple=True)
        return p
    
    def save(self, app):
        """ @method spirit
        保存するファイルの場所を選択する。
        Returns:
            Path:
        """
        p = app.open_pathdialog("s", self.p.dir())
        return p

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
        self._enc = None

    def detect_encoding(self):
        """ @method
        文字エンコーディング形式を推定する。
        Returns:
            Str: 文字エンコーディングの名前
        """
        if self._enc is not None:
            return self._enc
        encoding = detect_text_encoding(self._path)
        self._enc = encoding
        return encoding

    #
    def construct(self, s):
        return TextFile(s)
    
    def conversion_construct(self, context, v):
        p = TextFile(str(v))
        if not p.isfile():
            raise ValueError("ファイルではありません")
        return p
    
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



import os
import shutil
import stat
import re
import time
import math
from collections import defaultdict

from typing import Optional

from machaon.commands.shellpopen import popen_capture

#
#
#
def execprocess(spi, target, split=False, shell=False):
    cmds = []

    commandhead, _, commandstr = [x.strip() for x in target.partition(' ')]
    if not commandhead:
        return

    cpath = spi.abspath(commandhead)
    if os.path.isfile(cpath):
        cmds.append(cpath)
    else:
        cmds.append(commandhead)

    if commandstr:
        if split:
            cmds.extend(commandstr.split())
        else:
            cmds.append(commandstr)
    
    proc = popen_capture(cmds, shell=shell)
    for msg in proc:
        if msg.is_waiting_input():
            if not spi.interruption_point(noexception=True):
                msg.send_kill(proc)
                spi.warn("実行中のプロセスを強制終了しました")
                spi.raise_interruption()
            continue
            #inp = spi.get_input()
            #if inp == 'q':
            #    msg.end_input(proc)
            #elif inp:
            #    msg.send_input(proc, inp)
            #else:
            #    msg.skip_input(proc)
        
        if msg.is_output():
            spi.message(msg.text)
        
        if msg.is_finished():
            spi.message_em("プロセスはコード={}で終了しました".format(msg.returncode))
        
#
#
#
def currentdir(spi, path=None, silent=False):
    if path is not None:
        path = spi.abspath(path)
        if spi.change_current_dir(path):
            if not silent:
                spi.message("作業ディレクトリを変更しました")
                filelist(spi)
        else:
            spi.error("'{}'は有効なパスではありません".format(path))


#
#
#
class FilePath():
    def __init__(self, path):
        self._path = path
        self._isdir = None
        self._stat = None
    
    @property
    def isdir(self):
        if self._isdir is None:
            self._isdir = os.path.isdir(self._path)
        return self._isdir
    
    @property
    def stat(self):
        if self._stat is None:
            self._stat = os.stat(self._path)
        return self._stat

    #
    def path(self):
        return self._path

    def name(self):
        return os.path.basename(self._path)
    
    def nxname(self):
        n, _ext = os.path.splitext(os.path.basename(self._path))
        return n
    
    def ftype(self):
        if self.isdir:
            return "DIR"
        else:
            _, fext = os.path.splitext(self._path)
            if fext!="":
                fext = fext[1:].upper()
            return fext
    
    def modtime(self):
        mtime = time.localtime(os.path.getmtime(self._path))
        wkday = {6:"日",0:"月",1:"火",2:"水",3:"木",4:"金",5:"土"}.get(mtime[6],"？")
        ftime = "{:02}/{:02}/{:02}（{}）{:02}:{:02}.{:02}".format(
            mtime[0] % 100, mtime[1], mtime[2], wkday, 
            mtime[3], mtime[4], mtime[5])
        return ftime
    
    def size(self):
        if self.isdir:
            return None
        else:
            size_bytes = os.path.getsize(self._path)
            if size_bytes == 0:
                return "0B"
            i = int(math.floor(math.log(size_bytes, 1024)))
            p = math.pow(1024, i)
            s = round(size_bytes / p, 2)
            size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
            return "{:.0F} {}".format(s, size_name[i])
    
    def mode(self):
        return stat.filemode(self.stat.st_mode)
    
    @classmethod
    def describe_object(cls, describe):
        describe(
            typename="filepath",
            description="",
        )["member name n"](
            name="ファイル名"
        )["member nxname nx"](
            name="拡張子無しのファイル名"
        )["member path p"](
            name="パス"
        )["member ftype t"](
            name="タイプ"
        )["member modtime"](
            name="更新日時",
            type="datetime"
        )["member size"](
            name="サイズ"
        )["member mode"](
            name="ファイルモード"
        )["alias long"](
            "mode ftype modtime size name"
        )["alias short"](
            "ftype name"
        )["alias link"](
            "path",
        )


#
def filelist(app, pattern=None, long=False, howsort=None, recurse=1, silent=False):
    # パスを集める
    paths = []
    def walk(dirpath, level):
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

    cd = app.get_current_dir()
    walk(cd, 1)

    if not silent:
        app.message(cd+"\n")

    view = "/table" if long else "/wide"
    app.push_object_table(paths, view)

#
#
#
def get_text_content(app, target, encoding=None, head=0, tail=0, all=False):
    if all:
        head, tail = 0, 0
    pth = app.abspath(target)

    app.message_em("ファイル名：[%1%]", embed=[
        app.hyperlink.msg(pth)
    ])

    if encoding is None:
        # 自動検出
        encoding = detect_text_encoding(pth)

    app.message_em("エンコーディング：%1%", embed=[
        app.message.msg(encoding or "unknown")
    ])
    app.message_em("--------------------")

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
    
    app.message_em("\n--------------------")

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
    app.message_em("ファイル名：[%1%]", embed=[
        app.hyperlink.msg(target)
    ])
    app.message_em("--------------------")
    with open(app.abspath(target), "rb") as fi:
        bits = fi.read(size)
    j = 0
    app.message_em("        |" + " ".join(["{:0>2X}".format(x) for x in range(width)]))
    for i, bit in enumerate(bits):
        if i % width == 0:
            app.message_em("00000{:02X}0|".format(j), nobreak=True)
        app.message("{:02X} ".format(bit), nobreak=True)
        if i % width == width-1:
            app.message("")
            j += 1
    app.message_em("\n--------------------")

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



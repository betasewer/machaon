import os
import shutil
import re
import time
import subprocess

from typing import Optional

from machaon.cui import reencode

#
#
#
def execprocess(spi, commandhead, commandstr):
    cmds = []

    cpath = spi.abspath(commandhead)
    if os.path.isfile(cpath):
        cmds.append(cpath)
    else:
        cmds.append(commandhead)
    
    if commandstr:
        cmds.append(commandstr)
    
    import machaon.platforms
    shell_encoding = machaon.platforms.current.shell_ui().encoding

    proc = subprocess.Popen(cmds, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    out = None
    err = None
    while True:
        if not spi.interruption_point(noexception=True):
            proc.kill()
            spi.warn("実行中のプロセスを強制終了しました")
            spi.raise_interruption()
        
        try:
            out, err = proc.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            continue
        
        break

    if err:
        e = err.decode(shell_encoding)
        for line in e.splitlines():
            spi.error(line)
    if out:
        o = out.decode(shell_encoding)
        for line in o.splitlines():
            spi.message(line)
    

#
#
#
def currentdir(spi, path=None, silent=False):
    if path is not None:
        path = spi.abspath(path)
        if spi.change_current_dir(path):
            spi.message("現在の作業ディレクトリ：" + spi.get_current_dir())
            if not silent:
                filelist(spi)
        else:
            spi.error("'{}'は有効なパスではありません".format(path))

#
#
#
def filelist(app, pattern=None, long=False, howsort=None, presetpattern=None, recurse=1):
    if howsort == "t":
        def sorter(path):
            d = 1 if os.path.isdir(path) else 2
            t = os.path.getmtime(path)
            return (d, -t)
    else:
        def sorter(path):
            return 1 if os.path.isdir(path) else 2

    if presetpattern is not None: 
        pattern = presetpattern
    
    paths = []
    def walk(dirpath, level):
        items = sorted([(x,os.path.join(dirpath,x)) for x in os.listdir(dirpath)], key=lambda x: sorter(x[1]))
        for fname, fpath in items:
            if pattern is None or re.search(pattern, fname):
                paths.append(fpath)
            if recurse>level and os.path.isdir(fpath):
                walk(fpath, level+1)

    cd = app.get_current_dir()
    walk(cd, 1)

    app.message_em("ディレクトリ：%1%\n", embed=[
        app.hyperlink.msg(cd)
    ])
    if long:
        app.message("種類  変更日時                    サイズ ファイル名")
        app.message("-------------------------------------------------------")

    for fpath in paths:
        app.interruption_point()

        ftext = os.path.normpath(os.path.relpath(fpath, cd))
        isdir = os.path.isdir(fpath)
        if isdir and not ftext.endswith(os.path.sep):
            ftext += os.path.sep

        if long:
            if isdir:
                fext = "ﾌｫﾙﾀﾞ"
            else:
                _, fext = os.path.splitext(fpath)
                if fext!="":
                    fext = fext[1:].upper()

            mtime = time.localtime(os.path.getmtime(fpath))
            wkday = {6:"日",0:"月",1:"火",2:"水",3:"木",4:"金",5:"土"}.get(mtime[6],"？")
            ftime = "{:02}/{:02}/{:02}（{}）{:02}:{:02}.{:02}".format(
                mtime[0] % 100, mtime[1], mtime[2], wkday, 
                mtime[3], mtime[4], mtime[5])

            if isdir:
                fsize = "---"
            else:
                fsize = os.path.getsize(fpath)

            app.message("{:<5} {}  {:>8} %1%".format(fext, ftime, fsize), embed=[
                app.hyperlink.msg(ftext, link=fpath)
            ])
        else:
            app.hyperlink(ftext, link=fpath)
            
    app.message("")

#
#
#
def get_text_content(app, target, encoding=None, head=0, tail=0, all=False):
    if all:
        head, tail = 0, 0
    pth = app.abspath(target)

    if encoding is None:
        # 自動検出
        encoding = detect_text_encoding(pth)

    app.message_em("ファイル名：[%1%](%2%)", embed=[
        app.hyperlink.msg(pth),
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
def calculator(app, expression, library):
    expression = expression.strip()
    if not expression:
        raise TypeError("expression needed")

    glo = {}
    import math
    glo["math"] = math
    if library:
        import importlib
        for libname in library:
            glo[libname] = importlib.import_module(libname)

    val = eval(expression, glo, {})
    app.message_em(val)


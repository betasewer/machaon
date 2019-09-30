import os
import shutil
import re
import time

from machaon.command import describe_command
from machaon.shell import reencode

#
#
#
def filelist(app, pattern=None, long=False, howsort=None, presetpattern=None):
    if howsort == "t":
        def sorter(path):
            d = 1 if os.path.isdir(path) else 2
            t = os.path.getmtime(path)
            return (d, -t)
    else:
        def sorter(path):
            return 1 if os.path.isdir(path) else 2

    dirpath = app.get_current_dir()
    app.message_em("ディレクトリ：%1%", embed=[
        app.msg(dirpath, "hyperlink")
    ])

    app.message("")
    if long:
        app.message("種類  変更日時                    サイズ ファイル名")
        app.message("-------------------------------------------------------")

    if presetpattern is not None: pattern = presetpattern
    paths = []
    for fname in os.listdir(dirpath):
        if pattern is None or re.search(pattern, fname):
            paths.append(os.path.join(dirpath, fname))

    for fpath in sorted(paths, key=sorter):
        _, ftext = os.path.split(fpath)
        isdir = os.path.isdir(fpath)
        if isdir and not ftext.endswith("/"):
            ftext += "/"

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
                app.msg(ftext, "hyperlink", link=fpath)
            ])
        else:
            app.hyperlink(ftext, link=fpath)
            
    app.message("")

#
#
#
def get_content(app, target, encoding="utf-8", binary=False):
    app.message_em("ファイル名：[%1%]", embed=[
        app.msg(target, "hyperlink")
    ])
    app.message_em("--------------------")
    if binary:
        readsize = 128
        with open(app.abspath(target), "rb") as fi:
            bits = fi.read(readsize)
        j = 0
        app.message_em("        |" + " ".join(["{:0>2X}".format(x) for x in range(16)]))
        for i, bit in enumerate(bits):
            if i % 16 == 0:
                app.message_em("00000{:02X}0|".format(j), nobreak=True)
            app.message("{:02X} ".format(bit), nobreak=True)
            if i % 16 == 15:
                app.message("")
                j += 1
    elif encoding:
        with open(app.abspath(target), "r", encoding=encoding) as fi:
            for line in fi:
                app.message(line, nobreak=True)
    app.message_em("--------------------")

#
# プリセットコマンドの定義
#
definitions = [
    (filelist, ('dir', 'ls'), 
        describe_command(
            description="作業ディレクトリにあるフォルダとファイルの一覧を表示します。", 
        )["target pattern"](
            help="表示するフォルダ・ファイルを絞り込む正規表現パターン（部分一致）",
            nargs="?"
        )["target -l --long"](
            const_option=True,
            help="詳しい情報を表示する"
        )["target -t --time"](
            const_option="t",
            help="更新日時で降順に並び替える",
        )["target -o --opc"](
            const_option=r"\.(docx|doc|xlsx|xls|pptx|ppt)$",
            help="OPCパッケージのみ表示する",
            dest="presetpattern"
        ),
        True, # bindapp
    ),
    (get_content, ('type', 'touch'),
        describe_command(
            description="ファイルの内容を表示します。", 
        )["target target"](
            help="表示するファイル",
        )["target -e --encoding"](
            help="テキストエンコーディング [utf-8|utf-16|ascii|shift-jis]",
            default="utf-8"
        )["target -b --binary"](
            help="バイナリファイルとして開く",
            const_option=True,
        ),
        True, # bindapp
    )
]
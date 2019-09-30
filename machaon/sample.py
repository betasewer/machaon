#!/usr/bin/env python3
# coding: utf-8
import unicodedata
from machaon.app import AppMessage

#
# Sample Processors
#
class TestProcess():
    def __init__(self, app):
        self.app = app
    
    def init_process(self):
        self.app.message("文字列を倍増するプロセスを開始.")
    
    def process_target(self):
        target = self.app.get_input("文字列を入力してください...")
        templ = self.app.get_input("倍数を入力してください...")
        if not templ.isdigit():
            self.app.error("数値が必要です")
        else:
            self.app.message_em("\n".join([target for _ in range(int(templ))]))   
            
    def exit_process(self):
        self.app.message("文字列を倍増するプロセスを終了.")
    
    @classmethod
    def describe(cls, cmd):
        cmd.describe(
            description = "文字列を倍増します。"
        )

#
class LinkProcess():
    def __init__(self, app):
        self.app = app
    
    def init_process(self):
        self.app.message("リンク作成を開始.")
    
    def process_target(self, target, url):
        self.app.hyperlink(target, link=url)

    def exit_process(self):
        self.app.message("リンク作成を終了.")
        
    @classmethod
    def describe(cls, cmd):
        cmd.describe(
            description = "リンクを貼ります。"
        )["target target"](
            help = "リンクの文字列"
        )["target url"](
            help = "リンク先URL"
        )
    
#
class ColorProcess():
    def __init__(self, app):
        self.app = app
    
    def init_process(self):
        pass

    def process_target(self, text):
        self.app.message(text)
        self.app.message_em("【強調】" + text)
        self.app.print_message(AppMessage("【入力】" + text, "input"))
        self.app.print_message(AppMessage("【リンク】" + text, "hyperlink"))
        self.app.warn("【注意】" + text)
        self.app.error("【エラー発生】" + text)
    
    def exit_process(self):
        pass
    
    @classmethod
    def describe(cls, cmd):
        cmd.describe(
            description = "文字色のサンプルを表示します。"
        )["target --text"](
            default="文字色のサンプルです。"
        )

#
def char_detail_line(code, char=None):
    if char is None and code < 0x110000:
        char = chr(code)
    if char is not None:
        name = unicodedata.name(char, None)
        cat = unicodedata.category(char)

    if char is None:
        disp = "[not a character]"
    elif cat.startswith("C") or cat.startswith("Z"):
        if cat == "Cn":
            name = "[not a character]"
        else:
            name = "[{} control character]".format(cat)
        disp = name
    else:
        disp = char + "  " + name
    return " {:04X} {}".format(code, disp)

#
def launch_sample_app(default_choice=None):
    import sys
    import argparse
    from machaon.app import App
    from machaon.command import describe_command

    desc = 'machaon sample application'
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--cui", action="store_const", const="cui", dest="apptype")
    p.add_argument("--tk", action="store_const", const="tk", dest="apptype")
    args = p.parse_args()
    
    title = "sample app"
    apptype = args.apptype or default_choice
    if apptype is None or apptype == "cui":
        from machaon.shell import WinShellUI
        app = App(title, WinShellUI())
        app.add_syscommands(exclude=("interrupt",))
    elif apptype == "tk":
        from machaon.tk import tkLauncherUI
        app = App(title, tkLauncherUI())
        app.add_syscommands(exclude=("interrupt", "cls", "exit"))
    else:
        p.print_help()
        sys.exit()

    def encode_unicodes(text=""):
        app.message("input:")
        for char in text:
            line = char_detail_line(ord(char), char)
            app.message(line)
            
    def decode_unicodes(codebits=""):
        app.message("input:")
        for codebit in codebits.split():
            try:        
                code = int(codebit, 16)
            except ValueError:
                continue
            line = char_detail_line(code)
            app.message(line)

    # コマンドの設定
    app.add_command(TestProcess, ("spam",))
    app.add_command(ColorProcess, ("texts",))
    app.add_command(LinkProcess, ("link",))

    app.add_command(encode_unicodes, ("unienc",), 
        describe_command(
            description="文字を入力 -> コードにする"
        )["target characters"](
            help="コードにしたい文字列"
        )
    )
    app.add_command(decode_unicodes, ("unidec",),
        describe_command(
            description="コードを入力 -> 文字にする"
        )["target characters"](
            help="文字列にしたいコード"
        )
    )

    #app.launcher.command(app.ui.show_history, ("history",), desc="入力履歴を表示します。")
    #app.launcher.command(app.ui.show_hyperlink_database, ("hyperlinks",), hidden=True, desc="内部のハイパーリンクデータベースを表示します。")
    app.run()


#
#
#
if __name__ == "__main__":
    launch_sample_app()
#!/usr/bin/env python3
# coding: utf-8
import unicodedata
from machaon.processor import Processor
from machaon.app import AppMessage

#
# Sample Processors
#
class TestProcess(Processor):
    __desc__ = "文字列を倍増します。"
    
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
    def init_argparser(cls, cmd):
        pass

#
class LinkProcess(Processor):
    __desc__ = "リンクを貼ります。"
    
    def init_process(self):
        self.app.message("リンク作成を開始.")
    
    def process_target(self, target, url):
        self.app.hyperlink(target, link=url)

    def exit_process(self):
        self.app.message("リンク作成を終了.")
        
    @classmethod
    def init_argparser(cls, cmd):
        cmd.target_arg("target")
        cmd.target_arg("url")
    
#
class ColorProcess(Processor):
    __desc__ = "文字色のサンプルを表示します。"
    def process_target(self, text):
        self.app.message(text)
        self.app.message_em(text)
        self.app.print_message(AppMessage(text, "input"))
        self.app.print_message(AppMessage(text, "hyper"))
        self.app.warn(text)
        self.app.error(text)
    
    @classmethod
    def init_argparser(cls, cmd):
        cmd.target_arg("--text", default="文字色のサンプルです。")
  

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
        app.launcher.syscommands(("interrupt", "cls", "cd", "help", "exit"))
    elif apptype == "tk":
        from machaon.tk import tkLauncherUI
        app = App(title, tkLauncherUI())
        app.launcher.syscommands(("interrupt", "cd", "help", "exit"))
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
    app.launcher.command(TestProcess, ("spam",))
    app.launcher.command(encode_unicodes, ("unienc",), desc="文字を入力 -> コードにする")
    app.launcher.command(decode_unicodes, ("unidec",), desc="コードを入力 -> 文字にする")
    app.launcher.command(ColorProcess, ("texts",))
    app.launcher.command(LinkProcess, ("link",))
    #app.launcher.command(app.ui.show_history, ("history",), desc="入力履歴を表示します。")
    #app.launcher.command(app.ui.show_hyperlink_database, ("hyperlinks",), hidden=True, desc="内部のハイパーリンクデータベースを表示します。")
    app.run()


#
#
#
if __name__ == "__main__":
    launch_sample_app()
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
def char_detail_line(char):
    code = ord(char)
    name = unicodedata.name(char, None)
    cat = unicodedata.category(char)
    if cat.startswith("C") or cat.startswith("Z"):
        if cat == "Cn":
            name = "[not a character]"
        else:
            name = "[{} control character]".format(cat)
        disp = name
    else:
        disp = char + "  " + name
    return " {:04X} {}".format(code, disp)
    
def encode_unicodes(text=""):
    app.message("input:")
    for char in text:
        line = char_detail_line(char)
        app.print_message(AppMessage(line, "input"))
        
def decode_unicodes(codebits=""):
    app.message("input:")
    for codebit in codebits.split():
        try:        
            code = int(codebit, 16)
        except ValueError:
            continue
        char = chr(code)
        line = char_detail_line(char)
        app.print_message(AppMessage(line, "input"))

#
#
#
if __name__ == "__main__":
    import sys
    import argparse
    desc = 'machaon sample application'
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--cui", action="store_const", const="cui", dest="apptype")
    p.add_argument("--tk", action="store_const", const="tk", dest="apptype")
    args = p.parse_args()
    
    title = "sample app"
    apptype = args.apptype
    if apptype is None or apptype == "cui":
        from machaon.shell import BasicShellApp, WinShellUI
        app = BasicShellApp(title, WinShellUI)
    elif apptype == "tk":
        from machaon.tk import tkApp
        app = tkApp(title)
    else:
        p.print_help()
        sys.exit()
    
    # コマンドの設定
    #app.launcher.command(app.ui.show_history, ("history",), desc="入力履歴を表示します。")
    app.launcher.command(TestProcess, ("spam",))
    app.launcher.command(encode_unicodes, ("unienc",), desc="文字を入力 -> コードにする")
    app.launcher.command(decode_unicodes, ("unidec",), desc="コードを入力 -> 文字にする")
    app.launcher.command(ColorProcess, ("texts",))
    app.launcher.command(LinkProcess, ("link",))
    #app.launcher.command(app.ui.show_hyperlink_database, ("hyperlinks",), hidden=True, desc="内部のハイパーリンクデータベースを表示します。")
    app.run()
    

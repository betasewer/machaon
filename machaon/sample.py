#!/usr/bin/env python3
# coding: utf-8
import unicodedata
from machaon.app import AppMessage
from machaon.command import describe_command, describe_command_package

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
    
def encode_unicodes(app, text=""):
    app.message("input:")
    for char in text:
        line = char_detail_line(ord(char), char)
        app.message(line)

def decode_unicodes(app, codebits=""):
    app.message("input:")
    for codebit in codebits.split():
        try:        
            code = int(codebit, 16)
        except ValueError:
            continue
        line = char_detail_line(code)
        app.message(line)

#
spec_commands = describe_command_package(
        description="様々なテストコマンドです。"
    )["spam"](
        process=TestProcess
    )["texts"](
        process=ColorProcess
    )["link"](
        process=LinkProcess
    )["unienc"](
        describe_command(
            process=encode_unicodes,
            description="文字を入力 -> コードにする"
        )["target characters"](
            help="コードにしたい文字列"
        )
    )["unidec"](
        describe_command(
            process=decode_unicodes,
            description="コードを入力 -> 文字にする"
        )["target characters"](
            help="文字列にしたいコード"
        )
    )
    


#
def launch_sample_app(default_choice=None):
    import sys
    import argparse
    import machaon.starter
    from machaon.command import describe_command

    desc = 'machaon sample application'
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--cui", action="store_const", const="cui", dest="apptype")
    p.add_argument("--tk", action="store_const", const="tk", dest="apptype")
    args = p.parse_args()
    
    apptype = args.apptype or default_choice
    if apptype is None or apptype == "cui":
        boo = machaon.starter.ShellStarter()
    elif apptype == "tk":
        boo = machaon.starter.TkStarter(title="machaon sample app", geometry=(900,500))
    else:
        p.print_help()
        sys.exit()

    boo.install_commands("", spec_commands)

    import machaon.shell_command
    boo.install_commands("", machaon.shell_command.commands)

    boo.install_syscommands()

    boo.go()


#
#
#
if __name__ == "__main__":
    launch_sample_app("tk")
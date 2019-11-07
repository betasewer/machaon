#!/usr/bin/env python3
# coding: utf-8

from machaon.app import ExitApp
from machaon.command import describe_command, describe_command_package
from machaon.cui import test_yesno, composit_text


#
# アプリ基本コマンド
#
#
def command_syntax(app, command_string):
    results = app.parse_possible_commands(command_string)
    if not results:
        app.message("[有効なコマンドではありません]")
    else:
        for process, _spirit, result in results:
            app.message(process.get_prog()+" "+result.get_expanded_command())

# 
def command_interrupt(app):    
    if not app.is_process_running():
        app.message("実行中のプロセスはありません")
        return
    app.message("プロセスを中断します")
    app.interrupt_process()
  
#  
def command_cls(app):
    app.reset_screen()

#
def command_cd(app, path=None):
    if path is not None:
        path = app.abspath(path)
        app.change_current_dir(path)
    app.message("現在の作業ディレクトリ：" + app.get_current_dir())

#
def command_help(app, command_name=None):
    app.message("<< コマンド一覧 >>")
    app.message("各コマンドの詳細は command --help で")
    app.message("")
    
    for cmdset in app.get_command_sets():
        pfx = cmdset.get_prefixes()
        msgs = []

        for entry in cmdset.display_entries():
            heads = []
            for i, k in enumerate(entry.keywords):
                if i == 0 and pfx:
                    k = "{}.{}".format(pfx[0], k)
                elif pfx:
                    k = "{}{}".format(pfx[1 if len(pfx)>=1 else 0], k)
                heads.append(k)

            if command_name and not any(head.startswith(command_name) for head in heads):
                continue

            for h in heads:
                msgs.append(app.hyperlink.msg(h, nobreak=True))
                msgs.append(app.message.msg(", ", nobreak=True))
            msgs.pop()
            
            for l in composit_text(entry.get_description(), 100, indent=4, first_indent=6).splitlines():
                msgs.append(app.message.msg(l))
        
        if not msgs:
            continue

        if pfx:
            msg = app.warn.msg(pfx[0])
            app.message_em("[%1%] ", embed=[msg], nobreak=True)
        app.message_em(cmdset.get_description())
        app.message("---------------------------")
        for m in msgs:
            app.print_message(m)
        app.message("")
    
    app.message("")

#
def command_exit(app, ask=False):
    if ask:
        if not app.ask_yesno("終了しますか？ (Y/N)"):
            return
    return ExitApp
    
#
# エントリ
#
def app_commands():
    return describe_command_package(
        description="ターミナルを操作するコマンドです。",
    )["syntax"](
        describe_command(
            command_syntax,
            description="コマンド文字列を解析し、可能な解釈をすべて示します。"
        )["target command_string"](
            help="コマンド文字列",
            remainder=True
        )
    )["interrupt it"](
        describe_command(
            command_interrupt,
            description="現在実行中のプロセスを中断します。"
        )
    )["cls"](
        describe_command(
            command_cls,
            description="画面をクリアします。"
        )
    )["cd"](
        describe_command(
            command_cd,
            description="作業ディレクトリを変更します。", 
        )["target path"](
            nargs="?",
            help="移動先のパス"
        ),
    )["help h"](
        describe_command(
            command_help,      
            description="ヘルプを表示します。",
        )["target command_name"](
            nargs="?",
            help="ヘルプを見るコマンド"
        ),
    )["exit"](
        describe_command(
            command_exit,
            description="終了します。",
        )["target --ask -a"](
            const_option=True,            
            help="確認してから終了する"
        ),
    )
    
#
# クラスサンプル用コマンド
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
    
    def process_target(self, text):
        self.app.message(text)
        self.app.message_em("【強調】" + text)
        self.app.print_message(AppMessage("【入力】" + text, "input"))
        self.app.print_message(AppMessage("【リンク】" + text, "hyperlink"))
        self.app.warn("【注意】" + text)
        self.app.error("【エラー発生】" + text)
    
    @classmethod
    def describe(cls, cmd):
        cmd.describe(
            description = "文字色のサンプルを表示します。"
        )["target --text"](
            default="文字色のサンプルです。"
        )
   
#   
def sample_commands():
    return describe_command_package(
        description="テスト用コマンドです。"
    )["spam"](
        process=TestProcess
    )["texts"](
        process=ColorProcess
    )["link"](
        process=LinkProcess
    )
    
    

#!/usr/bin/env python3
# coding: utf-8

from machaon.command import describe_command, describe_command_package
from machaon.cui import test_yesno, composit_text


#
# アプリ基本コマンド
#
#
def command_syntax(spi, command_string):
    results = spi.get_app().parse_possible_commands(command_string)
    if not results:
        spi.message("[有効なコマンドではありません]")
    else:
        for process, _spirit, result in results:
            spi.message(process.get_prog()+" "+result.get_expanded_command())

# 
def command_interrupt(spi):  
    pass
"""  
    if not app.is_process_running():
        app.message("実行中のプロセスはありません")
        return
    app.message("プロセスを中断します")
    app.interrupt_process()
"""

#
def command_help(spi, command_name=None):
    spi.message("<< コマンド一覧 >>")
    spi.message("各コマンドの詳細は command --help で")
    spi.message("")
    
    for cmdset in spi.get_app().get_command_sets():
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
                msgs.append(spi.hyperlink.msg(h, nobreak=True))
                msgs.append(spi.message.msg(", ", nobreak=True))
            msgs.pop()
            
            for l in composit_text(entry.get_description(), 100, indent=4, first_indent=6).splitlines():
                msgs.append(spi.message.msg(l))
        
        if not msgs:
            continue

        if pfx:
            msg = spi.warn.msg(pfx[0])
            spi.message_em("[%1%] ", embed=[msg], nobreak=True)
        spi.message_em(cmdset.get_description())
        spi.message("---------------------------")
        for m in msgs:
            spi.post_message(m)
        spi.message("")
    
    spi.message("")

# 終了処理はAppRoot内にある
def command_exit(spi):
    raise NotImplementedError()
    
# テーマの選択
def command_ui_theme(app, themename=None, alt=(), show=False):
    from machaon.ui.theme import themebook
    if themename is None and not alt and not show:
        for name in themebook.keys():
            app.hyperlink(name)
        return

    root = app.get_app()
    if themename is not None:
        themenew = themebook.get(themename, None)
        if themenew is None:
            app.error("'{}'という名のテーマはありません".format(themename))
            return
        theme = themenew()
    else:
        theme = root.get_ui().get_theme()
    
    for altline in alt:
        cfgname, cfgval = altline.split("=")
        theme.setval(cfgname, cfgval)
    
    if show:
        for k, v in theme.config.items():
            app.message("{}={}".format(k,v))
    else:
        root.get_ui().apply_theme(theme)

# 立ち上げスクリプトのひな形を吐き出す
def command_bootstrap(app, tk=True):
    pass

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
        ),
    )["theme"](
        describe_command(
            command_ui_theme,
            description="アプリのテーマを変更します。"
        )["target themename"](
            help="テーマ名",
            nargs="?"
        )["target --alt"](
            help="設定項目を上書きする [config-name]=[config-value]",
            remainder=True,
            default=()
        )["target --show"](
            help="設定項目を表示する",
            const_option=True
        )
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
        self.app.custom_message("input", "【入力】" + text)
        self.app.custom_message("hyperlink", "【リンク】" + text)
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
        target=TestProcess
    )["texts"](
        target=ColorProcess
    )["link"](
        target=LinkProcess
    )
    
    

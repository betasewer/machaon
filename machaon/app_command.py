#!/usr/bin/env python3
# coding: utf-8

from machaon.app import ExitApp
from machaon.command import describe_command, describe_command_package
from machaon.cui import test_yesno, composit_text


#
# アプリ基本コマンド
#
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
def command_help(app, commandname=None):
    app.message("<< コマンド一覧 >>")
    app.message("各コマンドの詳細は command --help で")
    app.message("")
    
    for cmdset in app.launcher.command_sets():
        pfx = cmdset.get_prefixes()
        if pfx:
            msg = app.warn.msg(pfx[0])
            app.message_em("[%1%] ", embed=[msg], nobreak=True)
        app.message_em(cmdset.get_description())
        app.message("---------------------------")

        for entry in cmdset.display_entries():
            msgs = []
            for i, k in enumerate(entry.keywords):
                if i == 0 and pfx:
                    k = "{}.{}".format(pfx[0], k)
                elif pfx:
                    k = "{}{}".format(pfx[1 if len(pfx)>=1 else 0], k)
                msgs.append(app.hyperlink.msg(k, nobreak=True))
                msgs.append(app.message.msg(", ", nobreak=True))
            for m in msgs[:-1]:
                app.print_message(m)
            app.message("")

            for l in composit_text(entry.get_description(), 100, indent=4, first_indent=6).splitlines():
                app.message(l)
        
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
        )["target directory-path"](
            nargs="?",
            help="移動先のパス"
        ),
    )["help h"](
        describe_command(
            command_help,      
            description="ヘルプを表示します。",
        )["target command-name"](
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
# デバッグ用コマンド
#
# 
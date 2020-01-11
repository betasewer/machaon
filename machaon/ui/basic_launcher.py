#!/usr/bin/env python3
# coding: utf-8

import os
import datetime
import traceback
from typing import Tuple, Sequence, List

#
#
#
class Launcher():
    def __init__(self, title="", geometry=(900,400)):
        self.app = None
        self.screen_title = title
        self.screen_geo = geometry
        self.theme = None
        
    def init_with_app(self, app):
        self.app = app
        self.init_screen()
    
    def init_screen(self):
        pass

    #
    #
    #
    def message_handler(self, msg):
        """ メッセージを処理する """
        if msg.is_embeded():
            for msg in msg.expand():
                self.message_handler(msg)
        else:
            tag = msg.tag
            if tag == "exit-app":
                # アプリ終了の指示
                self.app.exit()
            else:
                # ログウィンドウにメッセージを出力
                self.insert_screen_message(msg)
    
    #
    def handle_chamber_message(self, chamber):
        for msg in chamber.handle_message():
            self.message_handler(msg)
        return True

    #
    # メッセージウィンドウの操作
    #
    def insert_screen_message(self, msg):
        pass

    def replace_screen_message(self, msgs):
        pass

    #
    # プロセスの情報を更新するために監視
    #
    def watch_process(self, process):
        pass
    
    #
    # 入力欄の操作
    #    
    # コマンドを実行する
    #  戻り値: False - なるべく早くアプリを終了させること
    def invoke_command(self, command):
        self.app.execute_command(command)
        if self.app.is_to_be_exit():
            return False
        self.install_chamber()
        return True
        
    # 入力を取得
    def get_input(self, spirit, instr):
        instr += " >>> "
        spirit.message(instr, nobreak=True)
        inputtext = spirit.wait_input()
        spirit.custom_message("input", inputtext)
        return inputtext
    
    # コマンド欄を実行する
    #  戻り値: False - なるべく早くアプリを終了させること
    def execute_command_input(self):
        command = self.pop_input_text()
        cha = self.app.get_active_chamber()
        if cha is not None and cha.is_waiting_input():
            cha.finish_input(command)
        else:
            return self.invoke_command(command)
        return True

    # コマンド欄を復元する
    def rollback_command_input(self):
        cha = self.app.get_active_chamber()
        if cha is None:
            return
        curline = self.pop_input_text(nopop=True)
        prevline = cha.get_command()
        if curline == prevline:
            return False
        self.replace_input_text(prevline)
        return True
    
    def insert_input_text(self, text):
        """ 入力文字列をカーソル位置に挿入する """
        pass
    
    def replace_input_text(self, text): 
        """ 入力文字列を代入する """
        pass
        
    def pop_input_text(self, nopop=False):
        """ 入力文字列を取り出しクリアする """
        return ""

    #
    #
    #
    def install_chamber(self):
        chamber = self.app.get_active_chamber()
        self.update_active_chamber(chamber, updatemenu=False, updateinput=False)
        self.add_chamber_menu(chamber)

    def shift_active_chamber(self, d):
        index = self.app.get_active_chamber_index()
        if index is None:
            return
        newindex = index - d
        if newindex<0:
            # 先頭を超えた場合は変化なし
            return
        if not self.app.set_active_chamber_index(newindex):
            # 末尾を超えた場合はコマンド欄を空にする
            self.replace_input_text("") 
            return
        self.update_active_chamber(self.app.get_active_chamber())
        
    def update_active_chamber(self, chamber, updatemenu=True, updateinput=True):
        msgs = chamber.get_message()
        self.replace_screen_message(msgs) # メッセージが膨大な場合、ここで時間がかかることも。別スレッドにするか？
        self.watch_process(chamber)
        if updateinput:
            cmd = chamber.get_command()
            self.replace_input_text(cmd)
        if updatemenu:
            self.update_chamber_menu(active=chamber)

    def add_chamber_menu(self, chamber):
        pass

    def update_chamber_menu(self, **kwargs):
        pass

    #
    # 
    #
    # ダイアログからファイルパスを入力
    def input_filepath(self, *filters:Tuple[str, str]):
        filepath = self.openfilename_dialog(filters = filters, initialdir = self.app.get_current_dir())
        if filepath:
            self.insert_input_text("{}".format(filepath))
    
    # カレントディレクトリの変更
    def change_cd_dialog(self):
        dirpath = self.opendirname_dialog(initialdir = self.app.get_current_dir())
        if dirpath:
            return self.invoke_command("cd -- {}".format(dirpath))

    def openfilename_dialog(self, *, filters=None, initialdir=None):
        raise NotImplementedError()

    def opendirname_dialog(self, *, filters=None, initialdir=None):
        raise NotImplementedError()
    
    #
    # ハンドラ
    #
    def put_input_command(self, spirit, command):
        tim = datetime.datetime.now().strftime("%Y-%m-%d|%H:%M.%S")
        spirit.message_em("[{}] >>> ".format(tim), nobreak=True)
        spirit.custom_message("input", command)
    
    def on_exec_process(self, spirit, process):
        """ プロセス実行時 """
        self.put_input_command(spirit, process.get_full_command())
    
    def on_interrupt_process(self, spirit):
        """ プロセス中断時 """
        spirit.message_em("実行中のプロセスを中断しました")
    
    def on_error_process(self, spirit, process, excep):
        """ プロセスのエラーによる終了時 """
        spirit.error("失敗しました。以下、発生したエラーの詳細：")
        spirit.error(traceback.format_exc())

    def on_exit_process(self, spirit, process, invocation):
        """ プロセスの正常終了時 """
        spirit.message_em("実行終了\n")
        
        # 引数エラーを報告
        if invocation:
            for label, missings, unuseds in invocation.arg_errors():
                if missings:
                    spirit.warn("[{}] 以下の引数は与えられませんでした：".format(label))
                    for name in missings:
                        spirit.warn("  {}".format(name))
                if unuseds:
                    spirit.warn("[{}] 以下の引数は使用されませんでした：".format(label))
                    for name in unuseds:
                        spirit.warn("  {}".format(name))
    
    def on_bad_command(self, spirit, process, command, error):
        """ 不明なコマンド """
        self.put_input_command(spirit, command)
        if process is None:
            spirit.error("'{}'は不明なコマンドです".format(command))
            if self.app.test_valid_process("help"):
                spirit.message("'help'でコマンド一覧を表示できます")
        else:
            spirit.error("{}: コマンド引数が間違っています:".format(process.get_prog()))
            spirit.error(error)
            for line in process.get_help():
                spirit.message(line)
    
    def on_exit(self):
        """ アプリ終了時 """
        self.destroy()

    #
    #
    # 
    def run_mainloop(self):
        pass
    
    def destroy(self):
        pass
    
    #
    #
    #
    def get_theme(self):
        return self.theme
    
    def set_theme(self, theme):
        self.theme = theme
    
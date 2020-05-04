#!/usr/bin/env python3
# coding: utf-8

import os
import datetime
import traceback
from typing import Tuple, Sequence, List

from machaon.cui import fixsplit

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
            if tag == "delete-message":
                cnt = msg.argument("count")
                lno = msg.argument("line")
                self.delete_screen_message(lno, cnt)
            elif tag == "dataview":
                datas = self.app.get_active_chamber().get_bound_data(running=True)
                if datas is None:
                    msg.tag = "message"
                    msg.text = "データが作成されていません" + "\n"
                    self.insert_screen_message(msg)
                elif datas.nothing():
                    msg.tag = "message"
                    msg.text = "結果は0件です" + "\n"
                    self.insert_screen_message(msg)
                else:
                    viewer = self.dataviewer(datas.get_viewtype())
                    self.insert_screen_dataview(msg, viewer, datas)
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

    def delete_screen_message(self, lineno, count):
        pass

    def replace_screen_message(self, msgs):
        pass

    #
    # プロセスの情報を更新するために監視
    #
    def watch_active_process(self):
        pass

    def watch_running_process(self, states):
        pass
        
    # 
    def dataviewer(self, viewtype):
        return None

    def insert_screen_dataview(self, msg, viewer, data):
        pass
    
    #
    # 入力欄の操作
    #    
    # コマンドを実行する
    def invoke_command(self, command):
        # 終了コマンド
        if command == "exit":
            self.app.exit()
            return
        
        if not command:
            return

        # 特殊コマンド
        if command[0] == ":":
            if self.invoke_mini_command(command[1:]):
                return
    
        chamber = self.app.run_process(command) # 実行

        self.update_active_chamber(chamber, updatemenu=False)
        self.add_chamber_menu(chamber)

        # この時点でプロセスが終了している場合もあり、更新させるために手動で状態を追加しておく
        states = self.app.get_chambers_state()
        states["running"].append(chamber.get_index())
        self.watch_running_process(states)
    
    #
    def invoke_mini_command(self, command):
        if command.isdigit():
            # データのインデックスによる即時選択
            index = int(command)
            try:
                self.select_dataview_item(index)
            except IndexError:
                self.replace_input_text("<その番号のデータは存在しません>")
            return True

        elif command.endswith("."):
            # コマンド接頭辞の設定
            prefix = command[1:].strip()
            self.app.set_command_prefix(prefix)
            self.replace_input_text("<コマンド接頭辞を設定しました>")
            return True

        elif command.startswith(">"):
            # データビューの選択アイテムから文字列を展開する
            item = None
            chm = self.app.select_chamber()
            if chm:
                data = chm.get_bound_data()
                if data:
                    item = data.selection_item()
                    
            if item:
                itemname, restcommand = fixsplit(command[1:], sep=" ", maxsplit=1)
                if not itemname:
                    value = item.get_link()
                    if restcommand: value = value + " " + restcommand
                elif hasattr(item, itemname):
                    value = getattr(item, itemname)()
                    if restcommand: value = value + " " + restcommand
                else:
                    value = "<選択アイテムに'{}'というプロパティはありません>".format(itemname)
            else:
                value = "<何も選択されていません>"

            # 入力欄を置き換える
            self.replace_input_text(value)
            return True
        
        return False

    # 入力を取得
    def get_input(self, spirit, instr):
        instr += " >>> "
        spirit.message(instr, nobreak=True)
        inputtext = spirit.wait_input()
        spirit.custom_message("input", inputtext)
        return inputtext
    
    # コマンド欄を実行する
    def execute_command_input(self):
        command = self.pop_input_text()
        cha = self.app.get_active_chamber()
        if cha is not None and cha.is_waiting_input():
            cha.finish_input(command)
        else:
            self.invoke_command(command)

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
    def activate_new_chamber(self):
        chamber = self.app.get_active_chamber()
        self.update_active_chamber(chamber, updatemenu=False)
        self.add_chamber_menu(chamber)

        # この時点でプロセスが終了している場合もあり、更新させるために手動で状態を追加しておく
        states = self.app.get_chambers_state()
        states["running"].append(chamber.get_index())
        self.watch_running_process(states)

    def shift_active_chamber(self, d):
        index = self.app.get_active_chamber_index()
        if index is None:
            return
        newindex = index - d
        if newindex<0:
            # 先頭を超えた場合は変化なし
            return
        if not self.app.set_active_chamber_index(newindex):
            return
        self.update_active_chamber(self.app.get_active_chamber())
        
    def update_active_chamber(self, chamber, updatemenu=True):
        msgs = chamber.get_message()
        self.replace_screen_message(msgs) # メッセージが膨大な場合、ここで時間がかかることも。別スレッドにするか？
        self.watch_active_process()

        if updatemenu:
            self.update_chamber_menu(active=chamber.get_index())

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

    def openfilename_dialog(self, **options):
        raise NotImplementedError()

    def opendirname_dialog(self, **options):
        raise NotImplementedError()

    #
    #
    #
    def select_dataview_item(self, index):
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
        #self.put_input_command(spirit, process.get_full_command())
    
    def on_interrupt_process(self, spirit, process):
        """ プロセス中断時 """
        spirit.message_em("中断しました")
    
    def on_error_process(self, spirit, process, excep, timing):
        """ プロセスのエラーによる終了時 """
        if timing == "argparse":
            tim = "引数の解析中に"
        elif timing == "executing":
            tim = "プロセス実行の前後に"
        elif timing == "execute":
            tim = "プロセス内で"
        else:
            tim = "不明な時空間'{}'にて".format(timing)
        spirit.error("{}エラーが発生し、失敗しました。".format(tim))
        
        details = traceback.format_exception(type(excep), excep, excep.__traceback__)
        spirit.error(details[-1])
        spirit.message_em("スタックトレース：")
        spirit.message("".join(details[1:-1]))

    def on_exit_process(self, spirit, process, invocation):
        """ プロセスの正常終了時 """
        if invocation is not None:
            spirit.message_em("実行終了\n")
        
            # 引数エラーを報告
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
        #self.put_input_command(spirit, command)
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
    
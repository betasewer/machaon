#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import datetime
import traceback
import threading
import pprint

from typing import Tuple, Sequence, List

from machaon.cui import composit_text
from machaon.process import ProcessMessage, NotExecutedYet, ProcessChamber
from machaon.object.message import MessageError

#
meta_command_sigil = "/"

#
#
#
class Launcher():
    wrap_width = 0xFFFFFF

    def __init__(self, title="", geometry=None):
        self.app = None
        self.screen_title = title or "Machaon Terminal"
        self.screen_geo = geometry or (900,400)
        self.theme = None
        
    def init_with_app(self, app):
        self.app = app
        self.init_screen()
        # デスクトップの追加
        #deskchamber = self.app.select_chamber("desktop")
        #self.update_active_chamber(deskchamber, updatemenu=False)
        #self.add_chamber_menu(deskchamber)
    
    def init_screen(self):
        pass
    
    def prettyformat(self, value):
        pp = pprint.PrettyPrinter(width=type(self).wrap_width)
        return pp.pformat(value)

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
            if tag == "new-objects":
                objs = msg.argument("objects")
                for obj in objs:    
                    expr = " -> {} [{}]".format(obj.value, obj.get_typename())
                    self.insert_screen_message(ProcessMessage(expr, tag="message"))
                    
            elif tag == "delete-message":
                cnt = msg.argument("count")
                lno = msg.argument("line")
                self.delete_screen_message(lno, cnt)

            elif tag == "object-view":
                obj = msg.argument("object")
                
                # 見出し
                text = "オブジェクト：{} [{}]\n".format(obj.name, obj.get_typename())
                self.insert_screen_message(ProcessMessage(text, tag="message-em"))

                # 内容
                if obj.get_typename() == "dataview":
                    datas = obj.value
                    if datas.nothing():
                        text = "結果は0件です" + "\n"
                        self.insert_screen_message(ProcessMessage(text))
                    else:
                        viewtype = datas.get_viewtype()
                        self.insert_screen_dataview(datas, viewtype, obj.name)
                else:
                    text = "値：\n  {}\n".format(obj.to_string())
                    self.insert_screen_message(ProcessMessage(text))
            
            elif tag == "object-summary":
                self.insert_screen_object_summary(msg)

            elif tag == "canvas":
                self.insert_screen_canvas(msg)
            
            elif tag == "new-chamber-launched":
                self.insert_screen_prompt()
            
            elif tag == "finished":
                self.insert_screen_message(ProcessMessage("", tag="message")) # 改行を1つ入れる
                self.insert_screen_prompt()

            else:
                # 適宜改行を入れる
                if msg.argument("wrap", True):
                    msg.text = composit_text(msg.get_text(), type(self).wrap_width)

                # ログウィンドウにメッセージを出力
                self.insert_screen_message(msg)
    
    # プロセスから送られたメッセージをひとつひとつ処理する
    def handle_chamber_message(self, chamber):
        for msg in chamber.handle_process_messages():
            self.message_handler(msg)

    #
    # メッセージウィンドウの操作
    #
    def insert_screen_message(self, msg):
        raise NotImplementedError()

    def delete_screen_message(self, lineno, count):
        raise NotImplementedError()

    def replace_screen_message(self, msgs):
        raise NotImplementedError()

    #
    # プロセスの情報を更新するために監視
    #
    def watch_chamber_message(self):        
        """ チャンバーの発するメッセージを読みに行く """
        procchamber = self.app.get_active_chamber()
        running = not procchamber.is_finished()
        self.handle_chamber_message(procchamber)
        return running

    def watch_chamber_state(self, prevstates):
        """ 動作中のプロセスの状態を調べる """
        curstates = self.app.get_chambers_state()

        # 停止したプロセスを調べる
        for wasrunning in prevstates["running"]:
            if wasrunning not in curstates["running"]:
                chm = self.app.get_chamber(wasrunning)
                self.finish_chamber(chm)

        return curstates
        
    # 
    def insert_screen_dataview(self, dataview, viewtype, dataname):
        raise NotImplementedError()
    
    #
    def insert_screen_appendix(self, values, title=""):
        raise NotImplementedError()
    
    #
    def insert_screen_object_summary(self, msg):
        raise NotImplementedError()
    
    #
    def insert_screen_canvas(self, canvas):
        raise NotImplementedError()
    
    # ログ保存用にテキストのみを取得する
    def get_screen_texts(self) -> str:
        raise NotImplementedError()

    # 入力待ちを示す
    def insert_screen_prompt(self):
        prompt = ">>> "
        self.insert_screen_message(ProcessMessage(prompt, tag="message-em", nobreak=True))
    
    #
    # 入力欄の操作
    #
    # 入力を取得
    def get_input(self, spirit, instr):
        instr += " >>> "
        spirit.message(instr, nobreak=True)
        inputtext = spirit.wait_input()
        spirit.custom_message("input", inputtext)
        return inputtext
    
    # コマンド欄を実行する
    def execute_command_input(self):
        message = self.pop_input_text()
        cha = self.app.get_active_chamber()
        if cha is not None and cha.is_waiting_input():
            cha.finish_input(message)
        else:
            self.app.eval_object_message(message)

    # コマンド欄を復元する
    def rollback_command_input(self):
        cha = self.app.get_active_chamber()
        if cha is None:
            return
        curline = self.pop_input_text(nopop=True)
        prevline = cha.get_input_command()
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
    def activate_new_chamber(self, newchm: ProcessChamber):
        """ チャンバーの新規作成時に呼ばれる """
        self.update_active_chamber(newchm, updatemenu=False)
        self.add_chamber_menu(newchm)

        # この時点でプロセスが終了している場合もあり、更新させるために手動で状態を追加しておく
        states = self.app.get_chambers_state()
        states["running"].append(newchm.get_index())

        self.watch_chamber_state(states)

    def shift_active_chamber(self, delta):
        """ 隣接したチャンバーをアクティブにする """
        chm = self.app.shift_active_chamber(delta)
        if chm is None:
            return
        self.update_active_chamber(chm)

    def update_active_chamber(self, chamber, updatemenu=True):
        """ アクティブなチャンバーを移す """
        msgs = chamber.get_process_messages()
        self.replace_screen_message(msgs) # メッセージが膨大な場合、ここで時間がかかることも。別スレッドにするか？
        self.watch_chamber_message()
        if updatemenu:
            self.update_chamber_menu(active=chamber)

    def close_active_chamber(self):
        """ アクティブなチャンバーを削除する。動作中なら停止を試みる """
        chm = self.app.get_active_chamber()

        # 第一デスクトップは削除させない
        if chm.get_index() == 0:
            return

        # 削除し新たにアクティブにする
        def remove_and_shift(chm):
            # 消去
            self.remove_chamber_menu(chm)
            self.app.remove_chamber(chm.get_index())
            
            # 隣のチャンバーに移る
            nchm = self.app.get_active_chamber() # 新たなチャンバー
            self.update_active_chamber(nchm)

        # 停止処理
        if not chm.is_finished():
            self.break_chamber_process(timeout=10, after=remove_and_shift)
        else:
            remove_and_shift(chm)
    
    def break_chamber_process(self, timeout=10, after=None):
        """ アクティブな作動中のチャンバーを停止する """
        chm = self.app.get_active_chamber()
        if chm.is_finished():
            return
        if chm.is_interrupted():
            return # 既に別箇所で中断が試みられている

        chm.interrupt() # 中断をプロセスに通知する

        self.insert_screen_appendix("プロセス[{}]の中断を試みます...({}秒)".format(chm.get_index(), timeout))
        
        def watcher():
            for _ in range(timeout):
                if chm.is_finished():
                    if after: after(chm)
                    break
                chm.join(timeout=1)
            else:
                self.insert_screen_appendix("プロセス[{}]を終了できません".format(chm.get_index()))

        wch = threading.Thread(None, watcher, daemon=True)
        wch.start() # 一定時間、終了を待つ
    
    def finish_chamber(self, chamber):
        """ 終了したチャンバーに対する処理 """
        # 文字色を実行中の色から戻す
        self.update_chamber_menu(ceased=chamber)

    # メニューの更新
    def add_chamber_menu(self, chamber):
        raise NotImplementedError()

    def update_chamber_menu(self, *, active=None, ceased=None):
        raise NotImplementedError()
    
    def remove_chamber_menu(self, chamber):
        raise NotImplementedError()

    #
    # 
    #
    # ダイアログからファイルパスを入力
    def input_filepath(self, *filters:Tuple[str, str]):
        pass
    #    filepath = self.openfilename_dialog(filters = filters, initialdir = self.app.get_current_dir())
    #    if filepath:
    #        self.insert_input_text("{}".format(filepath))
    
    # カレントディレクトリの変更
    def change_cd_dialog(self):
        pass
    #    dirpath = self.opendirname_dialog(initialdir = self.app.get_current_dir())
    #    if dirpath:
    #        return self.invoke_command("cd -- {}".format(dirpath))

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
    def on_exec_process(self, spirit, process):
        """ プロセス実行時 """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d|%H:%M.%S")
        spirit.post("message", "[{}] ".format(timestamp), nobreak=True) 
        spirit.post("input", process.message.source)
    
    def on_interrupt_process(self, spirit, process):
        """ プロセス中断時 """
        spirit.post("message-em", "中断しました")
    
    def on_error_process(self, spirit, process, excep, timing):
        """ プロセスのエラーによる終了時 """
        if timing == "onexec":
            tim = "実行時に"
        else:
            tim = "不明なタイミング'{}'で".format(timing)
        spirit.post("error", "{}エラーが発生し、失敗しました。".format(tim))
        
        if isinstance(excep, MessageError):
            spirit.post("message-em", "メッセージ解決：")
            excep.message.pprint_log(lambda x: spirit.post("message", x))
        else:
            details = traceback.format_exception(type(excep), excep, excep.__traceback__)
            spirit.post("error", details[-1])
            spirit.post("message-em", "スタックトレース：")
            spirit.post("message", "".join(details[1:-1]))    

    def on_exit_process(self, spirit, process, invocation):
        """ プロセスの正常終了時 """
        pass
    
    def on_bad_command(self, spirit, process, excep):
        """ 不明なコマンド """
        command = process.get_command_string()
        err = "'{}'は不明なコマンドです".format(command)
        if self.app.search_command("prog"):
            err += "。プログラムの一覧を表示 -> prog"
        self.replace_input_text(err)
    
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
    


#
def parse_procindex(expr):
    argname = expr
    procindex = ""
    if expr and expr[0] == "[":
        end = expr.find("]")
        if end > -1:
            procindex = expr[1:end]
            argname = expr[end+1:]
    return procindex, argname.strip()

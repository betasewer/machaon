#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import traceback
import threading
import pprint
from typing import Tuple, Sequence, List, Optional

from machaon.cui import composit_text
from machaon.process import ProcessMessage, NotExecutedYet, ProcessChamber, TempSpirit

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
        self.history = InputHistory()
        
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
            if tag == "on-exec-process":
                process = msg.argument("process")
                code = msg.text
                if code == "begin":
                    timestamp = msg.argument("timestamp")
                    self.on_exec_process(process, timestamp)
                elif code == "interrupted":
                    self.on_interrupt_process(process)
                    self.on_end_process(process)
                elif code == "error":
                    error = msg.argument("error") # error はProcessError型のオブジェクト
                    expr = " -> {} [{}<{}>]".format(error.summary(), error.get_typename(), error.value.get_error_typename())
                    self.insert_screen_message("message", expr)
                    self.on_error_process(process, error)
                    self.on_end_process(process)
                elif code == "success":
                    obj = msg.argument("ret")
                    process = msg.argument("process")
                    context = msg.argument("context")
                    if obj:
                        if obj.is_pretty_view():
                            m = ProcessMessage(tag="object-pretty-view", process=process, object=obj.value.get_object(), context=context)
                            self.message_handler(m)
                        else:
                            expr = " -> {} [{}]".format(obj.summary(), obj.get_typename())
                            self.insert_screen_message("message", expr)
                    self.on_success_process(process)
                    self.on_end_process(process)
                else:
                    self.insert_screen_message(msg.tag, msg.text, **msg.args)
            
            elif tag == "delete-message":
                cnt = msg.argument("count")
                lno = msg.argument("line")
                self.delete_screen_message(lno, cnt)

            elif tag == "object-pretty-view":
                obj = msg.argument("object")
                process = msg.argument("process")
                context = msg.argument("context")
                # pprintメソッドを呼ぶ
                obj.pprint(context.spirit)
                # ただちにメッセージを取得し処理する
                for msg in process.handle_post_message():
                    self.message_handler(msg)
            
            elif tag == "object-summary":
                self.insert_screen_object_summary(msg)
            
            elif tag == "object-setview":
                data = msg.argument("data")
                viewtype = data.get_viewtype()
                context = msg.argument("context")
                self.insert_screen_setview(data, viewtype, "testdata", context)
            
            elif tag == "object-tupleview":
                data = msg.argument("data")
                context = msg.argument("context")
                self.insert_screen_setview(data, "tuple", "", context)

            elif tag == "canvas":
                self.insert_screen_canvas(msg)

            else:
                # 適宜改行を入れる
                if msg.argument("wrap", True):
                    msg.text = composit_text(msg.get_text(), type(self).wrap_width)

                # ログウィンドウにメッセージを出力
                self.insert_screen_message(msg.tag, msg.text, **msg.args)
    
    # プロセスから送られたメッセージをひとつひとつ処理する
    def handle_chamber_message(self, chamber):
        for msg in chamber.handle_process_messages():
            self.message_handler(msg)

    #
    # メッセージウィンドウの操作
    #
    def insert_screen_message(self, tag, value, **args):
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
    def insert_screen_setview(self, setview, viewtype, dataname, context):
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

    #
    # 入力欄の操作
    #
    # 入力を取得
    def get_input(self, spirit, instr):
        instr += " {} ".format(self.get_input_prompt())
        spirit.message(instr, nobreak=True)
        inputtext = spirit.wait_input()
        spirit.custom_message("input", inputtext)
        return inputtext
    
    # コマンド欄を実行する
    def execute_input_text(self):
        message = self.get_input_text(pop=True) # メッセージを取得
        cha = self.app.get_active_chamber()
        if cha is not None and cha.is_waiting_input():
            # 入力を完了する
            cha.finish_input(message)
        else:
            # メッセージを実行する
            self.app.eval_object_message(message)
        # 入力履歴に追加する
        self.history.push(message)
        self.history.select_last()

    # コマンド欄を復元する
    def rollback_input_text(self):
        message = self.history.get()
        if message is not None:
            self.replace_input_text(message)
    
    def insert_input_text(self, text):
        """ 入力文字列をカーソル位置に挿入する """
        pass
    
    def replace_input_text(self, text): 
        """ 入力文字列を代入する """
        pass
        
    def get_input_text(self, pop=False):
        """ 入力文字列を取り出す """
        return ""

    def get_input_prompt(self) -> str:
        """ 入力プロンプト """
        return ">>> "

    #
    # チャンバーの操作
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
    # 入力ヒストリ
    #
    def shift_history(self, delta):
        self.history.shift(delta)
        inputmsg = self.history.get()
        if inputmsg is not None:
            self.replace_input_text(inputmsg)

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
    def select_setview_item(self, index):
        raise NotImplementedError()
    
    #
    # ハンドラ
    #    
    def on_exec_process(self, process, exectime):
        """ プロセス実行開始時 """
        self.insert_screen_message("message-em", "[{:04}] ".format(process.get_index()), nobreak=True)
        timestamp = exectime.strftime("%Y-%m-%d|%H:%M.%S")
        self.insert_screen_message("message", "[{}] ".format(timestamp), nobreak=True)
        self.insert_screen_message("input", process.message.source)
    
    def on_interrupt_process(self, process):
        """ プロセス中断時 """
        self.insert_screen_message("message-em", "中断しました。")
    
    def on_error_process(self, process, excep):
        """ プロセスの異常終了時 """
        #self.insert_screen_message("error", "実行中にエラーが発生し、失敗しました。")

    def on_success_process(self, process):
        """ プロセスの正常終了時 """
        pass
    
    def on_end_process(self, process):
        """ 正常であれ異常であれ、プロセスが終了した後に呼ばれる """
        self.insert_screen_message("message", "") # 改行を1つ入れる
        self.insert_screen_message("message-em", self.get_input_prompt(), nobreak=True) # 次回入力へのプロンプト
    
    #def on_bad_command(self, spirit, process, excep):
    #    """ 不明なコマンド """
    #    command = process.get_command_string()
    #    err = "'{}'は不明なコマンドです".format(command)
    #    if self.app.search_command("prog"):
    #        err += "。プログラムの一覧を表示 -> prog"
    #    self.replace_input_text(err)
    
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


#
#
#
class InputHistory():
    def __init__(self):
        self._msgs: List[str] = [] 
        self._index = None
    
    def push(self, msg: str):
        self._msgs.append(msg)
        
    def select_last(self):
        self._index = len(self._msgs)-1 # 末尾を選択する

    def shift(self, delta: int):
        if self._index is None:
            return
        newindex = self._index + delta
        if newindex >= len(self._msgs):
            newindex = len(self._msgs)-1
        elif newindex < 0:
            newindex = 0
        self._index = newindex
    
    def get(self) -> Optional[str]:
        if self._index is None:
            return None
        return self._msgs[self._index]
    

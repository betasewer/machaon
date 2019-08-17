#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import queue
import threading
import traceback
import configparser
import subprocess
from collections import OrderedDict

from machaon.processor import Processor, BadCommand
from machaon.cui import reencode, test_yesno

#
# ###################################################################
#  すべてのmachaonアプリで継承されるアプリクラス
#   プロセッサーを走らせる、UIの管理を行う
#   プロセッサーに渡され、メッセージ表示・設定項目へのアクセスを提供する
# ###################################################################
#
class App:
    def __init__(self, title, ui=None):
        self.title = title
        self.ui = ui
        self.settings = {}
        self.thr = None 
        self.lastresult = None # is_runnning中は外からアクセスしないのでセーフ？
        self.stopflag = False # boolの代入・読みだしはスレッドセーフ
        
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        self.curdir = desktop # 基本ディレクトリ
        
        if self.ui is not None:
            self.init_ui()
    
    @property
    def launcher(self):
        return self.ui.get_launcher()
    
    def init_ui(self, ui=None):
        if ui is not None:
            self.ui = ui
        if hasattr(self.ui, "init_with_app"):
            self.ui.init_with_app(self)
        
    #
    #
    #
    def run(self):
        if self.ui is None:
            raise ValueError("App UI must be initialized")
        if self.launcher is None:
            raise ValueError("App launcher must be initialized")
        self.mainloop()
        self.join_process_running()

    def exit(self):
        self.on_exit()
    
    def mainloop(self):
        self.ui.reset_screen()
        self.ui.run_mainloop()
    
    #
    #　メッセージ
    #
    def message(self, msg, **options):
        self.print_message(AppMessage(msg, "message", **options))
        
    # 重要
    def message_em(self, msg, **options):
        self.print_message(AppMessage(msg, "message_em", **options))
        
    # エラー
    def error(self, msg, **options):
        self.print_message(AppMessage(msg, "error", **options))
        return False
        
    # 警告
    def warn(self, msg, **options):
        self.print_message(AppMessage(msg, "warn", **options))

    # リンクを貼る
    def hyperlink(self, msg, link=None, tag=None, **options):
        self.print_message(AppMessage(msg, "hyper", link=(link or msg), linktag=tag, **options))
    
    # リンクを開くハンドラ
    def open_hyperlink(self, link):
        if os.path.isfile(link):
            cmds = ["start", link]
            subprocess.Popen(cmds, shell=True)
        else:
            import webbrowser
            webbrowser.open_new_tab(link)
    
    # メッセージを流す
    def print_message(self, msg):
        self.ui.post_message(msg)
    
    def print_target(self, target):
        self.message_em('対象 --> [{}]'.format(target))
    
    def print_title(self):
        self.message_em(" ------ {} ------ ".format(self.title))
    
    # CUIの動作
    def ask_yesno(self, desc):
        answer = self.ui.get_input(desc)
        return test_yesno(answer)
    
    def reset_screen(self):
        self.ui.reset_screen()

    def scroll_screen(self, index):
        self.ui.scroll_screen(index)
    
    def get_input(self, desc=""):
        return self.ui.get_input(desc)

    # 基本ディレクトリ
    def change_current_dir(self, path):
        if os.path.isdir(path):
            self.curdir = path
    
    def get_current_dir(self):
        return self.curdir
    
    def abspath(self, path):
        # 絶対パスにする
        if not os.path.isabs(path):
            cd = self.curdir
            if cd is None:
                cd = os.getcwd()
            path = os.path.normpath(os.path.join(cd, path))
        return path
    
    #
    # コマンド処理の流れ
    #
    # コマンド文字列からで呼び出す
    def command_process(self, cmdstr, *, threading=False):
        cmd = self.launcher.translate_command(cmdstr)
        if cmd is None:
            self.error("'{}'は不明なコマンドです".format(cmdstr))
            cmd = self.launcher.translate_command("help")
            if cmd is not None:
                self.message("'help'でコマンド一覧を表示")
            self.on_exit_command(None)
            return None

        ret = None
        if threading:
            self.run_process(cmd.get_command(), cmd.get_argument())
        else:
            ret = self.exec_process(cmd.get_command(), cmd.get_argument())
        return ret

    # コマンドクラスと引数文字列を渡して実行する
    def exec_process(self, proc, commandstr=""):
        result = None
        try:
            if isinstance(proc, type):
                # Processor派生クラス
                procs = proc.generates(self, commandstr)
                for proc in procs:
                    if self.is_process_interrupted():
                        self.message("中断しました")
                        break
                    result = proc.start() 
            else:
                # 簡易実装のコマンドインスタンス（CommandFunction）
                if commandstr.strip() in ("-h", "--help"):
                    proc.help(self)
                else:
                    result = proc.invoke(commandstr)
        except BadCommand as b:
            self.error("コマンド引数が間違っています:")
            proc.help(self)
            self.error(b.error)
        except Exception:
            self.error("失敗しました。以下、発生したエラーの詳細：")
            self.error(traceback.format_exc())
            
        self.lastresult = result
        self.on_exit_command(proc)
        return result
        
    # コマンド（プロセス/CommandFunction）実行終了時に呼び出されるハンドラ
    def on_exit_command(self, procclass):
        self.ui.on_exit_command(procclass)
    
    # アプリケーション終了時に呼び出されるハンドラ
    def on_exit(self):
        self.ui.on_exit()
    
    #
    # 非同期処理
    #
    def run_process(self, procclass, commandstr=None):
        if self.is_process_running():
            return
        self.stopflag = False
        self.lastresult = None
        self.thr = threading.Thread(target=self.exec_process, args=(procclass, commandstr))
        self.thr.start()

    def is_process_running(self):
        return self.thr and self.thr.is_alive()

    def join_process_running(self):
        if self.is_process_running():
            self.thr.join()

    def get_process_result(self):
        if self.is_process_running():
            raise Exception("")
        return self.lastresult
    
    # 操作中断
    def interrupt_process(self):
        if self.stopflag is False:
            self.stopflag = True

    # Processor側で参照する
    def is_process_interrupted(self):
        return self.stopflag is True

    #
    def message_io(self, **kwargs):
        return AppMessageIO(self, **kwargs)
        
#
#
#
class AppMessage():
    def __init__(self, text, tag="message", **kwargs):
        self.text = str(text)
        self.tag = tag
        self.kwargs = kwargs
        
    def argument(self, name, default=None):
        return self.kwargs.get(name, default)

    def set_argument(self, name, value):
        self.kwargs[name] = value
        
#
class AppMessageIO():
    def __init__(self, app, **kwargs):
        self.app = app
        self.kwargs = kwargs
    
    def write(self, text):
        tag = self.kwargs.pop("tag", None)
        self.app.print_message(AppMessage(text, tag, **self.kwargs))
        
# このクラスをプロセスの返り値として返すとアプリが終了する
class ExitApp():
    pass

#
# ###################################################################
#  Basic UI
# ###################################################################
#
class BasicCUI:
    def __init__(self):
        self.msgqueue = queue.Queue()
    
    def get_launcher(self):
        return self
    
    # キューにためたメッセージを処理
    def handle_queued_message(self):
        try:
            while True:
                entry = self.msgqueue.get(block=False)
                self.message_handler(entry)
        except queue.Empty:
            return
        
    def discard_queued_message(self):
        self.msgqueue = queue.Queue()
        
    def queue_message(self, msg):
        self.msgqueue.put(msg)
    
    def post_message(self, msg):
        if msg.argument("fromAnotherThread", False):
            self.queue_message(msg)
        else:
            self.message_handler(msg)

    def message_handler(self, msg):
        raise NotImplementedError()
                
    #
    def get_input(self, desc):
        pass

    def reset_screen(self):
        pass
        
    def scroll_screen(self, index):
        pass

    # UIのメインループ
    def run_mainloop(self):
        raise NotImplementedError()

    # コマンド（プロセス/CommandFunction）実行終了時に呼び出されるハンドラ
    def on_exit_command(self, procclass=None):
        pass
    
    # アプリケーション終了時に呼び出されるハンドラ
    def on_exit(self):
        pass


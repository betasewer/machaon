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

from machaon.command import ProcessClass, ProcessFunction, BadCommand, describe_command
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
        self.ui = None
        self.settings = {}
        self.thr = None 
        self.lastresult = None # is_runnning中は外からアクセスしないのでセーフ？
        self.stopflag = False # boolの代入・読みだしはスレッドセーフ
        
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        self.curdir = desktop # 基本ディレクトリ
        
        if ui is None:
            from machaon.shell import WinShellUI
            ui = WinShellUI() # デフォルトはとりあえずWindows決め打ち
        self.init_ui(ui)
    
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
        self.print_message(AppMessage(msg, "hyperlink", link=link, linktag=tag, **options))
    
    # リンクを開くハンドラ
    def open_hyperlink(self, link):
        if os.path.isfile(link):
            cmds = ["start", link]
            subprocess.Popen(cmds, shell=True)
        else:
            import webbrowser
            webbrowser.open_new_tab(link)
    
    def msg(self, msg, tag, **options):
        return AppMessage(msg, tag, **options)
    
    # メッセージを流す
    def print_message(self, msg):
        for m in msg.expand():
            self.ui.post_message(m)
    
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
        else:
            self.error("'{}'は有効なパスではありません".format(path))
    
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
    def exec_command(self, cmdstr, *, threading=False):
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
    
    # プロセスを即時実行する
    def exec(self, process, commandstr="", describer=None, bindapp=None, bindargs=None, prog=None):        
        proc = self.wrapped_process(process, describer=describer, bindapp=bindapp, bindargs=bindargs, prog=prog)
        return self.exec_process(proc, commandstr)
    
    # コマンドクラスと引数文字列を渡して実行する
    def exec_process(self, proc, commandstr):
        result = None
        try:
            procs = proc.generate_instances(self, commandstr)
            for proc in procs:
                if self.is_process_interrupted():
                    self.message_em("中断しました")
                    break
                result = proc.start()
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
    #
    #
    def wrapped_process(self, process, *, prog, describer=None, bindapp=False, bindargs=None):
        if isinstance(process, type):
            proc = ProcessClass(process, prog=prog)
        else:
            args = []
            if bindapp:
                args.append(self)
            if bindargs:
                args.extend(bindargs)
            proc = ProcessFunction(process, describer, *args, prog=prog)
        return proc
    
    # コマンド登録
    def add_command(self, process, keywords, describer=None, hidden=False, auxiliary=False, bindapp=False, bindargs=None, prog=None): 
        if len(keywords)<1:
            raise ValueError("keywords must be defined 1 or more")
        if prog is None:
            prog=keywords[0]
        proc = self.wrapped_process(process, prog=prog, describer=describer, bindapp=bindapp, bindargs=bindargs)
        return self.launcher.define_command(proc, keywords=keywords, hidden=hidden, auxiliary=auxiliary)

    def add_syscommands(self, *, exclude=(), shell=True):
        entries = []

        modules = []
        if shell:
            from machaon.shell_command import definitions as shell_definitions
            modules.append(shell_definitions)

        for defs in modules:
            for entry in defs:
                entries.append(entry)
        
        for obj in (self.ui, self.launcher, self):
            for entry in getattr(obj, "syscommands", ()):
                fnname = entry[0]
                cmd = getattr(obj, fnname, None)
                if cmd is None:
                    continue
                entries.append((cmd, *entry[1:]))
        
        for entry in entries:
            cmd = entry[0]
            keywords = entry[1]
            describer = entry[2]
            bindapp = entry[3] if len(entry)>3 else False
            bindargs = entry[4] if len(entry)>4 else None
            if len(keywords)==0 or keywords[0] in exclude:
                continue
            self.add_command(cmd, keywords=keywords, describer=describer, auxiliary=True, bindapp=bindapp, bindargs=bindargs)

    #
    # システムコマンド
    #
    def command_interrupt(self):    
        if not self.is_process_running():
            self.message("実行中のプロセスはありません")
            return
        self.message("プロセスを中断します")
        self.interrupt_process()
        
    def command_exit(self, ask=False):
        if ask:
            if not self.ask_yesno("終了しますか？ (Y/N)"):
                return
        return ExitApp
        
    def command_cls(self):
        self.reset_screen()

    def command_cd(self, path=None):
        if path is not None:
            path = self.abspath(path)
            self.change_current_dir(path)
        self.message("現在の作業ディレクトリ：" + self.get_current_dir())

    syscommands = [
        ("command_interrupt", ("interrupt", "it"), 
            describe_command(
                description="現在実行中のプロセスを中断します。"
            )
        ),
        ("command_cls", ("cls",), 
            describe_command(
                description="画面をクリアします。"
            )
        ),
        ("command_cd", ('cd',), 
            describe_command(
                description="作業ディレクトリを変更します。", 
            )["target directory-path"](
                nargs="?",
                help="移動先のパス"
            )
        ),
        ("command_exit", ("exit",),
            describe_command(
                description="終了します。"
            )["target --ask -a"](
                const_option=True,            
                help="確認してから終了する"
            )
        ),
    ]
    
    #
    # 非同期処理
    #
    def run_process(self, proc, commandstr=None):
        if self.is_process_running():
            return
        self.stopflag = False
        self.lastresult = None
        self.thr = threading.Thread(target=self.exec_process, args=(proc, commandstr))
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
    def __init__(self, text, tag="message", embed=None, **kwargs):
        self.text = str(text)
        self.tag = tag
        self.embed = embed
        self.kwargs = kwargs
        
    def argument(self, name, default=None):
        return self.kwargs.get(name, default)

    def set_argument(self, name, value):
        self.kwargs[name] = value
    
    def get_hyperlink_link(self):
        l = self.kwargs.get("link")
        if l is not None:
            return l
        return self.text

    def expand(self):
        if self.embed is None:
            return [self]

        def partmsg(msg=None, text=None, withbreak=False):
            if text is not None:
                msg = AppMessage(text, self.tag, None, **self.kwargs)
            if not withbreak:
                msg.set_argument("nobreak", True)
            return msg
            
        expanded = []
        state = 0
        lastkey = ""
        lasttext = ""
        for ch in self.text:
            if ch == "%":
                if state == 0:
                    state = 1
                elif state == 1:
                    lasttext += "%"
                    state = 0
                elif state == 2:
                    emsg = self.embed[int(lastkey)-1]
                    if emsg is not None:
                        expanded.append(partmsg(text=lasttext))
                        expanded.append(partmsg(emsg))
                        lasttext = ""
                    state = 0
            elif state == 1 or state == 2:
                lastkey += ch
                state = 2
            else:
                lasttext += ch
            
        expanded.append(partmsg(text=lasttext, withbreak=True))
        return expanded

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


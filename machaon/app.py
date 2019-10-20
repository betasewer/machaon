#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import queue
import threading
import traceback
import subprocess

from machaon.command import BadCommand, describe_command
from machaon.cui import test_yesno
import machaon.platforms

#
#
#
class _appmsg_functor():
    def __init__(self, fn, obj):
        self.fn = fn
        self.obj = obj

    def __call__(self, *args, **kwargs):
        self.obj.print_message(self.fn(self.obj, *args, **kwargs))
        return None
    
    def msg(self, *args, **kwargs):
        return self.fn(self.obj, *args, **kwargs)

class _appmsg_method():
    def __init__(self, fn):
        self.fn = fn
    
    def __get__(self, obj, objtype=None):
        return _appmsg_functor(self.fn, obj)

#
# ###################################################################
#  すべてのmachaonアプリで継承されるアプリクラス
#   プロセッサーを走らせる、UIの管理を行う
#   プロセッサーに渡され、メッセージ表示・設定項目へのアクセスを提供する
# ###################################################################
#
class AppRoot:
    def __init__(self):
        self.ui = None
        self.thr = None 
        self.lastresult = None # is_runnning中は外からアクセスしないのでセーフ？
        self.stopflag = False # boolの代入・読みだしはスレッドセーフ
        self.curdir = "" # 基本ディレクトリ        
        self.spirits = {}
    
    @property
    def launcher(self):
        return self.ui.get_launcher()
    
    def init_ui(self, ui):
        self.ui = ui
        if hasattr(self.ui, "init_with_app"):
            self.ui.init_with_app(self)
        
    #
    #
    #
    def get_spirit(self, spirit):
        if spirit is True or spirit is None:
            spiid = App.spirit_id
        else:
            spiid = spirit.spirit_id
        if spiid == App.spirit_id:
            return self
        
        if spiid in self.spirits:
            if self.spirits[spiid] is None:
                instance = spirit(self)
                self.spirits[spiid] = instance
            else:
                instance = self.spirits[spiid]
            return instance
        else:
            raise ValueError("Unknown spirit id: {}".format(spiid))
    
    #
    def touch_spirit(self, spirit):     
        if spirit is None:
            return None
        if spirit is App:
            return self

        spiid = spirit.spirit_id
        if spiid == App.spirit_id or spiid is None:
            spiid = len(self.spirits)+101

        if spiid not in self.spirits:
            if spiid < 100:
                raise ValueError("user spirit id must be > 100")
            spirit.spirit_id = spiid
        self.spirits[spiid] = None

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
    @_appmsg_method
    def message(self, msg, **options):
        return AppMessage(msg, "message", **options)
        
    # 重要
    @_appmsg_method
    def message_em(self, msg, **options):
        return AppMessage(msg, "message_em", **options)
        
    # エラー
    @_appmsg_method
    def error(self, msg, **options):
        return AppMessage(msg, "error", **options)
        
    # 警告
    @_appmsg_method
    def warn(self, msg, **options):
        return AppMessage(msg, "warn", **options)

    # リンクを貼る
    @_appmsg_method
    def hyperlink(self, msg, link=None, linktag=None, **options):
        return AppMessage(msg, "hyperlink", link=link, linktag=linktag, **options)
    
    @_appmsg_method
    def custom_message(self, tag, msg, **options):
        return AppMessage(msg, tag, **options)
    
    #
    def print_message(self, msg):
        for m in msg.expand():
            self.ui.post_message(m)
    
    def print_target(self, target):
        self.message_em('対象 --> [{}]'.format(target))
    
    #
    # CUIの動作
    #
    def ask_yesno(self, desc):
        answer = self.ui.get_input(desc)
        return test_yesno(answer)
    
    def get_input(self, desc=""):
        return self.ui.get_input(desc)
    
    def reset_screen(self):
        self.ui.reset_screen()

    def scroll_screen(self, index):
        self.ui.scroll_screen(index)

    # リンクを開くハンドラ
    def open_hyperlink(self, link):
        if os.path.isfile(link):
            machaon.platforms.current.openfile(link)
        else:
            import webbrowser
            webbrowser.open_new_tab(link)
    
    #
    # 基本ディレクトリ
    #
    def change_current_dir(self, path):
        if os.path.isdir(path):
            self.curdir = path
        else:
            self.error("'{}'は有効なパスではありません".format(path))
    
    def abspath(self, path):
        # 絶対パスにする
        if not os.path.isabs(path):
            cd = self.curdir
            if cd is None:
                cd = os.getcwd()
            path = os.path.normpath(os.path.join(cd, path))
        return path
    
    def get_current_dir(self):
        return self.curdir
    
    def set_current_dir_desktop(self):
        self.curdir = os.path.join(os.path.expanduser("~"), "Desktop")

    #
    # コマンド処理の流れ
    #
    # コマンド文字列からで呼び出す
    def exec_command(self, cmdstr, *, threading=False):
        # プロセスを確定
        cmd, cmdarg = self.launcher.translate_command(cmdstr)
        if cmd is None:
            self.on_exit_command(None, cmdstr)
            return None
        process = cmd.process
            
        # プロセスのスピリットを取得する
        spirit = self.get_spirit(process.get_bound_app())
        
        # 引数コマンドを解析
        argmap = self.parse_process_command(process, spirit, cmdarg)
        if argmap is None:
            self.on_exit_command(process, cmdarg)
            return None
        
        # 実行
        ret = None
        if threading:
            self.run_process(process, spirit, argmap)
        else:
            ret = self.exec_process(process, spirit, argmap)
        return ret
    
    # コマンド文字列を解析する
    def parse_process_command(self, process, spirit, commandarg):
        # 遅延コマンド初期化関数があればここで呼ぶ
        process.load_lazy_describer(spirit)

        # コマンドを処理
        bad = None
        argument = commandarg
        try:
            argmap, argument = process.run_argparser(spirit, commandarg)
        except BadCommand as b:
            bad = b.error

        self.on_exec_command(process, argument)
        if bad:
            self.on_bad_command(process, commandarg, bad)
            return None

        # help表示
        if argmap is None:
            process.get_argparser().print_parser_message(self)
        return argmap
    
    # プロセスを即時実行する
    def exec(self, process, argument="", *, bindapp=True, bindargs=None, custom_command_parser=None, prog=None):        
        # コマンドエントリの構築
        d = describe_command(process, bindapp=bindapp, bindargs=bindargs, custom_command_parser=custom_command_parser)
        prog = prog or getattr(process, "__name__") or "$"
        entry = d.build_entry(self, prog, (prog,))
        # 実行
        spirit = self.get_spirit(entry.process.get_bound_app())
        argmap = self.parse_process_command(entry.process, spirit, argument)
        if argmap is not None:
            return self.exec_process(entry.process, spirit, argmap)
        return None
    
    # プロセスクラスと引数文字列を渡して実行する
    def exec_process(self, process, spirit, argmap):
        proc = None
        result = None
        try:
            for proc in process.generate_instances(spirit, argmap):
                if self.is_process_interrupted():
                    self.message_em("中断しました")
                    break
                result = proc.start()
        except BadCommand as b:
            self.on_bad_command(process, "", b.error())
        except Exception:
            self.error("失敗しました。以下、発生したエラーの詳細：")
            self.error(traceback.format_exc())
            
        self.lastresult = result
        self.on_exit_command(proc, argmap)
        return result
    
    # 有効なプロセスコマンドか調べる（オプションまでは調べない）
    def test_command(self, commandstr):
        cmd, _ = self.launcher.translate_command(commandstr)
        return cmd is not None
        
    # コマンドパッケージを導入
    def install_commands(self, prefixes, package, *, exclude=()):
        # コマンドエントリを構築
        cmdset = package.build_commands(self, prefixes, exclude)
        # ランチャーに設定
        self.launcher.install_commands(cmdset)

    #
    # ハンドラ
    #
    # プロセス実行直前に呼び出されるハンドラ
    def on_exec_command(self, proc, argument):
        self.ui.on_exec_command(proc, argument)

    # コマンド解析失敗時に呼ばれるハンドラ
    def on_bad_command(self, proc, argument, error):   
        self.ui.on_bad_command(proc, argument, error)
        
    # プロセス実行終了時に呼び出されるハンドラ
    def on_exit_command(self, proc, argmap):
        self.ui.on_exit_command(proc, argmap)
    
    # アプリケーション終了時に呼び出されるハンドラ
    def on_exit(self):
        self.ui.on_exit()

    #
    # 非同期処理
    #
    def run_process(self, process, spirit, argmap):
        if self.is_process_running():
            return
        self.stopflag = False
        self.lastresult = None
        self.thr = threading.Thread(target=self.exec_process, args=(process, spirit, argmap))
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


#
# ###################################################################
#  App Spirit
# ###################################################################
#
default_app_id = 0
#
class App():
    spirit_id: int = default_app_id

    def __init__(self, app=None):
        self.root = app
    
    # rootアプリにリダイレクトする
    def __getattr__(self, name):
        if self.root is None:
            raise ValueError("App '{}': AppRoot must be bound, but none".format(type(self)))
        return getattr(self.root, name, None)

#
# Appを遅延して生成／初期化するローダータイプ
#
class Spirit():
    def __init__(self, klass, setup_fn):
        self.klass = klass
        self.setup = setup_fn
    
    @property
    def spirit_id(self):
        return self.klass.spirit_id
    
    @spirit_id.setter
    def spirit_id(self, v):
        self.klass.spirit_id = v
        return self
    
    def __call__(self, app): # -> app.App inheriting instance
        return self.setup(app)

# デコレータ
def spirit(klass):
    def _deco(fn):
        return Spirit(klass, fn)
    return _deco
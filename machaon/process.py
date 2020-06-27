#!/usr/bin/env python3
# coding: utf-8
import os
import sys
import inspect
import threading
import queue
import time
from typing import Sequence, Optional, List, Dict, Any, Tuple
from collections import defaultdict

from machaon.dataset import DataViewFactory
from machaon.cui import test_yesno, MiniProgressDisplay
from machaon.parser import CommandParser
         
#
# 各アプリクラスを格納する
#
"""
def __init__(self, app):
    self.app = app

def init_process(self):
    pass

def process_target(self, target) -> bool: # True/None 成功 / False 中断・失敗
    raise NotImplementedError()

def exit_process(self):
    pass
"""

#
#
#
class ProcessInitFailed(Exception):
    pass

#
# ###################################################################
#  process target class / function
# ###################################################################
#
class ProcessTarget():
    def __init__(self, argp, spirittype, lazyargdescribe):
        self.argparser = argp
        self.spirittype = spirittype
        self.lazyargdescribe = lazyargdescribe
    
    def load_lazy_describer(self, spirit):
        if self.lazyargdescribe is not None:
            self.lazyargdescribe(spirit, self.argparser)
            self.lazyargdescribe = None # 初回の引数解析時のみ発動する

    def get_argparser(self):
        return self.argparser
    
    def get_help(self):
        return self.argparser.get_help()
    
    def get_prog(self):
        return self.argparser.get_prog()
    
    def get_description(self):
        return self.argparser.get_description()
    
    # 自らのスピリットを生成する
    def inherit_spirit(self, other_spirit):
        sp = self.spirittype(other_spirit.app)
        sp.inherit(other_spirit)
        return sp
        
    #
    def invoke(self, spirit, parsedcommand, invocation):
        raise NotImplementedError()

    #
    def _target_invocation(self, label, invocation, invoker, preargs, parsedcommand):
        for inv in invoker.prepare_invocations(label, preargs, parsedcommand):
            invoker.invoke(inv)
            if not invocation.continue_(label, inv):
                return False
        return True

#
#
#
class ProcessTargetClass(ProcessTarget):
    def __init__(self, klass, argp, spirittype=None, lazyargdescribe=None):
        super().__init__(argp, spirittype, lazyargdescribe)
        self.klass = klass
        
        if hasattr(klass, "init_process"):
            self.init_invoker = FunctionInvoker(klass.init_process)
        else:
            self.init_invoker = None
        
        self.target_invoker = FunctionInvoker(klass.process_target)
        
        if hasattr(klass, "exit_process"):
            self.exit_invoker = FunctionInvoker(klass.exit_process)
        else:
            self.exit_invoker = None
    
    def get_valid_labels(self):
        labels = (
            ("init", self.init_invoker), 
            ("target", self.target_invoker),
            ("exit", self.exit_invoker)
        )
        return [x for (x,inv) in labels if inv is not None]
    
    def get_inspection(self):
        return "class", self.klass.__qualname__, self.klass.__module__

    # 
    def invoke(self, spirit, parsedcommand, invocation):
        # プロセスを生成
        proc = self.klass(spirit)
        if self.init_invoker:
            if not self._target_invocation("init", invocation, self.init_invoker, (proc,), parsedcommand):
                return invocation

        # メイン処理
        if not self._target_invocation("target", invocation, self.target_invoker, (proc,), parsedcommand):
            return invocation

        # 後処理
        if self.exit_invoker:
            if not self._target_invocation("exit", invocation, self.exit_invoker, (proc,), parsedcommand):
                return invocation

        return invocation

#
#
#
class ProcessTargetFunction(ProcessTarget):
    def __init__(self, fn, argp, spirittype=None, args=None, lazyargdescribe=None):
        super().__init__(argp, spirittype, lazyargdescribe)
        self.args = args or ()
        self.target_invoker = FunctionInvoker(fn)
    
    def get_valid_labels(self):
        return ["target"]
        
    def get_inspection(self):
        return "function", self.target_invoker.fn.__qualname__, self.target_invoker.fn.__module__

    def invoke(self, spirit, parsedcommand, invocation):
        # 束縛引数
        preargs = []
        if self.spirittype is not None:
            preargs.append(spirit)
        preargs.extend(self.args)
        
        # メイン処理
        self._target_invocation("target", invocation, self.target_invoker, preargs, parsedcommand)
        return invocation

#
#
#
class FunctionInvoker:
    def __init__(self, fn):
        self.fn = fn
        self.argnames = None # args, kwargs
        self.kwargvarname = None

        # inspectで引数名を取り出す
        names = []
        sig = inspect.signature(self.fn)
        for _, p in sig.parameters.items():
            if p.kind == inspect.Parameter.VAR_KEYWORD:
                self.kwargvarname = p.name
            elif p.kind == inspect.Parameter.VAR_POSITIONAL:
                pass
            else:
                names.append(p.name)
        self.argnames = names
    
    @property
    def fnqualname(self):
        # デバッグ用
        return self.fn.__qualname__
    
    #
    def prepare(self, *args, **kwargs):
        argmap = {}
        argmap.update(kwargs)

        values = []
        values.extend(args)

        paramnames = self.argnames[len(values):]
        remained_argnames = {k.replace("-","_"): k for k in argmap.keys()}
        missing_args = []
        for paramname in paramnames:
            if paramname in remained_argnames:
                valuekey = remained_argnames.pop(paramname)
                values.append(argmap[valuekey])
            else:
                missing_args.append(paramname)
            
        if missing_args:
            raise MissingArgumentError(self.fnqualname, missing_args)
        
        kwargs = {}
        if self.kwargvarname:
            for pname, aname in remained_argnames.items():
                if pname in argmap:
                    kwargs[pname] = argmap[aname]
            
            for pname in kwargs.keys():
                remained_argnames.pop(pname)

        unused_args = list(remained_argnames.values())
        
        #
        entry = InvocationEntry(values, kwargs)
        entry.set_arg_errors(missing_args, unused_args)
        return entry
    
    #
    def prepare_next_target(self, entry, **kwargs):
        entry = entry.clone()
        target_arg = kwargs["target"]
        if "target" in self.argnames:
            entry.args[self.argnames.index("target")] = target_arg
        else:
            raise ValueError("'target' argument not found")
        return entry
    
    #
    def prepare_invocations(self, label, preargs, parsedcommand):
        inv = None
        for targs in parsedcommand.prepare_arguments(label):
            if inv is None:
                inv = self.prepare(*preargs, **targs)
            else:
                inv = self.prepare_next_target(inv, **targs)
            yield inv
    
    #
    def invoke(self, invocation):            
        # 関数を実行する
        result = None
        exception = None
        try:
            result = self.fn(*invocation.args, **invocation.kwargs)
        except ProcessInterrupted as e:
            raise e
        except Exception as e:
            exception = e

        invocation.set_result(result, exception)
        return invocation

#
class MissingArgumentError(Exception):
    def __init__(self, fnqualname, missings):
        self.fnqualname = fnqualname
        self.missings = missings

#
#
#
class InvocationEntry():
    def __init__(self, args, kwargs):
        self.args = args
        self.kwargs = kwargs
        self.result = None
        self.missing_args = []
        self.unused_args = []
        self.exception = None
    
    def clone(self):
        inv = InvocationEntry(self.args, self.kwargs)
        inv.result = self.result
        inv.missing_args = self.missing_args
        inv.unused_args = self.unused_args
        inv.exception = self.exception
        return inv

    def set_arg_errors(self, missing_args, unused_args):
        self.missing_args = missing_args
        self.unused_args = unused_args
    
    def set_result(self, result, exception):
        self.result = result
        self.exception = exception
    
    def is_failed(self):
        if self.exception:
            return True
        return False

    def is_init_failed(self):
        if self.exception:
            return True
        else:
            return self.result is False

#
#
#
class ProcessInvocation:
    def __init__(self):
        self.entries = defaultdict(list)
        self.last_exception = None
    
    def continue_(self, label: str, entry: InvocationEntry):
        self.entries[label].append(entry)
        if entry.is_failed():
            self.last_exception = entry.exception
            return False
        if label == "init" and entry.is_init_failed():
            self.last_exception = ProcessInitFailed()
            return False
        return True
    
    def initerror(self, excep: BaseException):
        entry = InvocationEntry((), {})
        entry.set_result(None, excep)
        self.continue_("init", entry)

    def get_entries_of(self, label):
        return self.entries[label]
    
    def get_last_result(self):
        if self.entries["target"]:
            return self.entries["target"][-1].result
        return None
    
    def arg_errors(self):
        for label in ("init", "target", "exit"):
            if label not in self.entries or not self.entries[label]:
                continue
            tail = self.entries[label][-1] # 同じラベルであればエラーも同一のはず
            yield label, tail.missing_args, tail.unused_args

    def get_last_exception(self):
        return self.last_exception


#
# ######################################################################
# プロセスの実行
# ######################################################################
#
# スレッドの実行、停止、操作を行う 
#
class Process:
    def __init__(self, command):
        self.command = command
        # 
        self.target = None
        self.spirit = None
        self.parsedcommand = None
        # スレッド
        self.thread = None
        self.stop_flag = False
        self.last_invocation = None
        # メッセージ
        self.post_msgs = queue.Queue()
        # 入力
        self.input_waiting = False
        self.event_inputend = threading.Event()
        self.last_input = None
        # 付属データ
        self.bound_data = None
        
    def run(self, app):
        self.thread = threading.Thread(target=app.execute_process, args=(self,))
        self.stop_flag = False
        self.thread.start()
    
    def execute(self, target, spirit, parsedcommand):
        self.target = target
        self.spirit = spirit
        self.parsedcommand = parsedcommand

        # 操作を実行する
        invocation = ProcessInvocation()
        target.invoke(spirit, parsedcommand, invocation)
        self.last_invocation = invocation
        return invocation
    
    def get_target(self):
        if self.target is None:
            raise NotExecutedYet()
        return self.target 

    def get_spirit(self):
        if self.spirit is None:
            raise NotExecutedYet()
        return self.spirit
        
    def get_parsed_command(self):
        if self.parsedcommand is None:
            raise NotExecutedYet()
        return self.parsedcommand
    
    def get_command_args(self):
        return self.parsedcommand
    
    def build_command_string(self):
        prog = self.target.get_prog()
        exp = self.parsedcommand.get_expanded_command()
        return " ".join(x for x in [prog, exp] if x)
    
    def get_command_string(self):
        return self.command

    def get_last_invocation(self):
        if self.is_running():
            raise StillExecuting()
        return self.last_invocation
    
    def is_failed(self):
        if self.last_invocation is None:
            raise NotExecutedYet()
        e = self.last_invocation.get_last_exception()
        return e is not None
    
    def failed_before_execution(self, excep):
        # 実行前に起きたエラーを記録する
        invocation = ProcessInvocation()
        invocation.initerror(excep)
        self.last_invocation = invocation

    #
    # スレッド
    #
    def is_running(self):
        return self.thread and self.thread.is_alive()

    def join(self):
        if self.is_running():
            self.thread.join()
    
    def tell_interruption(self):
        self.stop_flag = True
    
    def is_interrupted(self):
        return self.stop_flag
    
    def test_thread_ident(self, ident):
        return self.thread.ident == ident

    #
    # メッセージ
    #
    def post_message(self, msg):
        self.post_msgs.put(msg)

    def handle_post_message(self):
        msgs = []
        try:
            while True:
                msg = self.post_msgs.get_nowait()
                msgs.append(msg)
        except queue.Empty:
            pass
        return msgs

    #
    # 入力
    #
    def wait_input(self):
        """
        入力終了イベント発生まで待機する
        """
        self.event_inputend.clear()
        self.input_waiting = True
        self.event_inputend.wait() # 待機...
        self.input_waiting = False
        # 入力されたテキストを取得する
        text = self.last_input
        self.last_input = None
        return text

    def is_waiting_input(self):
        return self.input_waiting
    
    def tell_input_end(self, text):
        """ 
        UIスレッドから呼び出す。
        入力完了を通知する 
        """
        self.last_input = text
        self.event_inputend.set()
    
    #
    #
    #
    def bind_data(self, data):
        self.bound_data = data

    def get_data(self, running=False):
        if not running and self.is_running():
            # 動作中はアクセスできない
            return None
        return self.bound_data
    
#
# プロセスの中断指示
#
class ProcessInterrupted(Exception):
    pass

#
# プロセスのメソッド呼び出しで起こるエラー
#
class NotExecutedYet(Exception):
    pass

class StillExecuting(Exception):
    pass

#
# プロセス実行前に設定されうるエラー
#
class ProcessBadCommand(Exception):
    def __init__(self, target, reason):
        super().__init__(target, reason)

    def get_target(self):
        return super().args[0]
    
    def get_reason(self):
        return super().args[1]

#
# ###################################################################
#  Process Spirit
#  プロセスがアプリケーションにたいし使用するコントローラー
# ###################################################################
#
class _spirit_msgmethod():
    # メッセージ関数
    class functor():
        def __init__(self, fn, spirit):
            self.fn = fn
            self.spirit = spirit

        def __call__(self, *args, **kwargs):
            m = self.fn(self.spirit, *args, **kwargs)
            self.spirit.post_message(m)
            return None
        
        def msg(self, *args, **kwargs):
            m = self.fn(self.spirit, *args, **kwargs)
            return m

    def __init__(self, fn):
        self.fn = fn
    
    def __get__(self, obj, objtype=None):
        return _spirit_msgmethod.functor(self.fn, obj)

#
#
#
class Spirit():
    def __init__(self, app, process=None):
        self.app = app
        self.process = process
        # プログレスバー        
        self.cur_prog_display = None 
    
    def inherit(self, other):
        self.app = other.app
        self.process = other.process

    def get_app(self):
        return self.app
    
    def get_app_ui(self):
        return self.app.get_ui()
    
    def bind_process(self, process):
        self.process = process

    #
    # メッセージ出力
    #
    # プロセススレッド側からメッセージを投稿
    def post_message(self, msg):
        if self.process is None:
            print("discarded message:", msg.text)
            return
        self.process.post_message(msg)
    
    @_spirit_msgmethod
    def message(self, msg, **options):
        return ProcessMessage(msg, "message", **options)
        
    # 重要
    @_spirit_msgmethod
    def message_em(self, msg, **options):
        return ProcessMessage(msg, "message_em", **options)
        
    # エラー
    @_spirit_msgmethod
    def error(self, msg, **options):
        return ProcessMessage(msg, "error", **options)
        
    # 警告
    @_spirit_msgmethod
    def warn(self, msg, **options):
        return ProcessMessage(msg, "warn", **options)

    # リンクを貼る
    @_spirit_msgmethod
    def hyperlink(self, msg, link=None, linktag=None, label=None, **options):
        return ProcessMessage(msg, "hyperlink", link=link, linktag=linktag, label=label, **options)
    
    @_spirit_msgmethod
    def custom_message(self, tag, msg, **options):
        return ProcessMessage(msg, tag, **options)

    @_spirit_msgmethod
    def delete_message(self, line=None, count=None):
        return ProcessMessage(tag="delete-message", count=count, line=line)
    
    @_spirit_msgmethod
    def dataview(self):
        return ProcessMessage(tag="dataview")
    
    def canvas(self, name, width, height, color=None):
        return ProcessScreenCanvas(self, name, width, height, color)

    # ファイル対象に使用するとよい...
    def print_target(self, target):
        self.message_em('対象 --> [{}]'.format(target))

    #
    def message_io(self, tag="message", *, oneliner=False, **options):
        return ProcessMessageIO(self, tag, oneliner, **options)
    
    #
    # UIの動作を命じる
    #
    def ask_yesno(self, desc):
        answer = self.app.get_ui().get_input(desc)
        return test_yesno(answer)
    
    def get_input(self, desc=""):
        return self.app.get_ui().get_input(self, desc)
    
    def wait_input(self):
        if self.process is None:
            return None
        return self.process.wait_input()
    
    def scroll_screen(self, index):
        self.app.get_ui().scroll_screen(index)
    
    def ask_openfilename(self, **kwargs):
        return self.app.get_ui().openfilename_dialog(**kwargs)
    
    def ask_opendirname(self, **kwargs):
        return self.app.get_ui().opendirname_dialog(**kwargs)

    #
    # スレッド操作／プログレスバー操作
    #
    # プロセススレッド側で中断指示を確認する
    def interruption_point(self, *, nowait=False, progress=None, noexception=False):
        if self.process and self.process.is_interrupted():
            if not noexception:
                raise ProcessInterrupted()
            return False
        if not nowait:
            time.sleep(0.05)
        if progress and self.cur_prog_bar:
            self.cur_prog_bar.update(progress)
        return True
    
    def raise_interruption(self):
        raise ProcessInterrupted()

    # プログレスバーを開始する
    def start_progress_display(self, *, total=None):
        self.cur_prog_bar = MiniProgressDisplay(spirit=self, total=total)

    # プログレスバーを完了した状態にする
    def finish_progress_display(self, total=None):
        if self.cur_prog_bar is None:
            return
        if total:
            self.cur_prog_bar.finish(total)

    #
    # カレントディレクトリ
    #
    def get_current_dir(self):
        return self.app.get_current_dir()

    def change_current_dir(self, path):
        if os.path.isdir(path):
            self.app.set_current_dir(path)
            return True
        else:
            return False
    
    def abspath(self, path):
        # 絶対パスにする
        if not os.path.isabs(path):
            cd = self.app.get_current_dir()
            if cd is None:
                cd = os.getcwd()
            path = os.path.normpath(os.path.join(cd, path))
        return path
    
    #
    #
    #
    def bind_data(self, dataview):
        if self.process is None:
            raise ValueError("no process to be bound dataset exists")
        self.process.bind_data(dataview)
    
    def create_data(self, datas, *command_args, **command_kwargs):
        dataview = DataViewFactory(datas, *command_args, **command_kwargs)
        self.bind_data(dataview)
        return dataview

    #
    def select_process_chamber(self, index=None):
        return self.app.select_chamber(index)

#
#
#
class TempSpirit(Spirit):
    def __init__(self, app=None, cd=None):
        super().__init__(app, process=None)
        self.msgs = []
        self.cd = cd

    def bind_process(self, p):
        pass

    def post_message(self, msg):
        if msg.is_embeded():
            for m in msg.expand():
                self.msgs.append(m)
        else:
            self.msgs.append(msg)
    
    def printout(self):
        for msg in self.msgs:
            kwargs = str(msg.kwargs) if msg.kwargs else ""
            print("[{}]{} {}".format(msg.tag, msg.text, kwargs))
    
    def get(self):
        return self.msgs
        
    #
    # カレントディレクトリ
    #
    def get_current_dir(self):
        return self.cd

    def change_current_dir(self, path):
        if os.path.isdir(path):
            self.cd = path
            return True
        else:
            return False
    
    def abspath(self, path):
        # 絶対パスにする
        if not os.path.isabs(path):
            cd = self.cd
            if cd is None:
                cd = os.getcwd()
            path = os.path.normpath(os.path.join(cd, path))
        return path
    
#
#  メッセージクラス
#
class ProcessMessage():
    def __init__(self, text=None, tag="message", embed=None, **kwargs):
        self.text = text
        self.tag = tag
        self.embed_ = embed or []
        self.kwargs = kwargs

    def argument(self, name, default=None):
        return self.kwargs.get(name, default)

    def set_argument(self, name, value):
        self.kwargs[name] = value
    
    def get_text(self):
        return str(self.text)
    
    def get_hyperlink_link(self):
        l = self.kwargs.get("link")
        if l is not None:
            return l
        return self.text
    
    def get_hyperlink_label(self):
        return self.kwargs.get("label")
    
    def is_embeded(self):
        return len(self.embed_) > 0
    
    def embed(self, *args, **kwargs):
        self.embed_.append(ProcessMessage(*args, **kwargs))
        return self

    def expand(self):
        if self.text is None:
            raise ValueError("Attempt to print bad message text : tag={}".format(self.tag))
        else:
            self.text = str(self.text)

        def partmsg(msg=None, text=None, withbreak=False):
            if text is not None:
                msg = ProcessMessage(text, self.tag, None, **self.kwargs)
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
                    emsg = self.embed_[int(lastkey)-1]
                    if emsg is not None:
                        expanded.append(partmsg(text=lasttext))
                        expanded.append(partmsg(emsg))
                        lasttext = ""
                    lastkey = ""
                    state = 0
            elif state == 1 or state == 2:
                lastkey += ch
                state = 2
            else:
                lasttext += ch
            
        expanded.append(partmsg(text=lasttext, withbreak=True))
        return expanded

#
#
#
class ProcessMessageIO():
    def __init__(self, spirit, tag, oneliner, **options):
        self.spirit = spirit
        self.tag = tag
        self.oneliner = oneliner
        self.options = options
        self.linecnt = 0
    
    def write(self, msg):
        if self.oneliner and self.linecnt == 1:
            #self.spirit.delete_message_line()
            self.linecnt = 0
        self.spirit.custom_message(self.tag, msg, **self.options)
        self.linecnt += 1
    
    def flush(self):
        pass

    def truncate(self, size=None):
        return size
    
    def seekable(self):
        return False

    def writable(self):
        return True

    def readable(self):
        return False
    
    def close(self):
        pass
    
    def closed(self):
        return False

#
#
#
class ProcessScreenCanvas():
    def __init__(self, spi, name, width, height, color=None):
        self.spirit = spi
        self.graphs = []
        self.name = name
        self.bg = color
        self.width = width
        self.height = height

    def __enter__(self):
        return self
    
    def __exit__(self, et, ev, tb):
        self.post()
        return None
    
    def post(self):
        self.spirit.post_message(ProcessMessage(tag="canvas", canvas=self))
    
    def get_graphs(self) -> List[Tuple[str, Dict[str, Any]]]:
        return self.graphs
    
    def add_graph(self, typename, **kwargs):
        self.graphs.append((typename, kwargs))
        
    def rectangle_frame(self, *, coord=None, width=None, color=None, dash=None, stipple=None):
        self.add_graph("rectangle-frame", coord=coord, width=width, color=color, dash=dash, stipple=stipple)
        
    def rectangle(self, *, coord=None, color=None, dash=None, stipple=None):
        self.add_graph("rectangle", coord=coord, color=color, dash=dash, stipple=stipple)

    def oval(self, *, coord=None, color=None, dash=None, stipple=None):
        self.add_graph("oval", coord=coord, color=color, dash=dash, stipple=stipple)


#
# #####################################################################
#  スクリーン
# #####################################################################
#
# プロセスの動作を表示する
#
class ProcessChamber:
    def __init__(self, index, process):
        self.index = index
        self.process = process
        self.handled_msgs = []
        
    def is_failed(self):
        return self.process.is_failed()
    
    def is_running(self):
        return self.process.is_running()
    
    def join(self):
        self.process.join()
    
    def is_interrupted(self):
        return self.process.stop_flag

    def interrupt(self):
        if self.process.is_waiting_input():
            self.process.tell_input_end("")
        self.process.tell_interruption()

    def is_waiting_input(self):
        return self.process.is_waiting_input()
    
    def finish_input(self, text):
        self.process.tell_input_end(text)

    def handle_message(self):
        msgs = self.process.handle_post_message()
        self.handled_msgs.extend(msgs)
        return msgs

    def get_message(self):
        return self.handled_msgs
    
    def get_command(self):
        return self.process.get_command_string()
    
    def get_process(self):
        return self.process
    
    # ヌルの可能性あり
    def get_bound_spirit(self):
        return self.process.get_spirit()
    
    # ヌルの可能性あり
    def get_bound_data(self, running=False):
        return self.process.get_data(running=running)

    def get_index(self):
        return self.index

#
#
#
class ProcessHive:
    def __init__(self):
        self.chambers = []
        self.active = None
        self.prevactive = None
    
    def run(self, app):
        cha = self.get_active()
        p = cha.get_process()
        p.run(app)

    def execute(self, app):
        cha = self.get_active()
        p = cha.get_process()
        app.execute_process(p)

    # 新しいチャンバーを作成し、アクティブにして返す
    def new_activate(self, process):
        newindex = len(self.chambers)
        scr = ProcessChamber(newindex, process)
        self.chambers.append(scr)
        self.set_active_index(newindex) # アクティブにする
        return scr
    
    # 既存のチャンバーをアクティブにして返す
    def activate(self, index):
        if self.set_active_index(index):
            return self.chambers[index]
        return None

    def count(self):
        return len(self.chambers)
    
    def get(self, index):
        return self.chambers[index]
    
    def set_active_index(self, index):
        if 0<=index and index<len(self.chambers):
            self.prevactive = self.active
            self.active = index
            return True
        return False

    def get_active_index(self):
        return self.active

    def get_active(self):
        if self.active is not None:
            return self.chambers[self.active]
    
    def get_previous_active(self):
        if self.prevactive is not None:
            return self.chambers[self.prevactive]

    def get_chambers(self):
        return self.chambers

    #
    #
    #
    def get_runnings(self):
        return [x for x in self.chambers if x.is_running()]

    def stop(self):
        for cha in self.get_runnings():
            cha.interrupt()
        for cha in self.get_runnings():
            cha.join()

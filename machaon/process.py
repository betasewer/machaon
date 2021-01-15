#!/usr/bin/env python3
# coding: utf-8
import os
import sys
import threading
import queue
import time
import traceback
import datetime
from typing import Sequence, Optional, List, Dict, Any, Tuple, Set, Generator, Union

#from machaon.action import ActionInvocation
from machaon.core.object import Object, ObjectCollection
from machaon.core.message import MessageEngine, MessageError
from machaon.core.invocation import InvocationContext
from machaon.cui import collapse_text, test_yesno, MiniProgressDisplay, composit_text

#
# ######################################################################
# プロセスの実行
# ######################################################################
#
# スレッドの実行、停止、操作を行う 
#
class Process:
    def __init__(self, index, message):
        self.index: int = index
        # 
        self.message: MessageEngine = message
        self.routine = None
        self._finished = False
        # スレッド
        self.state = {}
        self.thread = None
        self._interrupted = False
        self.last_context = None
        # メッセージ
        self.post_msgs = queue.Queue()
        # 入力
        self.input_waiting = False
        self.event_inputend = threading.Event()
        self.last_input = None

    #
    #
    # プロセスの実行フロー
    #
    #
    def start_process(self, root):
        # メインスレッドへの伝達者
        spirit = Spirit(root, self)

        # 実行開始
        timestamp = datetime.datetime.now()
        spirit.post("on-exec-process", "begin", spirit=spirit, process=self, timestamp=timestamp)

        # オブジェクトを取得
        inputobjs = root.select_object_collection()

        # コマンドを解析
        context = InvocationContext(
            input_objects=inputobjs, 
            type_module=root.get_type_module(),
            spirit=spirit
        )
        self.last_context = context
        msgroutine = self.message.runner(context, log=False)

        # 実行開始
        for nextmsg in msgroutine:
            if nextmsg.is_task():
                # 非同期実行へ移行する
                self.thread = threading.Thread(
                    target=self.run_process_async, 
                    args=(context, msgroutine), 
                    daemon=True
                )
                self._interrupted = False
                self.thread.start()
                return
        
        # 同期実行の終わり
        self.on_finish_process(context)

    # メッセージ実行後のフロー
    def on_finish_process(self, context):
        # 実行時に発生した例外を確認する
        excep = context.get_last_exception()
        if excep is None:
            # 返り値をオブジェクトとして配置する
            returns = context.clear_local_objects()
            ret = returns[0] if returns else None
            if ret:
                context.push_object(str(self.index), ret)
            context.spirit.post("on-exec-process", "success", process=self, ret=ret, context=context)
            success = True
        elif isinstance(excep, ProcessInterrupted):
            context.spirit.post("on-exec-process", "interrupted", process=self)
            success = False
        else:
            error = context.new_type(ProcessError).new_object(ProcessError(self, excep))
            context.push_object(str(self.index), error)
            context.spirit.post("on-exec-process", "error", process=self, error=error)
            success = False

        # プロセス終了
        self.finish()
        return success

    def run_process_async(self, context, routine=None):
        self.message.run(context, runner=routine)
        self.on_finish_process(context)
    
    # プロセスID
    def get_index(self):
        return self.index

    # 紐づけられた実行中／実行済みコンテキスト
    def get_last_invocation_context(self):
        return self.last_context
    
    #
    # スレッド
    #
    def is_running(self):
        return self.thread and self.thread.is_alive()

    def join(self, timeout=None):
        if self.is_running():
            self.thread.join(timeout=timeout)
    
    def tell_interruption(self):
        """ ワーカースレッドから停止を伝える """
        self._interrupted = True
    
    def is_interrupted(self):
        """ メインスレッドで停止を確認する """
        return self._interrupted
    
    def get_thread_ident(self):
        return self.thread.ident
    
    # 動作が終わっているか（未開始の場合は真）
    def is_finished(self):
        return self._finished
        
    def finish(self):
        self._finished = True

    # 一度でも失敗したか（未開始の場合は偽）
    def is_failed(self):
        if self.last_context:
            return self.last_context.is_failed()
        return False

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
        """ ワーカースレッドで入力終了イベント発生まで待機する """
        self.event_inputend.clear()
        self.input_waiting = True
        self.event_inputend.wait() # 待機...
        self.input_waiting = False
        # 入力されたテキストを取得する
        text = self.last_input
        self.last_input = None
        return text

    def is_waiting_input(self):
        """ メインスレッドで入力待ちか確認する """
        return self.input_waiting
    
    def tell_input_end(self, text):
        """ メインスレッドから入力完了を通知する """
        self.last_input = text
        self.event_inputend.set()

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
# ###################################################################
#  Process Spirit
#  プロセスがアプリケーションにたいし使用するコントローラー
# ###################################################################
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
    
    def get_process(self):
        return self.process

    #
    # メッセージ出力
    #
    # プロセススレッド側からメッセージを投稿
    def post_message(self, msg):
        if self.process is None:
            print("discarded message:", msg.text)
            return
        self.process.post_message(msg)
    
    def post(self, tag, value=None, **options):
        """ メッセージを共同キューに入れる。
        message: value, **commonoptions
        message-em: (same)
        warn: (same)
        error: (same)
        hyperlink: value, *, link, linktag, label
        delete-message: line, count
        object-view: object
        canvas: *, name, width, height, color
        """
        self.post_message(ProcessMessage(value, tag, **options))
    
    def message(self, tag, value=None, **options):
        return ProcessMessage(value, tag, **options)

    # ファイル対象に使用するとよい...
    def print_target(self, target):
        self.post("message-em", '対象 --> [{}]'.format(target))

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
class TempSpirit(Spirit):
    def __init__(self, app=None, cd=None):
        super().__init__(app, process=None)
        self.msgs = []
        self.cd = cd

    def post_message(self, msg):
        if msg.is_embeded():
            for m in msg.expand():
                self.msgs.append(m)
        else:
            self.msgs.append(msg)
    
    def printout(self):
        for msg in self.msgs:
            kwargs = str(msg.args) if msg.args else ""
            print("[{}]{} {}".format(msg.tag, msg.text, kwargs))
        self.msgs.clear()
    
    def get_message(self):
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

    # プログレスバーの更新のみを行う
    def interruption_point(self, *, nowait=False, progress=None, noexception=False):
        if progress and self.cur_prog_bar:
            self.cur_prog_bar.update(progress)
        return True
    
#
#  メッセージクラス
#
class ProcessMessage():
    def __init__(self, text=None, tag="message", embed=None, **args):
        self.text = text
        self.tag = tag
        self.embed_ = embed or []
        self.args = args

    def argument(self, name, default=None):
        return self.args.get(name, default)

    def set_argument(self, name, value):
        self.args[name] = value
    
    def get_text(self) -> str:
        return str(self.text)
    
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
                msg = ProcessMessage(text, self.tag, None, **self.args)
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

    def text(self, *, coord=None, text=None, color=None):
        self.add_graph("text", coord=coord, text=text, color=color)

#
# #####################################################################
#  スクリーン
# #####################################################################
#
# プロセスの動作を表示する
#
class ProcessChamber:
    def __init__(self, index):
        self._index = index
        self._prlist = []
        self.prelude_msgs = []
        self.handled_msgs = []
    
    def add(self, process):
        if self._prlist and not self.last_process.is_finished():
            return
        self._prlist.append(process)
    
    def add_prelude_messages(self, messages):
        self.prelude_msgs.extend(messages)
    
    @property
    def last_process(self):
        if not self._prlist:
            raise ValueError("No process")
        return self._prlist[-1]
    
    def is_empty(self):
        return not self._prlist
    
    def is_failed(self):
        if not self._prlist:
            return False
        return self.last_process.is_failed()
    
    def is_finished(self):
        if not self._prlist:
            return True
        return self.last_process.is_finished()
    
    def is_interrupted(self):
        if not self._prlist:
            return False
        return self.last_process.is_interrupted()

    def interrupt(self): 
        if not self._prlist:
            return
        if self.last_process.is_waiting_input():
            self.last_process.tell_input_end("")
        self.last_process.tell_interruption()

    def is_waiting_input(self): # -
        if not self._prlist:
            return False
        return self.last_process.is_waiting_input()
    
    def finish_input(self, text): # -
        if not self._prlist:
            return
        self.last_process.tell_input_end(text)
        
    def join(self, timeout):
        if not self._prlist:
            return
        self.last_process.join(timeout=timeout)
    
    def handle_process_messages(self):
        if not self._prlist:
            msgs = self.prelude_msgs
        else:
            msgs = self.last_process.handle_post_message()
        self.handled_msgs.extend(msgs)
        return msgs

    def get_process_messages(self): # -
        return self.handled_msgs
    
    def add_initial_prompt(self, prompt):
        self.prelude_msgs.append(ProcessMessage(prompt, tag="message-em", nobreak=True))
    
    def get_title(self): # -
        title = "Chamber"
        title = "{}. {}".format(self._index, title)
        return title
    
    def get_last_object_message(self):
        return self.last_process.message
    
    def get_last_context(self): # -
        return self.last_process.get_invocation_context()

    def get_index(self): # -
        return self._index

    def get_last_process_index(self): # -
        return self.last_process.get_index()
    
    def get_input_string(self):
        if not self._prlist:
            return ""
        return self.last_process.message.source

#
#
#
class DesktopChamber():
    def __init__(self, name, index):
        self._index = index
        self._name = name
        self._objcol = ObjectCollection()
        self._msgs = []
    
    def get_objects(self):
        return self._objcol

    def get_index(self): # -
        return self._index
    
    def is_finished(self):
        return True
    
    def is_failed(self):
        return False
        
    def is_waiting_input(self): # -
        return False

    def handle_process_messages(self):
        return []

    def get_process_messages(self): #
        msgs = []
        for item in self._objcol.pick_all():
            msg = ProcessMessage(object=item.object, deskname=self._index, tag="object-summary", sel=item.selected)
            msgs.append(msg)
        return msgs

    def get_title(self): # -
        title = "机{}. {}".format(self._index+1, self._name)
        return title
    
    def get_input_string(self):
        return ""

#
#
#
class ProcessHive:
    def __init__(self):
        self.chambers: Dict[int, Union[ProcessChamber,DesktopChamber]] = {}
        self._allhistory: List[int] = []
        self._nextindex: int = 0
        self._nextprocindex: int = 0
    
    # 新しい開始前のプロセスを作成する
    def new_process(self, expression: str):
        procindex = self._nextprocindex + 1
        message = MessageEngine(expression)
        process = Process(procindex, message)
        self._nextprocindex = procindex
        return process

    # 既存のチャンバーに追記する
    def append_to_active(self, process) -> ProcessChamber:
        chamber = self.get_active()
        chamber.add(process)
        return chamber

    # 新しいチャンバーを作成して返す
    def addnew(self, initial_prompt=None):
        newindex = self._nextindex
        chamber = ProcessChamber(newindex)
        if initial_prompt:
            chamber.add_initial_prompt(initial_prompt)
        self.chambers[newindex] = chamber
        self._nextindex += 1
        self.activate(newindex)
        return chamber

    def addnew_desktop(self, name: str, *, activate=True) -> DesktopChamber:
        newindex = self._nextindex
        chamber = DesktopChamber(name, newindex)
        self.chambers[newindex] = chamber
        self._nextindex += 1
        self.activate(newindex)
        return chamber
    
    # 既存のチャンバーをアクティブにする
    def activate(self, index: int) -> bool:
        if index in self.chambers:
            self._allhistory.append(index)
            return True
        return False
    
    def rhistory(self):
        return (i for i in reversed(self._allhistory) if i in self.chambers)

    def get_active_index(self):
        return next(self.rhistory(), None)

    def get_active(self):
        ac = next(self.rhistory(), None)
        if ac is not None:
            return self.chambers[ac]
        return None
    
    def get_previous_active(self):
        vs = self.rhistory()
        next(vs, None)
        ac = next(vs, None)
        if ac is not None:
            return self.chambers[ac]
        return None
    
    def get_last_active_desktop(self):
        for index in self.rhistory():
            chm = self.chambers[index]
            if isinstance(chm, DesktopChamber):
                return chm
        return None

    #
    def count(self):
        return len(self.chambers)
    
    def get(self, index):
        return self.chambers.get(index)
    
    def get_chambers(self):
        return self.chambers.values()

    def remove(self, index=None):
        if index is None: 
            index = self.get_active_index()

        if index not in self.chambers:
            raise KeyError(index)
        
        del self.chambers[index]
    
    # 隣接する有効なチャンバーのインデックス
    def next_indices(self, start:int=None, d:int=1) -> Generator[int, None, None]:
        beg = self.get_active_index() if start is None else start
        i = beg
        imax = max([*self.chambers.keys(), 0])
        while True:
            while i == beg or i not in self.chambers:
                i += d
                if i<0 or imax<i:
                    return None
            yield i
            beg = i
        
    def get_next_index(self, index=None, *, delta=1) -> Optional[int]:
        g = self.next_indices(index, +1 if delta>=0 else -1)
        i = None
        for _ in range(abs(delta)):
            i = next(g, None)
        return i

    #
    #
    #
    def get_runnings(self):
        return [x for x in self.chambers.values() if not x.is_finished()]

    def interrupt_all(self):
        for cha in self.get_runnings():
            cha.interrupt()

#
#
#
class ProcessError():
    """@type
    プロセスの実行時に起きたエラー。
    Typename: ProcessError
    """
    def __init__(self, process, error):
        self.error = error
        self.process = process
    
    def get_error_typename(self):
        if isinstance(self.error, MessageError):
            err = self.error.error
        else:
            err = self.error
        return err.__class__.__name__

    def summarize(self):
        if isinstance(self.error, MessageError):
            error = self.error.error
            return "文法エラー：{}".format(str(error))
        else:
            error = self.error
            return "実行エラー：{}".format(str(error))

    def pprint(self, app):
        if isinstance(self.error, MessageError):
            error = self.error.error
            errortype = traceback.format_exception_only(type(error), error)
            app.post("error", errortype[0] if errortype else "")
            app.post("message-em", "メッセージ解決：")
            self.error.message.pprint_log(lambda x: app.post("message", x))
        else:
            excep = self.error
            details = traceback.format_exception(type(excep), excep, excep.__traceback__)
            app.post("error", details[-1] if details else "")
            app.post("message-em", "スタックトレース：")
            app.post("message", "".join(details[1:-1]) + "\n")
            app.post("message-em", "メッセージ解決：")
            self.process.message.pprint_log(lambda x: app.post("message", x))




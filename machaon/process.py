#!/usr/bin/env python3
# coding: utf-8
import inspect
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
from machaon.core.message import MessageEngine, InternalMessageError
from machaon.core.invocation import InvocationContext
from machaon.cui import collapse_text, test_yesno, MiniProgressDisplay, composit_text
from machaon.core.symbol import full_qualified_name


class Process:
    """
    プロセスの開始、スレッドの実行、停止、操作を行う 
    """
    def __init__(self, index, message):
        self.index: int = index
        # 
        self.message: MessageEngine = message
        self.routine = None
        self._finished = False
        # スレッド
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
        spirit.post("on-exec-process", "begin", spirit=spirit, timestamp=timestamp)

        # オブジェクトを取得
        inputobjs = root.select_object_collection()

        # コマンドを解析
        context = InvocationContext(
            input_objects=inputobjs, 
            type_module=root.get_type_module(),
            spirit=spirit
        )
        self.last_context = context
        msgroutine = self.message.runner(context)

        # 実行開始
        for nextmsg in msgroutine:
            if nextmsg.is_task():
                # 非同期実行へ移行する
                self.thread = threading.Thread(
                    target=self.run_process_async, 
                    args=(context, msgroutine), 
                    name="Process{}_Worker".format(self.index),
                    daemon=True
                )
                self._interrupted = False
                self.thread.start()
                return

        # 同期実行の終わり
        self.on_finish_process(context)

    # メッセージ実行後のフロー
    def on_finish_process(self, context):
        # 返り値をオブジェクトとして配置する
        ret = self.message.finish(context)
        context.push_object(str(self.index), ret)
        
        # 実行時に発生した例外を確認する
        excep = context.get_last_exception()
        if excep is None:
            context.spirit.post("on-exec-process", "success", ret=ret, context=context)
            success = True
        elif isinstance(excep, ProcessInterrupted):
            context.spirit.post("on-exec-process", "interrupted")
            success = False
        else:
            context.spirit.post("on-exec-process", "error", error=ret)
            success = False

        # プロセス終了
        self.finish()
        return success

    def run_process_async(self, context, routine):
        for _ in routine: pass # 残りの処理を全て実行する
        self.on_finish_process(context)
    
    def get_index(self):
        """ @method alias-name [index]
        プロセス番号を得る。
        Returns:
            Int:
        """
        return self.index

    def get_last_invocation_context(self):
        """ @method alias-name [context]
        紐づけられた実行中／実行済みコンテキストを得る。
        Returns:
            Context:
        """
        return self.last_context
    
    #
    # スレッド
    #
    def is_running(self):
        """ @method
        スレッドが実行中か
        Returns:
            bool:
        """
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
    
    def is_finished(self):
        """ @method
        作業が終わっているか。未開始の場合も真
        Returns:
            bool:
        """
        return self._finished
        
    def finish(self):
        self._finished = True

    def is_failed(self):
        """ @method
        一度でも失敗したか。未開始の場合は偽
        Returns:
            bool:
        """
        if self.last_context:
            return self.last_context.is_failed()
        return False

    def _start_infinite_thread(self, spirit):
        """ テスト用の終わらないスレッドを開始する """
        def body(spi):
            while spi.interruption_point(nowait=True):
                time.sleep(0.1)
            
        self.thread = threading.Thread(
            target=body, 
            args=(spirit,), 
            name="Process{}_Infinite".format(self.index),
            daemon=True
        )
        self._interrupted = False
        self.thread.start()

    #
    # メッセージ
    #
    def post_message(self, msg):
        msg.set_argument("process", self.index) # プロセスを紐づける
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
    def __init__(self, root, process=None):
        self.root = root
        self.process = process
        # プログレスバー
        self.cur_prog_display = None 
    
    def inherit(self, other):
        self.root = other.root
        self.process = other.process

    def get_root(self):
        return self.root
    
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

    def message_io(self, tag="message", *, oneliner=False, **options):
        return ProcessMessageIO(self, tag, oneliner, **options)
    
    #
    # UIの関数を呼び出す
    #
    def get_ui(self):
        return self.root.get_ui()
    
    def ask_yesno(self, desc):
        answer = self.get_ui().get_input(desc)
        return test_yesno(answer)
    
    def get_input(self, desc=""):
        return self.get_ui().get_input(self, desc)
    
    def wait_input(self):
        if self.process is None:
            return None
        return self.process.wait_input()
    
    def scroll_screen(self, index):
        self.get_ui().scroll_screen(index)
    
    def open_pathdialog(self, dialogtype, 
        initialdir=None, initialfile=None, 
        filters=None, title=None, 
        multiple=False, 
        defaultextension=None,
        mustexist=False
    ):
        """ uiのダイアログ関数を呼び出す """
        return self.get_ui().open_pathdialog(
            dialogtype,
            initialdir=initialdir, initialfile=initialfile,
            filters=filters, title=title, 
            multiple=multiple,
            defaultextension=defaultextension,
            mustexist=mustexist
        )
    
    def get_ui_wrap_width(self):
        if self.root is None:
            return 0xFFFFFF
        return self.get_ui().wrap_width
    
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
    
    def is_interrupted(self):
        return self.process and self.process.is_interrupted()

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
    # 基本型へのショートカット
    #
    def path(self, p):
        """ ファイルパス操作オブジェクト """
        from machaon.types.shell import Path
        return Path(p)

    def open_input_stream(self, target, binary=False, encoding=None):
        """ 読み込みストリームを返す """
        from machaon.types.fundamental import InputStream
        return InputStream(target).open(binary, encoding)
    
    def open_output_stream(self, target, binary=False, encoding=None):
        """ 書き込みストリームを返す """
        from machaon.types.fundamental import OutputStream
        return OutputStream(target).open(binary, encoding)

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
        self._processes = {}
        self.prelude_msgs = []
        self.handled_msgs = []
    
    def add(self, process):
        if self._processes and not self.last_process.is_finished():
            raise ValueError("稼働中のプロセスが存在します")
        i = process.get_index()
        self._processes[i] = process
        return process
    
    def add_prelude_messages(self, messages):
        self.prelude_msgs.extend(messages)
    
    @property
    def last_process(self):
        if not self._processes:
            raise ValueError("No process")
        maxkey = max(self._processes.keys())
        return self._processes[maxkey]
    
    def is_empty(self):
        return not self._processes
    
    def is_failed(self):
        if not self._processes:
            return False
        return self.last_process.is_failed()
    
    def is_finished(self):
        if not self._processes:
            return True
        return self.last_process.is_finished()
    
    def is_interrupted(self):
        if not self._processes:
            return False
        return self.last_process.is_interrupted()

    def interrupt(self): 
        if not self._processes:
            return
        if self.last_process.is_waiting_input():
            self.last_process.tell_input_end("")
        self.last_process.tell_interruption()

    def is_waiting_input(self): # -
        if not self._processes:
            return False
        return self.last_process.is_waiting_input()
    
    def finish_input(self, text): # -
        if not self._processes:
            return
        self.last_process.tell_input_end(text)
        
    def join(self, timeout):
        if not self._processes:
            return
        self.last_process.join(timeout=timeout)
    
    def get_process(self, index):
        return self._processes.get(index, None)
    
    def get_processes(self):
        return [self._processes[x] for x in sorted(self._processes.keys())]
    
    def handle_process_messages(self):
        if not self._processes:
            msgs = self.prelude_msgs
        else:
            msgs = self.last_process.handle_post_message()
        self.handled_msgs.extend(msgs)
        return msgs

    def get_process_messages(self): # -
        return self.handled_msgs
    
    def add_initial_prompt(self, *args, **kwargs):
        self.prelude_msgs.append(ProcessMessage(*args, **kwargs))
    
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

    def get_input_string(self):
        if not self._processes:
            return ""
        return self.last_process.message.source
    
    def drop_processes(self, pred=None):
        """
        プロセスとプロセスに関連するメッセージを削除する。
        Params:
            *pred(callable): プロセスを判定する関数 
        """
        # メッセージの削除
        piset = {}
        end = None
        reserved_msgs = []
        for mi, msg in enumerate(self.handled_msgs):
            pi = msg.argument("process")
            if pi is None:
                deletes = False # プロセスが関連付けられていないなら削除しない
            elif pi not in piset:
                pr = self._processes[pi]
                if pr.is_running():
                    end = mi
                    break
                deletes = pred(pr) if pred else True
                piset[pi] = deletes
            else:
                deletes = piset[pi]
            if not deletes:
                reserved_msgs.append(msg)
        del self.handled_msgs[0:end]
        self.handled_msgs = reserved_msgs + self.handled_msgs
        # プロセスの削除
        for pi in [x for x,t in piset.items() if t]:
            del self._processes[pi]



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
            chamber.add_initial_prompt(initial_prompt, tag="message-em", nobreak=True)
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
    """
    プロセスの実行時に起きたエラー。
    """
    def __init__(self, context, error):
        self.error = error
        self.context = context
    
    def get_error(self):
        if isinstance(self.error, InternalMessageError):
            return self.error.error
        else:
            return self.error
    
    def get_error_typename(self):
        """ @method alias-name [error_typename]
        例外の型名。
        Returns:
            Str:
        """
        err = self.get_error()
        return err.__class__.__name__
    
    def local(self, level, name):
        """ @method 
        トレースバックから変数にアクセスする。
        Params:
            level(int): トレースバックの深度
            name(str): 変数名
        Returns:
            Any:
        """
        err = self.get_error()
        return get_local_from_traceback(err, level, name)
    
    def location(self, level):
        """ @method
        エラーの発生個所を得る。
        Params:
            level(int): トレースバックの深度
        Returns:
            TextPath:
        """
        err = self.get_error()
        fpath, line = get_location_from_traceback(err, level)
        return fpath, line
    
    def get_context(self):
        """ @method alias-name [context]
        関連づけられたコンテキストを得る。
        Returns:
            Context:
        """
        return self.context

    def constructor(self, context, value):
        """ @meta 
        例外オブジェクトからの変換をサポート
        """
        if isinstance(value, Exception):
            return ProcessError(context, value)
        else:
            raise TypeError(repr(value))

    def summarize(self):
        """ @meta """
        if isinstance(self.error, InternalMessageError):
            error = self.error.error
            return "文法エラー：{}[{}]".format(str(error), self.get_error_typename())
        else:
            error = self.error
            return "実行エラー：{}[{}]".format(str(error), self.get_error_typename())

    def pprint(self, app):
        """ @meta """
        if isinstance(self.error, InternalMessageError):
            excep = self.error.error
            title = "（内部エラー）"
        else:
            excep = self.error
            title = ""
        
        details = traceback.format_exception(type(excep), excep, excep.__traceback__)
        app.post("error", details[-1] if details else "")
        app.post("message-em", "スタックトレース{}：".format(title))

        msg = verbose_display_traceback(excep, app.get_ui_wrap_width())
        app.post("message", msg + "\n")

        app.post("message-em", "メッセージ解決：")
        self.context.pprint_log_as_message(app)


def walk_traceback(exception):
    # 子のエラーのトレースバックにも自動的に遡行
    def next_nested_traceback(exc):
        if hasattr(exc, "child_exception"):
            e = exc.child_exception()
            if e:
                return e.__traceback__, e
        return None, exc

    tb = exception.__traceback__
    if tb is None:
        tb, exception = next_nested_traceback(exception)
    
    level = 0
    while tb:
        yield level, tb, exception
        tb = tb.tb_next
        if tb is None:
            tb, exception = next_nested_traceback(exception)
        level += 1

def goto_traceback(exception, level):
    for l, tb, excep in walk_traceback(exception):
        if level == l:
            return tb, excep
    raise ValueError("トレースバックの深さの限界に到達")

def verbose_display_traceback(exception, linewidth):
    import linecache

    lines = []
    for level, tb, _excep in walk_traceback(exception):
        frame = tb.tb_frame
        filename = frame.f_code.co_filename
        fnname = frame.f_code.co_name
        lineno = tb.tb_lineno
        msg_location = "[{}] {}, {}行目".format(level, filename, lineno)

        msg_line = linecache.getline(filename, lineno).strip()

        indent = "  "
        msg_fn = "{}:".format(fnname)
        msg_locals = []
        localdict = frame.f_locals

        localself = localdict.pop("self", None)
        if localself is not None:
            sig = find_frame_function_signature(localself, fnname)
            if isinstance(sig, Exception):
                msg_fn = "{}(<error: {}>):".format(fnname, sig)
            elif sig is not None:
                msg_fn = "{}{}:".format(fnname, display_parameters(sig))

            msg_locals.append("self = <{}>".format(full_qualified_name(type(localself))))

        for name, value in sorted(localdict.items()):
            try:
                if type(value).__repr__ is object.__repr__:
                    if hasattr(value, "stringify"):
                        val_str = "<{} {}>".format(full_qualified_name(type(value)), value.stringify())
                    else:
                        val_str = "<{}>".format(full_qualified_name(type(value)))
                else:
                    val_str = repr(value)
            except:
                val_str = "<error on __repr__>"
            val_str = collapse_text(val_str, linewidth)
            val_str = val_str.replace('\n', '\n{}'.format(' ' * (len(name) + 2)))
            msg_locals.append("{} = {}".format(name, val_str))

        lines.append(msg_location)
        lines.append(indent + msg_line)
        lines.append(indent + "-" * 30)
        lines.append(indent + msg_fn)
        for line in msg_locals:
            lines.append(indent + indent + line)
        lines.append(indent + "-" * 30)
        lines.append("\n")

    return '\n'.join(lines)

def find_frame_function_signature(selfobj, fnname):
    """ inspect.Signatureを抽出して返す """
    selftype = type(selfobj)
    cfn = getattr(selftype, fnname, None)
    if cfn is None or isinstance(cfn, property): # プロパティをはじく
        return None
    
    fn = getattr(selfobj, fnname, None)
    try:
        return inspect.signature(fn)
    except Exception as e:
        return e

def display_parameters(sig):
    params = ["self"]
    for p in sig.parameters.values():
        if p.default == inspect.Parameter.empty:
            params.append(p.name)
        else:
            params.append("{} = {}".format(p.name, p.default))
    return "({})".format(", ".join(params))


def get_local_from_traceback(exception, level, name):
    """ フレームから変数を取り出す """
    tb, _excep = goto_traceback(exception, level)
    
    frame = tb.tb_frame
    localdict = frame.f_locals
    if name not in localdict:
        raise ValueError("変数'{}'が見つかりません".format(name))
    
    return localdict[name]


def get_location_from_traceback(exception, level):
    """ エラーの起きた行を調べる """
    tb, _excep = goto_traceback(exception, level)
    
    frame = tb.tb_frame
    filename = frame.f_code.co_filename
    lineno = tb.tb_lineno

    return filename, lineno

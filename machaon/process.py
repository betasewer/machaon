#!/usr/bin/env python3
# coding: utf-8
import os
import threading
import queue
import time
import traceback
import datetime
from typing import Sequence, Optional, List, Dict, Any, Tuple, Set, Generator, Union

#from machaon.action import ActionInvocation
from machaon.core.object import Object, ObjectCollection
from machaon.core.message import MessageEngine
from machaon.core.invocation import InvocationContext
from machaon.cui import collapse_text, test_yesno, MiniProgressDisplay, composit_text
from machaon.ui.basic import Launcher


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
        self._isconsumed_msgs = False
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
        launcher = root.get_ui()
        launcher.post_on_exec_process(self, timestamp)

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
            if isinstance(nextmsg, str):
                continue
            elif nextmsg.is_task():
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
        launcher = context.root.get_ui()
        if excep is None:
            # 成功
            launcher.post_on_success_process(self, ret, context.spirit)
            success = True
        elif isinstance(excep, ProcessInterrupted):
            launcher.post_on_interrupt_process(self)
            success = False
        else:
            launcher.post_on_error_process(self, ret)
            success = False
        
        launcher.post_on_end_process(self)

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
        self._isconsumed_msgs = False
        msg.set_argument("process", self.index) # プロセスを紐づける
        if msg.is_embeded():
            for m in msg.expand():
                self.post_msgs.put(m)
        else:
            self.post_msgs.put(msg)

    def post(self, tag, value=None, **options):
        self.post_message(ProcessMessage(value, tag, **options))

    def handle_post_message(self, count=None):
        """ 指定の数だけメッセージを取り出す """
        msgs = []
        try:
            while count is None or len(msgs) < count:
                msg = self.post_msgs.get_nowait()
                msgs.append(msg)
        except queue.Empty:
            self._isconsumed_msgs = True
        return msgs

    def is_messages_consumed(self):
        """ 作業スレッドが終わり、メッセージも全て処理済みなら真 """
        return self.is_finished() and self._isconsumed_msgs
    
    #
    # 入力
    #
    def wait_input(self):
        """ @hidden
        ワーカースレッドで入力終了イベント発生まで待機する 
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
        """ @hidden
        メインスレッドで入力待ちか確認する
        """
        return self.input_waiting
    
    def tell_input_end(self, text):
        """ @hidden
        メインスレッドから入力完了を通知する
        """
        self.last_input = text
        self.event_inputend.set()
    
    #
    #
    #
    def store(self, context, name):
        """ @method context
        フォルダにメッセージを書き出す
        Params:
            name(str): メッセージ名
        """
        from machaon.core.persistence import StoredMessage
        m = StoredMessage.constructor(StoredMessage, context, name)
        message = self.message.get_expression()
        m.write(message)

    #
    #
    #
    def constructor(self, context, value):
        """ @meta 
        Params:
            int|str:
        """
        if isinstance(value, int):
            proc = context.root.find_process(value)
            if proc is None:
                raise ValueError("プロセス'{}'は存在しません".format(value))
            return proc
        elif isinstance(value, str):
            v = int(value)
            return Process.constructor(self, context, v)

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
        self.process: Process = process
        # プログレスバー
        self.cur_prog_display = None 
        self._slp = 0
    
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
        """ @hidden """
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
    def interruption_point(self, *, nowait=False, progress=None, noexception=False, wait=None):
        if self.process and self.process.is_interrupted():
            if not noexception:
                raise ProcessInterrupted()
            return False
        
        if not nowait:
            slp = time.monotonic()
            if slp - self._slp > 0.1:
                time.sleep(0.05)
                self._slp = slp
                #print("slept 0.05 {}".format(slp))
            if wait:
                time.sleep(wait)
                #print("slept {}".format(wait))

        if progress and self.cur_prog_bar:
            self.cur_prog_bar.update(progress)
            if self.cur_prog_bar.is_starting(): 
                time.sleep(0.1) # 初回はバー全体の表示用に待つ
        return True
    
    def raise_interruption(self):
        raise ProcessInterrupted()
    
    def is_interrupted(self):
        return self.process and self.process.is_interrupted()

    # プログレスバーを開始する
    def start_progress_display(self, *, total=None, title=None, tag=None):
        self.cur_prog_bar = MiniProgressDisplay(spirit=self, total=total, tag=tag, title=title)

    # プログレスバーを完了した状態にする
    def finish_progress_display(self, total=None):
        if self.cur_prog_bar is None:
            return
        self.cur_prog_bar.finish(total)
    
    # with文のためのオブジェクトを作る
    def progress_display(self, *, total=None, title=None, tag=None):
        return Spirit.ProgressDisplayScope(self, total, title=title, tag=tag)
    
    class ProgressDisplayScope():
        def __init__(self, spirit, total=None, **kwargs):
            self.spirit = spirit
            self.total = total
            self.kwargs = kwargs
        
        def __enter__(self):
            self.start()
            return self
        
        def __exit__(self, et, ev, tb):
            self.finish()

        def start(self):
            self.spirit.start_progress_display(total=self.total, **self.kwargs)

        def finish(self):
            self.spirit.finish_progress_display(total=self.total)
        
        def set_total(self, total):
            if self.spirit.cur_prog_bar is None:
                return
            self.spirit.cur_prog_bar.set_total(total)
            self.total = total

    #
    # キャンバス
    #
    def new_canvas(self, name, width, height, color=None):
        from machaon.ui.basic import ScreenCanvas
        return ScreenCanvas(name, width, height, color)
    
    #
    # クリップボード
    #
    def clipboard_copy(self, value):
        from machaon.platforms import clipboard
        clipboard().clipboard_copy(value)
        self.post("message", "クリップボードに文字列をコピーしました")

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
    
    def printout(self, *, printer=None):
        if printer is None: printer = print
        for msg in self.msgs:
            kwargs = str(msg.args) if msg.args else ""
            printer("[{}]{} {}".format(msg.tag, msg.text, kwargs))
        self.msgs.clear()
    
    def get_message(self):
        return self.msgs

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

    def __repr__(self):
        parts = []
        parts.append(self.text)
        parts.append(self.args)
        if self.embed_:
            parts.append(self.embed_)
        return "<ProcessMessage {}: {}>".format(self.tag, " ".join([str(x) for x in parts]))

    def argument(self, name, default=None):
        return self.args.get(name, default)

    def req_arguments(self, *names):
        """ 値が存在しない場合は例外を投げる """
        seq = []
        for name in names:
            if name not in self.args:
                raise KeyError("メッセージ'{}'に必須の引数'{}'が存在しません".format(self.tag, name))
            seq.append(self.args[name])
        return seq

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
        self.chamber_msgs = []
        self.handled_msgs = []
    
    def add(self, process):
        if self._processes and not self.last_process.is_finished():
            return None
        i = process.get_index()
        self._processes[i] = process
        return process
    
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
    
    def count_process(self):
        return len(self._processes)
    
    def handle_messages(self, count=None):
        chmsgs = []
        if self.chamber_msgs:
            chmsgs = self.chamber_msgs[0:count]
            if count is not None:
                self.chamber_msgs = self.chamber_msgs[count:]
            else:
                self.chamber_msgs.clear()
        
        if count is not None:
            count -= len(chmsgs)

        prmsgs = []
        if self._processes:
            prmsgs = self.last_process.handle_post_message(count)

        msgs = chmsgs + prmsgs
        self.handled_msgs.extend(msgs)
        return msgs

    def get_handled_messages(self): # -
        return self.handled_msgs
    
    def is_messages_consumed(self):
        if self.chamber_msgs:
            return False
        if self._processes:
            return self.last_process.is_messages_consumed()
        else:
            return True
    
    def post_chamber_message(self, tag, value=None, **options):
        self.chamber_msgs.append(ProcessMessage(tag=tag, text=value, **options))

    def get_index(self): # -
        return self._index

    def get_title(self): # -
        title = "Chamber"
        return "{}. {}".format(self._index, title)
    
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
        pis = [x for x,t in piset.items() if t]
        for pi in pis:
            del self._processes[pi]
        
        return pis # 削除されたプロセスのリスト

    def start_process_sequence(self, messages):
        """
        一連のプロセスを順に実行する。
        """
        def _launch(chamber):
            iline = 0
            while iline < len(messages):
                c1 = chamber.count_process()
                if iline <= c1 and chamber.is_messages_consumed():
                    chamber.post_chamber_message("eval-message", message=messages[iline])
                    iline += 1
                else:
                    time.sleep(0.1)
                    continue
        
        # プロセスを順に立ち上げるスレッドを始動
        thread = threading.Thread(name="ProcessSequenceLauncher", target=_launch, args=(self,), daemon=True)
        thread.start()

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

    def handle_messages(self):
        return []

    def get_handled_messages(self): #
        msgs = []
        for item in self._objcol.pick_all():
            msg = ProcessMessage(object=item.object, deskname=self._index, tag="object-summary", sel=item.selected)
            msgs.append(msg)
        return msgs

    def get_title(self): # -
        title = "机{}. {}".format(self._index+1, self._name)
        return title


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

    # 新しいチャンバーを作成して返す
    def addnew(self, initial_prompt=None):
        newindex = self._nextindex
        chamber = ProcessChamber(newindex)
        if initial_prompt:
            chamber.post_chamber_message("message-em", initial_prompt, nobreak=True)
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

    def is_active(self, index):
        return self.get_active_index() == index

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

    def shift_active(self, delta: int) -> Optional[ProcessChamber]:
        i = self.get_next_index(delta=delta)
        if i is not None:
            self.activate(i)
            return self.get(i)
        return None
    
    def select(self, index=None, *, activate=False) -> Optional[ProcessChamber]:
        chm = None
        if index is None or index == "":
            chm = self.get_active()
        elif isinstance(index, str):
            if index=="desktop":
                chm = self.processhive.get_last_active_desktop()
            else:
                try:
                    index = int(index, 10)-1
                except ValueError:
                    raise ValueError(str(index))
                chm = self.get(index)
                if activate:
                    self.activate(index)
        elif isinstance(index, int):
            chm = self.get(index)
            if activate:
                self.activate(index)
        return chm

    #
    #
    #
    def get_runnings(self):
        return [x for x in self.chambers.values() if not x.is_finished()]

    def interrupt_all(self):
        for cha in self.get_runnings():
            cha.interrupt()

    def handle_messages(self, count):
        for chm in self.chambers.values():
            if chm.is_messages_consumed():
                continue
            for msg in chm.handle_messages(count):
                yield msg

    def compare_running_states(self, laststates):
        runnings = {}
        begun = []
        ceased = []
        for chm in self.chambers.values():
            if chm.is_finished():
                runnings[chm.get_index()] = False
                if chm.get_index() in laststates:
                    ceased.append(chm)
            else:
                runnings[chm.get_index()] = True
                if chm.get_index() not in laststates:
                    begun.append(chm)

        return runnings, begun, ceased


#!/usr/bin/env python3
# coding: utf-8
import os
import sys
import threading
import queue
import time
import traceback
from typing import Sequence, Optional, List, Dict, Any, Tuple, Set, Generator, Union

#from machaon.action import ActionInvocation
from machaon.object.object import Object, ObjectCollection
from machaon.cui import collapse_text, test_yesno, MiniProgressDisplay, composit_text

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
        self.index = None
        # 
        self.target = None
        self.spirit = None
        self.parameter = None
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
        self.bound_objects = []
        
    def run(self, app):
        self.thread = threading.Thread(target=app.execute_process, args=(self,), daemon=True)
        self.stop_flag = False
        self.thread.start()
    
    def execute(self, execentry, objdesktop): # -> ActionInvocation:
        self.target = execentry.target
        self.spirit = execentry.spirit
        self.parameter = execentry.parameter

        # 操作を実行する
        invocation = ActionInvocation(execentry.spirit, execentry.parameter, objdesktop)
        self.last_invocation = invocation
        self.target.invoke(invocation)
        return invocation
    
    def set_index(self, index):
        if self.index is not None:
            raise ValueError("Process.index has already set.")
        self.index = index
    
    def get_index(self):
        return self.index
    
    def get_target(self):
        if self.target is None:
            raise NotExecutedYet()
        return self.target 

    def get_spirit(self):
        if self.spirit is None:
            raise NotExecutedYet()
        return self.spirit
    
    def is_constructor_process(self) -> bool:
        if self.target is None:
            return False
        return self.target.is_constructor_action()
        
    #def get_parsed_command(self):
    #    if self.parsedcommand is None:
    #        raise NotExecutedYet()
    #    return self.parsedcommand
    
    def get_command_string(self):
        return self.command

    def get_last_invocation(self):
        return self.last_invocation
    
    #def is_executed(self):
    #    return self.target is not None and self.parsedcommand is not None
    
    def is_failed(self):
        e = self.get_last_exception()
        return e is not None
    
    def is_failed_before_execution(self):
        if self.last_invocation is None:
            return False
        time = self.last_invocation.get_last_exception_time()
        return time == "init"
    
    def failed_before_execution(self, excep):
        # 実行前に起きたエラーを記録する
        invocation = ActionInvocation(None, None, None)
        invocation.initerror(excep)
        self.last_invocation = invocation
    
    def get_last_exception(self):
        if self.last_invocation is None:
            return None
        return self.last_invocation.get_last_exception()

    #
    # スレッド
    #
    def is_running(self):
        return self.thread and self.thread.is_alive()

    def join(self, timeout=None):
        if self.is_running():
            self.thread.join(timeout=timeout)
    
    def tell_interruption(self):
        self.stop_flag = True
    
    def is_interrupted(self):
        return self.stop_flag
    
    def get_thread_ident(self):
        return self.thread.ident

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
    def push_object(self, value, typename, name=None):  
        if self.last_invocation is None:
            raise ValueError("No object desktop")

        desk = self.last_invocation.get_object_desktop()
        if isinstance(value, Object):
            obj = value
        else:
            otype = desk.get_type(typename)

            if name is None:
                obji = len(self.bound_objects)
                name = "{}-{}-{}".format(otype.typename.lower(), self.index+1, obji)
            
            if isinstance(value, tuple):
                obj = desk.new(name, otype, *value)
            else:
                obj = desk.new(name, otype, value)

        desk.push(obj)
        return obj
    
    def get_bound_objects(self, running=False) -> List[Object]:
        if not running and self.is_running():
            # 動作中はアクセスできない
            return []
        return self.bound_objects
    
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
    def objectview(self, o):
        return ProcessMessage(tag="object-view", object=o)
    
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
    def push_object(self, value, *, typename, name=None, view=True):
        o = self.process.push_object(value, typename, name)
        if view:
            self.objectview(o)
        return o
    
    def push_dataview(self, items, *dataview_args, name=None, view=True, **dataview_kwargs):
        # データビューオブジェクトを作成
        from machaon.object.dataset import parse_new_dataview
        inv = self.process.get_last_invocation()
        if inv is None:
            raise ValueError()
        dataview = parse_new_dataview(inv.get_object_desktop(), items, *dataview_args, **dataview_kwargs)
        # オブジェクトを積む
        return self.push_object(dataview, typename="dataview", name=name, view=view)

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
    def __init__(self, process):
        self.process = process
        self.handled_msgs = []
    
    def is_failed(self):
        return self.process.is_failed()
    
    def is_running(self):
        return self.process.is_running()
    
    def join(self, timeout):
        self.process.join(timeout=timeout)
    
    def is_interrupted(self):
        return self.process.stop_flag

    def interrupt(self): 
        if self.process.is_waiting_input():
            self.process.tell_input_end("")
        self.process.tell_interruption()

    def is_waiting_input(self): # -
        return self.process.is_waiting_input()
    
    def finish_input(self, text): # -
        self.process.tell_input_end(text)
        
    def is_constructor_process(self) -> bool:
        return self.process.is_constructor_process()

    def handle_message(self):
        msgs = self.process.handle_post_message()
        self.handled_msgs.extend(msgs)
        return msgs

    def get_message(self): # -
        return self.handled_msgs
    
    def get_title(self): # -
        target = self.process.target
        if target is not None:
            title = target.get_prog()
        else:
            cmd = self.process.get_command_string()
            title = collapse_text(cmd.partition(" ")[0], 15)
        title = "{}. {}".format(self.process.get_index()+1, title)
        return title
    
    def get_input_command(self):
        return self.process.get_command_string()
    
    def get_process(self): # -
        return self.process
    
    # ヌルの可能性あり
    def get_bound_spirit(self): # -
        return self.process.get_spirit()

    def get_index(self): # -
        return self.process.get_index()

#
#
#
class DesktopChamber():
    def __init__(self, name, index):
        self._index = index
        self._name = name
        self._objdesk = ObjectDesktop()
        self._objdesk.add_fundamental_types()
        self._msgs = []
    
    def get_desktop(self):
        return self._objdesk

    def get_index(self): # -
        return self._index
    
    def is_running(self):
        return False
    
    def is_failed(self):
        return False
        
    def is_waiting_input(self): # -
        return False

    def is_constructor_process(self):
        return False

    def handle_message(self):
        return []

    def get_message(self): #
        msgs = []
        for obj in self._objdesk.enumerates():
            sel = self._objdesk.is_selected(obj.name)
            msg = ProcessMessage(object=obj, deskname=self._index, tag="object-summary", sel=sel)
            msgs.append(msg)
        return msgs

    def get_title(self): # -
        title = "机{}. {}".format(self._index+1, self._name)
        return title
        
    def get_input_command(self):
        return ""

#
#
#
class ProcessHive:
    def __init__(self):
        self.chambers: Dict[int, Union[ProcessChamber,DesktopChamber]] = {}
        self._allhistory: List[int] = []
        self._nextindex: int = 0
    
    def execute(self, app):
        cha = self.get_active()
        p = cha.get_process()
        app.execute_process(p)

    # 新しいチャンバーを作成して返す
    def new(self, process: Process, *, activate=True) -> ProcessChamber:
        newindex = self._nextindex
        process.set_index(newindex)
        chm = ProcessChamber(process)
        self.chambers[newindex] = chm
        self._nextindex += 1
        if activate:
            self.activate(newindex)
        return chm
    
    def new_desktop(self, name: str, *, activate=True) -> DesktopChamber:
        newindex = self._nextindex
        chm = DesktopChamber(name, newindex)
        self.chambers[newindex] = chm
        self._nextindex += 1
        if activate:
            self.activate(newindex)
        return chm
    
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
        return [x for x in self.chambers.values() if x.is_running()]

    def interrupt_all(self):
        for cha in self.get_runnings():
            cha.interrupt()

#
#
#
class ProcessError():
    def __init__(self, excep, timing, process):
        self._timing = timing
        self._excep = excep
        self._proc = process
    
    def explain_process(self):
        return "プロセス[{}] {}".format(self._proc.get_index(), self._proc.get_command_string())
    
    def explain_timing(self):
        if self._timing == "argparse":
            tim = "引数の解析"
        elif self._timing == "executing":
            tim = "実行前後での"
        elif self._timing == "execute":
            tim = "実行"
        else:
            tim = "不明な時空間'{}'での".format(self._timing)
        return "{}エラー".format(tim)
    
    def get_traces(self):
        traces = traceback.format_exception(type(self._excep), self._excep, self._excep.__traceback__)
        return traces[-1], traces[1:-1]

    def print_traceback(self, spi):
        excep, traces = self.get_traces()
        spi.error(excep)
        spi.message_em("スタックトレース：")
        spi.message("".join(traces))

    
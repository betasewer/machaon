﻿#!/usr/bin/env python3
# coding: utf-8

import threading
import pprint
import os

from typing import Dict, Iterator, Tuple, Sequence, List, Optional, Any, TYPE_CHECKING

from machaon.cui import composit_text
from machaon.types.stacktrace import ErrorObject
from machaon.process import ProcessSentence, ProcessHive

if TYPE_CHECKING:
    from machaon.app import AppRoot

#
#
#
text_message_tags = {
    "message",
    "message-em",
    "warn",
    "error",
    "hyperlink",
    "input",
    "selection",
    "item-selection",
    "black",
    "grey",
    "red",
    "blue",
    "green",
    "cyan",
    "yellow",
    "magenta"
}

system_message_tags = {
    "delete-message",  
    # 画面の文字を削除する。
    # Params:
    #   line: 
    #       削除を開始する行のインデックス（-1で末尾）
    #   count: 
    #       削除する行数
    "object-sheetview",       
    # 表組を画面に表示する。  
    # Params:
    #   rows: 
    #       文字列の表
    #   columns: 
    #       カラム名のリスト
    #   context:
    #       実行コンテキスト
    #   tabletype:
    #       テーブルの種類：tuple | sheet | collection
    "canvas",              
    # 図形を画面に表示する。     
    # Params:
    #   [text]:
    #       キャンバスオブジェクト
    "eval-message",      
    # プロセスを一つ立ち上げてメッセージを評価する。       
    # Params:
    #   message: 
    #       メッセージ文字列
    "eval-message-seq",  
    # プロセスを順番に立ち上げて一連のメッセージを評価する。     
    # Params:
    #   messages: 
    #       メッセージ文字列のリスト
    #   chamber:
    #       チャンバーオブジェクト
}

#
#
#
class Launcher():
    wrap_width = 0xFFFFFF
    is_async = True

    def __init__(self):
        self.app: 'AppRoot' = None
        self.theme = None
        self.history = InputHistory()
        self.keymap = self.new_keymap()
        self.screens = {} 
        self.chmstates = {}
        self.progress_displays: Dict[str, ProgressDisplayView] = {}
        
    def init_with_app(self, app):
        self.app = app
        self.keymap.load(self.app)
        self.init_screen()
    
    def init_screen(self):
        pass

    def prettyformat(self, value):
        pp = pprint.PrettyPrinter(width=type(self).wrap_width)
        return pp.pformat(value)

    @property
    def chambers(self) -> ProcessHive:
        return self.app.chambers()

    #
    #
    #
    def message_handler(self, msg, *, nested=False):
        """ メッセージを処理する """
        try:
            tag = msg.tag
            if tag in text_message_tags:
                # 適宜改行を入れる
                if msg.argument("wrap", True):
                    msg.text = composit_text(msg.get_text(), type(self).wrap_width)

                # ログウィンドウにメッセージを出力
                self.insert_screen_text(msg.tag, msg.text, **msg.args)

            elif tag == "delete-message":
                lno = msg.argument("line", -1)
                cnt = msg.argument("count", 1)
                self.delete_screen_text(lno, cnt)
            
            elif tag == "progress-display":
                command = msg.text
                key, iproc = msg.req_arguments("key", "process")
                view = self.update_progress_display_view(command, iproc, key, msg.args)
                self.insert_screen_progress_display(command, view)
            
            elif tag == "object-sheetview":
                rows, columns, context = msg.req_arguments("rows", "columns", "context")
                dataid = context.spirit.process.get_index()
                self.insert_screen_setview(rows, columns, dataid, context)

            elif tag == "canvas":
                canvas = msg.text
                if canvas is None or isinstance(canvas, str):
                    raise TypeError("machaon.ui.basic.ScreenCanvas value is required as message text")
                self.insert_screen_canvas(canvas)

            elif tag == "eval-message":
                message, = msg.req_arguments("message")
                leading = msg.argument("leading")
                self.app.eval_object_message(ProcessSentence(message, auto=True, autoleading=leading)) # メッセージを実行する

            elif tag == "eval-message-seq":
                messages, chamber = msg.req_arguments("messages", "chamber")
                chamber.start_process_sequence(messages) # eval-messageを順に投稿するスレッドを開始する

            else:
                raise ValueError("メッセージのタグが無効です：" + tag)
        
        except Exception as e:
            # メッセージ処理中にエラーが起きた
            # エラー内容をメッセージで詳細表示する
            if nested:
                raise e # エラーの詳細表示中にさらにエラーが起きた
            procid = msg.argument("process")
            process = self.chambers.get_active().get_process(procid) if procid is not None else None
            if process:
                context = process.get_last_invocation_context()
                error = ErrorObject(e, context=context)
                # エラーメッセージをUIに転送し、ただちにメッセージを取得して表示する
                context.spirit.instant_pprint(error)
                # コンテキストにエラーオブジェクトを設定し、メッセージの実行を終了
                errobj = context.new_invocation_error_object(error)
                context.push_extra_exception(errobj)
                process.on_finish_process(context, errobj)
            else:
                from machaon.types.stacktrace import verbose_display_traceback
                self.insert_screen_text("error", "プロセスの外部でエラーが発生：{}[{}]".format(e, type(e).__name__))
                self.insert_screen_text("message", verbose_display_traceback(e, 0x7FFFFF))
    
    def update_chamber_messages(self, count):
        """ 全チャンバーに送られたメッセージを読みに行く """
        handled_count = 0
        for msg in self.chambers.handle_messages(count):
            self.message_handler(msg)
            handled_count += 1
        return  handled_count

    #
    # メッセージウィンドウの操作
    #
    def insert_screen_text(self, tag, value, **args):
        raise NotImplementedError()

    def delete_screen_text(self, lineno, count):
        raise NotImplementedError()

    def replace_screen_text(self, text):
        raise NotImplementedError()
    
    def dump_screen_text(self):
        raise NotImplementedError()
    
    def drop_screen_text(self, process_ids):
        raise NotImplementedError()

    def insert_screen_setview(self, rows, columns, dataid, context):
        raise NotImplementedError()
    
    def insert_screen_progress_display(self, command, view):
        raise NotImplementedError()

    def insert_screen_canvas(self, canvas):
        raise NotImplementedError()
    
    def get_screen_texts(self) -> str:
        """ ログ保存用にテキストのみを取得する """
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
    
    def execute_input_text(self):
        """ 
        コマンド欄を実行する
        Returns:
            bool: プロセスが開始したか
        """
        message = self.get_input_text(pop=True) # メッセージを取得
        cha = self.chambers.get_active()
        if cha is not None and cha.is_waiting_input():
            # 入力を完了する
            cha.finish_input(message)
            return False
        
        else:
            # メッセージを実行する
            sentence = ProcessSentence(message)
            if self.app.eval_object_message(sentence) is None:
                return False
        
            # 入力履歴に追加する
            self.history.push(message)
            self.history.select_last()
            return True

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
    def activate_new_chamber(self, process=None):
        """ チャンバーを新規作成して追加する """
        lastchm = self.chambers.get_active()
        newchm = self.chambers.addnew(self.get_input_prompt())
        if lastchm:
            self.flip_chamber_content(newchm, lastchm)
        if process:
            newchm.add(process)
        self.add_chamber_menu(newchm)
    
    def shift_active_chamber(self, delta):
        """ 隣接したチャンバーをアクティブにする """
        lastchm = self.chambers.get_active()
        chm = self.chambers.shift_active(delta)
        if chm is None:
            return
        self.flip_chamber(chm, lastchm)
    
    def flip_chamber_content(self, chamber, prevchamber):
        if prevchamber:
            self.screens[prevchamber.get_index()] = self.dump_screen_text() # 現在のチャンバーの内容物を保存する
        if chamber.get_index() in self.screens:
            self.replace_screen_text(self.screens[chamber.get_index()]) # 新たなチャンバーの内容物に置き換える
        else:
            self.replace_screen_text(None)
    
    def flip_chamber(self, chamber, prevchamber):
        self.flip_chamber_content(chamber, prevchamber)
        self.update_chamber_menu(active=chamber)

    def close_active_chamber(self):
        """ アクティブなチャンバーを削除する。動作中なら停止を試みる """
        chm = self.chambers.get_active()

        # 第一デスクトップは削除させない
        if chm.get_index() == 0:
            return

        # 削除し新たにアクティブにする
        def remove_and_shift(chm):
            # 消去
            self.remove_chamber_menu(chm)
            self.chambers.remove(chm.get_index())
            
            # 隣のチャンバーに移る
            nchm = self.chambers.get_active() # 新たなチャンバー
            self.flip_chamber(nchm, None)

        # 停止処理
        if not chm.is_finished():
            self.break_chamber_process(timeout=10, after=remove_and_shift)
        else:
            remove_and_shift(chm)
    
    def break_chamber_process(self, timeout=10, after=None):
        """ アクティブな作動中のチャンバーを停止する """
        chm = self.chambers.get_active()
        if chm.is_finished():
            return
        if chm.is_interrupted():
            return # 既に別箇所で中断が試みられている

        chm.interrupt() # 中断をプロセスに通知する

        self.insert_screen_text("message", "プロセス[{}]の終了を待ちます...({}秒)".format(chm.get_index(), timeout))
        
        def watcher():
            for _ in range(timeout):
                if chm.is_finished():
                    if after: after(chm)
                    break
                chm.join(timeout=1)
            else:
                self.insert_screen_text("warn", "プロセス[{}]を終了できません".format(chm.get_index()))

        wch = threading.Thread(None, watcher, daemon=True, name="Process{}Killer".format(chm.get_index()))
        wch.start() # 一定時間、終了を待つ
    
    def finish_chamber(self, chamber):
        """ 終了したチャンバーに対する処理 """
        # 文字色を実行中の色から戻す
        self.update_chamber_menu(ceased=chamber)

    def update_chamber_states(self):
        """ 全チャンバーの状態表示を更新する """
        states, _begun, ceased = self.chambers.compare_running_states(self.chmstates)
        for chm in ceased:
            self.finish_chamber(chm)
        self.chmstates = states

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
    #
    #
    def update_progress_display_view(self, command, process_index, key, args):  
        progkey = "{}.{}".format(process_index, key)      
        if command == "start":
            v = ProgressDisplayView(progkey, total=args.get("total"), title=args.get("title"))
            self.progress_displays[progkey] = v
            return v
        else:
            v = self.progress_displays.get(progkey)
            if v is None:
                raise ValueError(progkey)
            if command == "progress":
                v.update(args.get("progress"))
            elif command == "end":
                v.finish()
            elif command == "total":
                v.set_total(args.get("total"))
            return v
    
    #
    # ハンドラ
    #    
    def post_on_exec_process(self, process, exectime):
        """ プロセス実行開始時 """
        raise NotImplementedError()
    
    def post_on_success_process(self, process, ret, spirit):
        """ プロセスの正常終了時 """
        raise NotImplementedError()

    def post_on_interrupt_process(self, process):
        """ プロセス中断時 """
        raise NotImplementedError()
    
    def post_on_error_process(self, process, excep):
        """ プロセスの異常終了時 """
        raise NotImplementedError()

    def post_on_end_process(self, process):
        """ 正常であれ異常であれ、プロセスが終了した後に呼ばれる """
        raise NotImplementedError()
    
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
    def get_keymap(self):
        return self.keymap

    def new_keymap(self):
        return KeybindMap()

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
class ProgressDisplayView:
    def __init__(self, key, total=None, title=None):
        self.key = key
        self.title = title
        self.total = total
        self.progress = None
        self.marquee = False if total else True
        self.lastbit = None
        self.changed = False

    def is_starting(self):
        """ updateでバーが初めて表示された """
        return self.progress == 0
    
    def set_total(self, total):
        if total is not None:
            self.total = total
            self.marquee = False
        else:
            self.total = None
            self.marquee = True

    def is_marquee(self):
        return self.marquee

    def get_total_int(self):
        return round(self.total)

    def get_progress_rate(self):
        if self.total is None or self.progress is None:
            return None
        return self.progress / self.total
    
    def update(self, delta=None):
        progress = self.progress 
        if progress is None:
            progress = 0
        else:
            progress += int(delta)
        self.progress = progress

    def update_change_bit(self, total_width):
        if self.marquee:
            bit = round(self.progress / total_width)
        else:
            bit = round(total_width * (self.progress / self.total))
        if self.lastbit == bit:
            changed = False
        else:
            changed = True
            self.lastbit = bit
        return changed

    def finish(self):
        if self.marquee:
            pass
        else:
            self.progress = self.total

    #
    #
    #
    def display_chars(self, charwidth: int, format, *, start=False, end=False):
        """ 
        マーキー表示
        Params:
            charwidth(int): 文字幅
            format((progress: int, total: int, percent: int, mainchars: int, rightchars: int) -> str): 整形関数 
        """
        if start:
            return format(0, self.total, 0, 0, charwidth)
        elif end:
            return format(self.total, self.total, 100, charwidth, 0)
        else:
            bar_width = round(charwidth * self.get_progress_rate())
            rest_width = charwidth - bar_width
            hund = round(self.get_progress_rate() * 100)
            return format(self.progress, self.total, hund, bar_width, rest_width)

    def display_marquee_chars(self, charwidth: int, format, *, start=False, end=False):
        """ 
        マーキー表示
        Params:
            charwidth(int): 文字幅
            format((progress: int, leftchars: int, mainchars: int, rightchars: int) -> str): 整形関数 
        """
        if start:
            return format(0, charwidth, 0, 0)
        elif end:
            prog = self.progress+1 if self.progress else 0
            return format(prog, 0, charwidth, 0)
        else:
            if not self.update_change_bit(charwidth):
                return None
            l, m = (
                (0, 0.3), (0.33, 0.34), (0.7, 0.3)
            )[self.lastbit % 3]
            lb = round(l * charwidth)
            mb = round(m * charwidth)
            rb = charwidth - lb - mb
            return format(self.progress, lb, mb, rb)


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
    
#
#
#
class Keybind:
    def __init__(self, key, when):
        self.key = key
        self.when = when

class KeyCommand:
    def __init__(self, command):
        self.command = command
        self.fn = None
        self.keybinds: List[Keybind] = []

    def add_keybind(self, k: Keybind):
        self.keybinds.append(k)

    def handler(self, fn):
        self.fn = fn


class KeybindMap():
    def __init__(self):
        self._commands: Dict[str, KeyCommand] = {}
        self.defines()

    def defines(self):
        cmds = (
            "Run",
            "Interrupt",
            "CloseChamber",
            "InputInsertBreak",
            "InputClear",
            "InputRollback",
            "InputHistoryNext",
            "InputHistoryPrev",
            "InputPaneExit",
            "LogScrollPageUp",
            "LogScrollPageDown",
            "LogScrollUp",
            "LogScrollDown",
            "LogScrollLeft",
            "LogScrollRight",
            "LogScrollNextProcess",
            "LogScrollPrevProcess",
            "LogInputSelection",
            "LogPaneExit",
            "DragAndDropPanelToggle"
        )
        self._commands = {x:KeyCommand(x) for x in cmds}
    
    def load(self, app):
        p = os.path.join(os.path.dirname(__file__), "../configs", "keybind.ini")
        if not os.path.isfile(p):
            raise ValueError("default keybind.ini is not found")
        
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read(p, encoding="utf-8")
        
        p = app.get_keybind_file()
        if p is not None:
            cfg.read(p, encoding="utf-8")
        
        import machaon.platforms
        if machaon.platforms.is_windows():
            pltkey = "win"
        elif machaon.platforms.is_osx():
            pltkey = "mac"
        else:
            app.post_stray_message("message", "この実行環境ではキーバインドは使用できません")
            return
        
        for section in cfg.sections():
            when = "root"
            if cfg.has_option(section, "when"):
                when = cfg.get(section, "when")
            
            command = None
            if not cfg.has_option(section, "command"):
                app.post_stray_message("warn", "キーマップ[{}]読み込み中に：commandキーがありません".format(section))
                continue
            command = cfg.get(section, "command")

            key = None
            if cfg.has_option(section, pltkey):
                key = cfg.get(section, pltkey)
            elif cfg.has_option(section, "key"):
                key = cfg.get(section, "key")
            else:
                app.post_stray_message("warn", "キーマップ[{}]読み込み中に：key|win|macキーがありません".format(section))
                continue
            
            cmd = self._commands.get(command, None)
            if cmd is None:
                app.post_stray_message("warn", "キーマップ[{}]読み込み中に：コマンド'{}'は存在しません".format(section, command))
                continue
            
            # キーバインドをセット
            keys = key.split("+")
            keybind = Keybind(keys, when)
            cmd.add_keybind(keybind)
    
    def get(self, command) -> KeyCommand:
        cmd = self._commands.get(command, None)
        if cmd is None:
            raise ValueError("定義されていないコマンドです")
        return cmd
    
    def get_keybinds(self, command) -> List[Keybind]:
        cmd = self._commands.get(command, None)
        if cmd is None:
            raise ValueError("定義されていないコマンドです")
        return cmd.keybinds

    def all_commands(self) -> Iterator[KeyCommand]:
        for cmd in self._commands.values():
            yield cmd

    def all_keybinds(self) -> Iterator[Keybind]:
        for cmd in self._commands.values():
            for k in cmd.keybinds:
                yield k

    def define_ui_handlers(self, ui):
        """ UIのコマンド関数を関連づける """
        for cmd in ui.keymap.all_commands():
            fn = getattr(self, cmd.command, None)
            if fn is not None:
                cmd.fn = self.wrap_ui_handler(fn, ui)
            else:
                raise ValueError("UI handler '{}' is not implemented".format(cmd.command))

    def wrap_ui_handler(self, fn, ui):
        raise NotImplementedError()

    def Run(self, ui, e):
        """ 入力の実行 """
        pass
    
    def Interrupt(self, ui, e):
        """ 入力中止 """
        pass

    def CloseChamber(self, ui, e): 
        """ チャンバーを閉じる """
        pass

    def InputInsertBreak(self, ui, e): 
        """ 改行を入力 """
        pass
    
    def InputClear(self, ui, e):
        """ """
        pass

    def InputRollback(self, ui, e):
        """ """
        pass
        
    def InputHistoryNext(self, ui, e):
        """ """
        pass

    def InputHistoryPrev(self, ui, e):
        """ """
        pass
    
    def InputPaneExit(self, ui, e):
        """ 選択モードへ """
        pass
    
    def LogPaneExit(self, ui, e):
        """  """
        pass
    
    def LogScrollPageUp(self, ui, e):
        pass

    def LogScrollPageDown(self, ui, e):
        pass

    def LogScrollUp(self, ui, e):
        pass

    def LogScrollDown(self, ui, e):
        pass
    
    def LogScrollLeft(self, ui, e):
        pass

    def LogScrollRight(self, ui, e):
        pass
    
    def LogScrollNextProcess(self, ui, e):
        pass

    def LogScrollPrevProcess(self, ui, e):
        pass
        
    def LogInputSelection(self, ui, e):
        pass

    def DragAndDropPanelToggle(self, ui, e):
        pass


#
#
#
class ScreenCanvas():
    def __init__(self, name, width, height, color=None):
        self.graphs: List[Dict[str, Any]] = []
        self.name: str = name
        self.bg: str= color
        self.width: int = width
        self.height: int = height

    def add_graph(self, typename, **kwargs):
        if "type" in kwargs:
            raise ValueError("key 'type' is reserved")
        kwargs["type"] = typename
        self.graphs.append(kwargs)
        return self
        
    def rectangle_frame(self, *, coord=None, width=None, color=None, dash=None, stipple=None):
        return self.add_graph("rectangle-frame", coord=coord, width=width, color=color, dash=dash, stipple=stipple)
        
    def rectangle(self, *, coord=None, color=None, dash=None, stipple=None):
        return self.add_graph("rectangle", coord=coord, color=color, dash=dash, stipple=stipple)

    def oval(self, *, coord=None, color=None, dash=None, stipple=None):
        return self.add_graph("oval", coord=coord, color=color, dash=dash, stipple=stipple)

    def text(self, *, coord=None, text=None, color=None):
        return self.add_graph("text", coord=coord, text=text, color=color)

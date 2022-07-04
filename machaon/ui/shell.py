#!/usr/bin/env python3
# coding: utf-8
import os
import sys
from machaon.cui import reencode, collapse_text

from machaon.ui.basic import Launcher

def isatty():
    import platform
    if hasattr(sys.stderr, "isatty") and sys.stderr.isatty():
        if platform.system()=='Windows':
            return False
        else:
            return True
    else:
        return False

class AnsiCodeComposer:
    def __init__(self):
        self._codes = None

    @property
    def codes(self):
        if self._codes is None:
            self._codes = {
                # 文字色
                "BLACK"     : "\33[30m",
                "RED"       : "\33[31m",
                "GREEN"     : "\33[32m",
                "YELLOW"    : "\33[33m", 
                "BLUE"      : "\33[34m", 
                "MAZENTA"   : "\33[35m", 
                "CYAN"      : "\33[36m", 
                "WHITE"     : "\33[37m", 
                "GRAY"      : "\33[90m",
                "XRED"      : "\33[91m",
                "XGREEN"    : "\33[92m",
                "XYELLOW"   : "\33[93m", 
                "XBLUE"     : "\33[94m", 
                "XMAZENTA"  : "\33[95m", 
                "XCYAN"     : "\33[96m", 
                "XWHITE"    : "\33[97m", 
                "ENDCOL"    : "\33[0m",
                # 編集
                "DELLINE"   : "\33[2K",
            }
        return self._codes

    def colortext(self, code, text):
        return self.codes[code] + text + self.codes["ENDCOL"]

    def colorize(self, tag, text):
        if tag == "error":
            text = self.colortext("XRED", text)
        elif tag == "warn":
            text = self.colortext("YELLOW", text)
        elif tag == "input":
            text = self.colortext("XGREEN", text)
        elif tag == "message-em":
            text = self.colortext("XYELLOW", text)
        elif tag == "hyperlink":
            text = self.colortext("CYAN", text)
        else:
            pass
        return text

    def deleteline(self, count):
        return "\33[{}M".format(count)

ansicodes = AnsiCodeComposer()


#
#
#
class ShellLauncher(Launcher):
    def __init__(self, encoding, width, maxlinecount=None, useansi=False):
        super().__init__()
        self.encoding = encoding
        self.wrap_width = width 
        self.maxlinecount = maxlinecount
        self._loop = True
        self._waiting_input_message = False
        self._useansi = useansi

    def printer(self, tag, text, end=None):
        if self._useansi:
            text = ansicodes.colorize(tag, text)
        else:
            if tag == "error":
                text = "!!≪error≫" + text
            elif tag == "warn":
                text = "!!≪warn≫" + text
        print(text, end=end)

    def use_ansi(self, b):
        self._useansi = b

    def init_screen(self):
        if isatty():
            self._useansi = True

    def insert_screen_text(self, tag, text, *, nobreak=False, **kwargs):
        if self.encoding is not None:
            text = reencode(text, self.encoding, "replace")
        
        if nobreak:
            end = ""
        else:
            end = None
        
        self.printer(tag, text, end=end)
    
    def delete_screen_text(self, lineno, count):
        if not self._useansi:
            return
        if lineno == -1:
            text = ansicodes.deleteline(count)
            print(text, end="")
        else:
            pass # Not Implemented

    def replace_screen_text(self, text):
        pass
    
    def save_screen_text(self):
        pass
    
    def drop_screen_text(self, process_ids):
        pass

    def insert_screen_setview(self, rows, columns, dataid, context):
        print("\t".join(columns))
        print("---------------------------")
        for _index, row in rows:
            print("\t".join(row))

    def add_chamber_menu(self, chamber):
        pass

    def update_chamber_menu(self, *, active=None, ceased=None):
        pass
    
    def remove_chamber_menu(self, chamber):
        pass
        
    def get_input_text(self, pop=False):
        return input()
    
    #
    # 表示ハンドラ
    #
    def post_on_exec_process(self, process, exectime):
        """ プロセス実行開始時 """
        pass # 何も表示しない
    
    def post_on_success_process(self, process, ret, spirit):
        """ プロセスの正常終了時 """
        index = process.get_index()
        if ret.is_pretty():
            ret.pprint(spirit) # 詳細表示を行う
        process.post("input", " [{}]".format(index), nobreak=True)
        process.post("message", " -> {} [{}]".format(ret.summarize(), ret.get_typename()))

    def post_on_interrupt_process(self, process):
        """ プロセス中断時 """
        process.post("message-em", "中断しました")
    
    def post_on_error_process(self, process, excep):
        """ プロセスの異常終了時 """
        index = process.get_index()
        process.post("input", " [{}]".format(index), nobreak=True)
        process.post("error", " -> {}".format(excep.summarize()))

    def post_on_end_process(self, process):
        """ 正常であれ異常であれ、プロセスが終了した後に呼ばれる """
        # 次回入力へのプロンプト
        process.post("message-em", self.get_input_prompt(), nobreak=True) 
        # 入力待ちになる
        if process.is_process_sequence:
            self._waiting_input_message = False # 自動実行モード
            process.post("message", "") 
        else:
            self._waiting_input_message = True

    def run_mainloop(self):
        while self._loop:
            self.update_chamber_messages(None)

            if self._waiting_input_message and self.chambers.get_active().is_messages_consumed():
                self._waiting_input_message = False
                if not self.execute_input_text():
                    self._waiting_input_message = True # エラーが起きた

    def on_exit(self):
        self._loop = False

#
#
#
class WinCmdShell(ShellLauncher):
    def __init__(self, args):
        super().__init__(
            encoding="cp932", 
            width=67, 
            maxlinecount=200,
            useansi=args.get("ansi", False)
        )

    def clear(self):
        os.system('cls')

class GenericShell(ShellLauncher):
    def __init__(self, args):
        super().__init__(
            encoding     = args.get("encoding", "utf-8"), 
            width        = args.get("width", 67), 
            maxlinecount = args.get("maxlinecount", 200),
            useansi      = args.get("ansi", False)
        )

    def clear(self):
        os.system('clear')

# 環境で自動判別する
# def ShellApp():



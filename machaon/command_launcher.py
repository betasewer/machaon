#!/usr/bin/env python3
# coding: utf-8

import sys
import os
import traceback
import shutil
from machaon.processor import Processor, BadCommand
from machaon.app import ExitApp
 
#
hidden_command = 2
auxiliary_command = 1

#
#
#
class LauncherEntry():
    def __init__(self, commandclass, keywords=None, desc=None, commandtype=0):
        self.command = commandclass
        def classattr(name, default):
            getter = getattr(commandclass, name, None)
            if getter: return getter()
            return default
        self.keywords = keywords or classattr("get_default_keywords", tuple())
        self.desc = desc or classattr("get_desc", "")
        self.commandtype = commandtype
    
    def match(self, kwd):
        return kwd in self.keywords
        
    def set_keywords(self, *kwds):
        self.keywords = kwds
        return self
    
    def set_desc(self, d):
        self.desc = d
        return self
        
    def get_first_keyword(self):
        return self.keywords[0]
    
    
#
class LauncherCommand():
    def __init__(self, entry, argstr=""):
        self.entry = entry
        self.argstr = argstr
    
    def reconstruct(self):
        return "{} {}".format(self.entry.get_first_keyword(), self.argstr)
    
    def get_command(self):
        return self.entry.command
    
    def get_argument(self):
        return self.argstr

#
class CommandFunction:
    def __init__(self, fn, desc, *args):
        self.fn = fn
        self.desc = desc
        self.bindargs = args
        
    def invoke(self, argstr):
        args = []
        args.extend(self.bindargs)
        if argstr:
            args.append(argstr)
        return self.fn(*args)

    def help(self, app):
        app.message(self.desc)

    
#
# コマンドを処理する
#
class CommandLauncher:
    def __init__(self, app):
        self.app = app
        self.lastcmdstr = ""
        self.nextcmdstr = None
        self.entries = []
        
    def command(self, proc, keywords=None, desc=None, hidden=False, auxiliary=False, bindapp=False):
        if not isinstance(proc, type):
            bindargs = []
            if bindapp:
                bindargs.append(self.app)
            proc = CommandFunction(proc, desc, *bindargs)
        typecode = 0
        if auxiliary: typecode = auxiliary_command
        if hidden: typecode = hidden_command
        entry = LauncherEntry(proc, keywords, desc, typecode)
        # キーワードの重複を確認
        for curentry in self.entries:
            if any(curentry.match(x) for x in keywords):
                raise ValueError("キーワード:{}は既に'{}'によって使用されています".format(",".join(keywords), curentry.get_first_keyword()))
        self.entries.append(entry)
        return entry
    
    # コマンドを処理
    def translate_command(self, commandstr=None):
        if commandstr is None:
            cmdstr = sys.argv[1] if len(sys.argv)>1 else ""
            argstr = " ".join(sys.argv[2:])
        else:
            spl = commandstr.split(maxsplit=1)            
            cmdstr = spl[0] if len(spl)>0 else ""
            argstr = spl[1] if len(spl)>1 else ""
        
        # メインコマンド
        for entry in self.entries:
            if entry.match(cmdstr):
                c = LauncherCommand(entry, argstr)
                return c
        else:
            return None
    
    # self.app.launcher.redirect_command("")
    def redirect_command(self, command: str):
        self.nextcmdstr = command
    
    def pop_next_command(self):
        nextcmd = None
        if self.nextcmdstr is not None:
            nextcmd = self.nextcmdstr
            self.nextcmdstr = None
        return nextcmd

    #
    def list_commands_for_display(self):
        entries = [x for x in self.entries if x.commandtype != hidden_command]
        entries = sorted(entries, key=lambda x: x.commandtype)
        return entries

    #
    def command_interrupt(self):    
        if not self.app.is_process_running():
            self.app.message("実行中のプロセスはありません")
            return
        self.app.message("プロセスを中断します")
        self.app.interrupt_process()
        
    def command_help(self):
        rows = [(", ".join(x.keywords), x.desc) for x in self.list_commands_for_display()]
        leftmax = max(len(kwds) for kwds, _ in rows)        
        self.app.message("<< コマンド一覧 >>")
        self.app.message("---------------------------")
        for kwds, desc in rows:
            row = "  {}    {}".format(kwds.ljust(leftmax), desc)
            self.app.message(row)
        self.app.message("---------------------------")
        self.app.message("詳細は各コマンドのhelpを参照")
        
    def command_exit(self, arg=None): 
        if arg in ("--ask", "-a"):
            if not self.app.ask_yesno("終了しますか？ (Y/N)"):
                return
        return ExitApp
    
    def command_cls(self):
        self.app.reset_screen()
    
    def command_cd(self, path=None):
        if path is not None:
            self.app.change_current_dir(path)
        self.app.message("現在の作業ディレクトリ：" + self.app.get_current_dir())

    # 備え付けのコマンドを登録する
    def syscommands(self, names=("interrupt", "cls", "cd", "help", "exit")):
        _cmds = {
            "interrupt" : (("interrupt", "it"), "現在実行中のプロセスを中断します。"),
            "exit" : (("exit",), "終了します。"),
            "help" : (("help", "h"), "ヘルプを表示します。"),
            "cls" : (("cls",), "画面をクリアします。"),
            "cd" : (('cd',), "作業ディレクトリを変更します。"),
        }
        for name in names:
            cmd = getattr(self, "command_{}".format(name), None)
            entry = _cmds.get(name)
            if cmd is None or entry is None:
                continue
            self.command(cmd, *entry, auxiliary=True)


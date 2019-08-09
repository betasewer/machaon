#!/usr/bin/env python3
# coding: utf-8

import sys
import os
import traceback
import shutil
from machaon.processor import Processor, BadCommand
from machaon.app import ExitApp
 
#
#
#
class LauncherEntry():
    def __init__(self, commandclass, keywords=None, desc=None, hidden=False):
        self.command = commandclass
        def callattr(obj, name, default):
            getter = getattr(obj, name, None)
            if getter: return getter()
            return default
        self.keywords = keywords or callattr(commandclass, "get_default_keywords", tuple())
        self.desc = desc or callattr(commandclass, "get_desc", "")
        self.hidden = hidden
    
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
    def __init__(self, fn, desc):
        self.fn = fn
        self.desc = desc
        
    def invoke(self, argstr):
        args = [argstr] if argstr else []
        return self.fn(*args)

    def help(self, app):
        app.message(self.desc)

    
#
# コマンドを処理する
#
class CommandLauncher:
    class ExitLauncher:
        pass

    def __init__(self, app):
        self.app = app
        self.lastcmdstr = ""
        self.nextcmdstr = None
        self.entries = []
        
    def command(self, proc, keywords=None, desc=None, hidden=False):
        if not isinstance(proc, type):
            proc = CommandFunction(proc, desc)
        entry = LauncherEntry(proc, keywords, desc, hidden)
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
            self.app.error("'{}'は不明なコマンドです".format(cmdstr))
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
    def command_interrupt(self):    
        if not self.app.is_process_running():
            return
        self.app.interrupt()
        
    def command_help(self):
        descs = []
        descs.extend([(", ".join(e.keywords), e.desc) for e in self.entries if not e.hidden])
        leftmax = max(len(kwds) for kwds, _ in descs)
        
        self.app.message("<< コマンド一覧 >>")
        self.app.message("---------------------------")
        for kwds, desc in descs:
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
    def syscommand_interrupt(self):
        return self.command(self.command_interrupt, ("interrupt", "it"), "現在のタスクを中断します。")
    
    def syscommand_help(self):
        return self.command(self.command_help, ("help", "h"), "ヘルプを表示します。")
    
    def syscommand_exit(self):
        return self.command(self.command_exit, ("exit",), "終了します。")
    
    def syscommand_cls(self):
        return self.command(self.command_cls, ("cls",), "画面をクリアします。")
    
    def syscommand_cd(self):
        return self.command(self.command_cd, ('cd',), "作業ディレクトリを変更します。")

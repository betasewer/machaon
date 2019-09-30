#!/usr/bin/env python3
# coding: utf-8

import sys
import os
import traceback
import shutil

from machaon.command import describe_command, BadCommand
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
        def invokeattr(klass, name, default):
            getter = getattr(klass, name, None)
            if getter: return getter()
            return default
        self.keywords = keywords or invokeattr(commandclass, "get_default_keywords", tuple())
        self.desc = desc or invokeattr(commandclass, "get_desc", "")
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
# コマンドを処理する
#
class CommandLauncher:
    def __init__(self, app):
        self.app = app
        self.lastcmdstr = ""
        self.nextcmdstr = None
        self.entries = []
        
    def define_command(self, proc, keywords=None, hidden=False, auxiliary=False):
        desc = proc.get_description()
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
    def command_help(self, commandname=None):
        rows = [(", ".join(x.keywords), x.desc) for x in self.list_commands_for_display()]
        leftmax = max(len(kwds) for kwds, _ in rows)        
        self.app.message("<< コマンド一覧 >>")
        self.app.message("---------------------------")
        for kwds, desc in rows:
            row = "  {}    {}".format(kwds.ljust(leftmax), desc)
            self.app.message(row)
        self.app.message("---------------------------")
        self.app.message("詳細は各コマンドのhelpを参照")
    
    #
    # プリセットコマンドの定義
    #
    syscommands = [
        ("command_help", ("help", "h"), 
            describe_command(
                description="ヘルプを表示します。"
            )["target command-name"](
                nargs="?",
                help="ヘルプを見るコマンド"
            )
        ),
    ]


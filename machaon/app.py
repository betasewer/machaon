#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import queue
import threading
import traceback
import subprocess

from typing import Optional, List, Any

from machaon.engine import CommandEngine, CommandEntry
from machaon.command import describe_command
from machaon.process import ProcessInterrupted, Process, Spirit, ProcessHive, ProcessChamber
from machaon.cui import test_yesno
import machaon.platforms

#
# ###################################################################
#  すべてのmachaonアプリで継承されるアプリクラス
#   プロセッサーを走らせる、UIの管理を行う
#   プロセッサーに渡され、メッセージ表示・設定項目へのアクセスを提供する
# ###################################################################
#
class AppRoot:
    def __init__(self):
        self.ui = None
        self.cmdengine = None 
        self.processhive = None
        self.curdir = "" # 基本ディレクトリ

    def initialize(self, *, ui):
        self.ui = ui
        if hasattr(self.ui, "init_with_app"):
            self.ui.init_with_app(self)
        self.processhive = ProcessHive()
        self.cmdengine = CommandEngine()
    
    def get_ui(self):
        return self.ui
 
    #
    # コマンドの追加
    #
    # コマンドパッケージを導入
    def install_commands(self, prefixes, package):
        cmdset = package.create_commands(self, prefixes)
        self.cmdengine.install_commands(cmdset)

    #
    # アプリの実行
    #
    def run(self):
        if self.ui is None:
            raise ValueError("App UI must be initialized")
        if self.cmdengine is None:
            raise ValueError("App launcher must be initialized")
        self.mainloop()

    def exit(self):
        self.to_be_exit = True
        self.processhive.stop()
        self.ui.on_exit()
    
    def mainloop(self):
        self.ui.run_mainloop()

    #
    # 基本ディレクトリ
    #
    def get_current_dir(self):
        return self.curdir
    
    def set_current_dir(self, path):
        self.curdir = path
    
    def set_current_dir_desktop(self):
        self.set_current_dir(os.path.join(os.path.expanduser("~"), "Desktop"))

    #
    # コマンド処理の流れ
    #
    # プロセスをスレッドで実行しアクティブにする
    def run_process(self, commandstr):
        process = Process(commandstr)
        chamber = self.processhive.add(process)
        self.processhive.run(self)
        return chamber
    
    # プロセスを即時実行する
    # メッセージ出力を処理しない
    def execute_instant(self, target, argument="", *, spirit=True, args=None, custom_command_parser=None, prog=None):        
        # コマンドエントリの構築
        d = describe_command(target, spirit=spirit, args=args, custom_command_parser=custom_command_parser)
        prog = prog or getattr(target, "__name__") or "$"
        entry = d.create_entry((prog,))

        # 実行
        process_target = entry.load()
        process_spirit = process_target.invoke_spirit(self)
        possible_syntaxes = process_target.run_argparser(process_spirit, argument, "")
        if not possible_syntaxes:
            return None

        parseresult = possible_syntaxes[0]
        if parseresult.has_exit_message():
            return None

        process = Process(process_target, process_spirit, parseresult)
        cha = self.processhive.add(process, process.get_full_command())
        result = self.execute_process(process)
        return result, cha.handle_message()
    
    # プロセスの実行フロー
    def execute_process(self, process):
        commandstr = process.get_command_string()

        # メインスレッドへの伝達者
        spirit = Spirit(self, process)

        # コマンドを解析
        target = None
        parsedcommand = None
        try:
            entries = self.cmdengine.expand_parsing_command(commandstr, spirit)
            entry = self.cmdengine.select_parsing_command(spirit, entries)
            if entry is not None:
                target, spirit = entry.target, entry.spirit
                parsedcommand = self.cmdengine.parse_command(entry)
        except Exception as parseexcep:
            # コマンド解析中の例外
            self.ui.on_error_process(spirit, process, parseexcep, timing = "argparse")
            return None
        
        if parsedcommand is None:
            if entry is None:
                failtarget, failreason = None, "合致するコマンドが無かった"
            else:
                failtarget, failreason = entry.target, self.cmdengine.get_last_parse_error()
            self.ui.on_bad_command(spirit, failtarget, commandstr, failreason)
            return None

        # 実行開始！
        self.ui.on_exec_process(spirit, process)
        
        # コマンドパーサのメッセージがある場合は出力して終了
        if parsedcommand.has_exit_message():
            for line in parsedcommand.get_exit_messages():
                spirit.message(line)
            return None

        # プロセスを実行する
        result = None
        invocation = None
        try:
            #parsedcommand.expand_special_arguments(spirit)
            invocation = process.execute(target, spirit, parsedcommand)
        except ProcessInterrupted:
            self.ui.on_interrupt_process(spirit, process)
        except Exception as execexcep:
            # アプリコードの外からの例外
            self.ui.on_error_process(spirit, process, execexcep, timing = "executing")
            return None

        if invocation:
            # エラーが発生しているか
            e = invocation.get_last_exception()
            if e:
                # アプリコードからの例外
                self.ui.on_error_process(spirit, process, e, timing = "execute")
            # 最後のtargetの返り値を返す
            result = invocation.get_last_result()

        self.ui.on_exit_process(spirit, process, invocation)
        return result
    
    # 可能な構文解釈の一覧を提示する
    def parse_possible_commands(self, commandstr):
        spirit = Spirit(self, None) # processはもちろん関連付けられていない
        return self.cmdengine.expand_parsing_command(commandstr, spirit)
    
    # コマンドを検索する
    def search_command(self, commandname) -> List[CommandEntry]:
        return [entry for (entry, remained) in self.cmdengine.expand_parsing_command_head(commandname) if not remained]
    
    def get_command_sets(self):
        return self.cmdengine.command_sets()
    
    def set_command_prefix(self, prefix):
        self.cmdengine.set_command_prefix(prefix)

    #
    # プロセススレッド
    #
    # アクティブプロセスの選択
    def get_active_chamber(self):
        return self.processhive.get_active()
        
    def get_active_chamber_index(self):
        return self.processhive.get_active_index()

    def set_active_chamber_index(self, index):
        return self.processhive.set_active_index(index)
    
    def get_previous_active_chamber(self):
        return self.processhive.get_previous_active()
    
    def get_chamber(self, index):
        return self.processhive.get(index)

    def get_chambers(self):
        return self.processhive.get_chambers()
    
    def get_chambers_state(self):
        runs = self.processhive.get_runnings()
        report = {
            "running" : [x.get_index() for x in runs]
        }
        return report
        
    def select_chamber(self, index=None) -> Optional[ProcessChamber]:
        chm = None
        if not index:
            chm = self.get_active_chamber()
        elif isinstance(index, str):
            try:
                process_index = int(index, 10)-1
                chm = self.get_chamber(process_index)
            except ValueError:
                raise ValueError(str(index))
        return chm
    
    # メインスレッド側から操作中断
    def interrupt_process(self):
        scr = self.processhive.get_active()
        if scr is not None:
            proc = scr.get_process()
            proc.tell_interruption()


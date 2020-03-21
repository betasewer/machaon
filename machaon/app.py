#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import queue
import threading
import traceback
import subprocess

from machaon.engine import BadCommand, CommandEngine 
from machaon.command import describe_command
from machaon.process import ProcessInterrupted, Process, InstantProcedure, ProcessHive
from machaon.cui import test_yesno, fixsplit
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
    # コマンド文字列から呼び出す
    def create_process(self, commandstr):
        # 文字列を先頭の空白で区切る
        commandhead, commandtail = fixsplit(commandstr, maxsplit=1, default="")
        
        # コマンドを解析
        possible_entries = self.cmdengine.parse_command(commandhead, commandtail, self)
        if not possible_entries:
            # すべて失敗
            failcmd, failcmderror = self.cmdengine.get_first_parse_command_fail()
            return CommandFailureProcedure(self, commandstr=commandstr, failcmd=failcmd, failcmderror=failcmderror)
        
        # 一つを選択する
        # TODO: ランチャー上で選択させる
        process_target, spirit, parseresult = possible_entries[0]

        # プロセスの作成
        return Process(process_target, spirit, parseresult)
    
    # プロセスを実行しアクティブにする
    def run_process(self, process):
        chamber = self.processhive.add(process, process.get_full_command())
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
        spirit = process.get_spirit()
        self.ui.on_exec_process(spirit, process)

        # プロセスを実行する
        invocation = None
        try:
            invocation = process.execute()
        except ProcessInterrupted:
            self.ui.on_interrupt_process(spirit, process)
        except Exception as e:
            self.ui.on_error_process(spirit, process, e)

        self.ui.on_exit_process(spirit, process, invocation)

        if invocation:
            # 最後のtargetの返り値を返す
            return invocation.get_last_result()
        return None
    
    # 有効なプロセスコマンドか調べる
    def test_valid_process(self, processname):
        return self.cmdengine.test_command_head(processname)
    
    def get_command_sets(self):
        return self.cmdengine.command_sets()
    
    def parse_possible_commands(self, commandstr):
        head, tail = fixsplit(commandstr, maxsplit=1, default="")
        return self.cmdengine.parse_command(head, tail, self)
    
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
    
    def get_chambers_state(self):
        runs = self.processhive.get_runnings()
        report = {
            "running" : [x.get_index() for x in runs]
        }
        return report
    
    # メインスレッド側から操作中断
    def interrupt_process(self):
        scr = self.processhive.get_active()
        if scr is not None:
            proc = scr.get_process()
            proc.tell_interruption()

#
#
#
class CommandFailureProcedure(InstantProcedure):
    def __init__(self, app, commandstr, failcmd, failcmderror):
        super().__init__(app, commandstr, failcmd=failcmd, failcmderror=failcmderror)

    def procedure(self, failcmd, failcmderror):
        ui = self.spirit.get_app_ui()
        ui.on_bad_command(self.spirit, failcmd, self.get_full_command(), failcmderror)

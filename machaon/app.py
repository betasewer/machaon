#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import queue
import threading
import traceback
import subprocess

from typing import Optional, List, Any

from machaon.engine import CommandEngine, CommandEntry, NotYetInstalledCommandSet, LoadFailedCommandSet
from machaon.command import describe_command, CommandPackage
from machaon.process import ProcessInterrupted, Process, Spirit, ProcessHive, ProcessChamber
from machaon.package.package import package_manager, PackageEntryLoadError
from machaon.cui import test_yesno
from machaon.milestone import milestone, milestone_msg
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
        self.pkgmanager = None
        self.cmdpackages = []

    def initialize(self, *, ui, directory):
        self.ui = ui
        if hasattr(self.ui, "init_with_app"):
            self.ui.init_with_app(self)
        self.processhive = ProcessHive()
        self.cmdengine = CommandEngine()
        self.pkgmanager = package_manager(directory)
        self.pkgmanager.add_to_import_path()
    
    def get_ui(self):
        return self.ui
 
    #
    # コマンドの追加
    #
    # パッケージを導入
    def setup_package(self, prefixes, package):
        # コマンドセットを構築して追加する
        if isinstance(package, CommandPackage):
            cmdset = package.create_commands(self, prefixes)
            package = None
        else:
            if not package.is_installed_module():
                # ダミーのコマンドセットを設置
                cmdset = NotYetInstalledCommandSet(package.name, prefixes)
            else:
                try:
                    cmdbuilder = package.load_command_builder()
                except PackageEntryLoadError as e:
                    cmdset = LoadFailedCommandSet(package.name, prefixes, error=e.get_basic())
                else:
                    cmdset = cmdbuilder.create_commands(self, prefixes)

        # パッケージ／コマンドビルダを格納する
        cmdset_index = self.cmdengine.add_command_set(cmdset)
        if package:
            package.attach_commandset(cmdset_index)
            self.cmdpackages.append(package)
    
    def setup_dependency_package(self, package):
        self.cmdpackages.append(package)
    
    # パッケージとコマンドセットの組を取得する
    def get_package_and_commandset(self, package_index):
        # パッケージを取得
        if package_index < 0 or len(self.cmdpackages) <= package_index:
            raise IndexError("package_index") 
        package = self.cmdpackages[package_index]
        # コマンドセット
        cmdset_index = package.get_attached_commandset()
        if cmdset_index is None:
            return package, None
        else:
            cmdset = self.cmdengine.get_command_set(cmdset_index)
            return package, cmdset

    # パッケージにアップデートが必要か
    def get_package_status(self, package):
        self.pkgmanager.load_database()
        return self.pkgmanager.get_update_status(package)
            
    # パッケージをローカルに展開する
    def operate_package(self, package, install=False, uninstall=False, update=False):
        self.pkgmanager.load_database()
        if install:
            yield from self.pkgmanager.install(package, newinstall=True)
        elif uninstall:
            yield from self.pkgmanager.uninstall(package)
        elif update:
            yield from self.pkgmanager.install(package, newinstall=False)
    
    def count_package(self):
        return len(self.cmdpackages)
    
    # パッケージからコマンドセットを構築し、差し替える
    def build_commandset(self, package):
        cmdset_index = package.get_attached_commandset()
        oldcmdset = self.cmdengine.get_command_set(cmdset_index)
        try:        
            cmdbuilder = package.load_command_builder()
        except PackageEntryLoadError as e:
            newcmdset = LoadFailedCommandSet(package.name, oldcmdset.prefixes, error=e.get_basic())
        else:
            newcmdset = cmdbuilder.create_commands(self, oldcmdset.prefixes)
        self.cmdengine.replace_command_set(cmdset_index, newcmdset)
        return newcmdset
    
    # コマンドセットを未インストール状態に差し替える
    def disable_commandset(self, package):
        cmdset_index = package.get_attached_commandset()
        oldcmdset = self.cmdengine.get_command_set(cmdset_index)
        dumbcmdset = NotYetInstalledCommandSet(package.name, oldcmdset.prefixes)
        self.cmdengine.replace_command_set(cmdset_index, dumbcmdset)
        return dumbcmdset

    #
    # アプリの実行
    #
    def run(self):
        if self.ui is None:
            raise ValueError("App UI must be initialized")
        if self.cmdengine is None:
            raise ValueError("App command engine must be initialized")
        self.mainloop()

    def exit(self):
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
        chamber = self.processhive.new_activate(process)
        self.processhive.run(self)
        return chamber
    
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
    
    # プロセスを即時実行する
    # メッセージ出力を処理しない
    def execute_instant(self, target, argument="", *, spirit=True, args=None, custom_command_parser=None, prog=None):        
        # コマンドエントリの構築
        d = describe_command(target, spirit=spirit, args=args, custom_command_parser=custom_command_parser)
        prog = prog or getattr(target, "__name__") or "$"
        entry = d.create_entry((prog,))

        # 引数の解析
        argentries = self.cmdengine.expand_parsing_command(argument, spirit)
        if not argentries:
            return None
        parsedcommand = self.cmdengine.parse_command(argentries[0])
        if parsedcommand is None:
            return None

        if parsedcommand.has_exit_message():
            return None
            
        # 実行
        process_target = entry.load_target()
        process_spirit = process_target.inherit_spirit(self)
        dummyproc = Process((prog + " " + argument).strip())
        process_spirit.bind_process(dummyproc)

        invocation = None
        try:
            invocation = process_target.invoke(process_spirit, parsedcommand)
        except Exception:
            return None

        return invocation, dummyproc.handle_post_message()
    
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

    def get_previous_active_chamber(self):
        return self.processhive.get_previous_active()
    
    def get_chamber(self, index, *, activate=False):
        if activate:
            return self.processhive.activate(index)
        else:
            return self.processhive.get(index)

    def get_chambers(self):
        return self.processhive.get_chambers()
    
    def get_chambers_state(self):
        runs = self.processhive.get_runnings()
        report = {
            "running" : [x.get_index() for x in runs]
        }
        return report
        
    def select_chamber(self, index=None, *, activate=False) -> Optional[ProcessChamber]:
        chm = None
        if index is None or index == "":
            chm = self.get_active_chamber()
        elif isinstance(index, str):
            try:
                index = int(index, 10)-1
            except ValueError:
                raise ValueError(str(index))
            chm = self.get_chamber(index, activate=activate)
        elif isinstance(index, int):
            chm = self.get_chamber(index, activate=activate)
        return chm
    
    # メインスレッド側から操作中断
    def interrupt_process(self):
        scr = self.processhive.get_active()
        if scr is not None:
            proc = scr.get_process()
            proc.tell_interruption()


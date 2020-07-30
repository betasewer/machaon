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
from machaon.object.desktop import Object, ObjectDesktop
from machaon.command import describe_command, CommandPackage
from machaon.process import ProcessInterrupted, Process, Spirit, ProcessHive, ProcessChamber, ProcessBadCommand
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
        self.objdesktop = None
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
        
        self.objdesktop = ObjectDesktop()
        self.objdesktop.add_fundamental_types()

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
        self.processhive.interrupt_all()

        # まだ走っているプロセスがあれば、強制終了する
        runs = self.processhive.get_runnings()
        if runs:
            # 待ってみる
            for r in runs:
                r.join(timeout=0.1)
            # 確認のダイアログをいれたい
            # return

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
    def run_process(self, commandstr: str):
        process = Process(commandstr)
        chamber = self.processhive.new(process)
        self.processhive.activate(chamber.get_index())
        self.processhive.run(self)
        return chamber
    
    # プロセスの実行フロー
    def execute_process(self, process: Process):
        commandstr = process.get_command_string()

        # メインスレッドへの伝達者
        spirit = Spirit(self, process)

        # コマンドを解析
        execentry = None
        try:
            entries = self.cmdengine.parse_command(commandstr, spirit)
            if len(entries) == 1:
                execentry = entries[0]
            elif len(entries) > 1:
                # 一つ選択
                # spirit.create_data(entries)
                # spirit.dataview()
                # self.ui.on_select_command(spirit, process, entries)
                # 今はとりあえず先頭を採用
                execentry = entries[0]

        except Exception as parseexcep:
            # コマンド解析中の例外（コマンド解析エラーではなく）
            process.failed_before_execution(parseexcep)
            self.ui.on_error_process(spirit, process, parseexcep, timing = "argparse")
            return None
        
        if execentry is None:
            error = ProcessBadCommand(target=None, reason="合致するコマンドが無かった")
            process.failed_before_execution(error)
            self.ui.on_bad_command(spirit, process, error)
            return None

        # 実行開始！
        spirit = execentry.spirit
        self.ui.on_exec_process(spirit, process)

        # プロセスを実行する
        result = None
        invocation = None
        try:
            invocation = process.execute(execentry, self.objdesktop)
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

            # 生成されたオブジェクトを得る
            for o in process.get_bound_objects(running=True):
                self.objdesktop.push(o)
            
            # 最後のtargetの返り値を返す
            result = invocation.get_last_result()

        self.ui.on_exit_process(spirit, process, invocation)
        return result

    # 可能な構文解釈の一覧を提示する
    def parse_possible_commands(self, commandstr):
        spirit = Spirit(self, None) # processはもちろん関連付けられていない
        return self.cmdengine.parse_command(commandstr, spirit)
    
    # コマンドを検索する
    def search_command(self, commandname) -> List[CommandEntry]:
        return [entry for (entry, remained) in self.cmdengine.expand_command_head(commandname) if not remained]
    
    def get_command_sets(self):
        return self.cmdengine.command_sets()

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
        chm = self.processhive.get(index)
        if activate:
            self.processhive.activate(index)
        return chm

    def get_chambers(self):
        return self.processhive.get_chambers()
    
    def count_chamber(self):
        return self.processhive.count()
    
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
    
    # 隣接するチャンバーをアクティブにする
    def shift_active_chamber(self, delta: int) -> Optional[ProcessChamber]:
        i = self.processhive.get_next_index(delta=delta)
        if i is not None:
            self.processhive.activate(i)
            return self.processhive.get(i)
        return None
    
    def remove_chamber(self, index=None):
        self.processhive.remove(index)

    def stop_chamber(self, index=None, timeout=None):
        if index is None:
            chm = self.get_active_chamber()
        else:
            chm = self.get_chamber(index)
        if chm:
            chm.interrupt()
            chm.join(timeout=timeout)
        return chm

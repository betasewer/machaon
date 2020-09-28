#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import queue
import threading
import traceback
import subprocess

from typing import Optional, List, Any

from machaon.object.object import Object, ObjectCollection
from machaon.object.type import TypeModule
from machaon.process import ProcessInterrupted, Process, Spirit, ProcessHive, ProcessChamber
from machaon.package.package import PackageManager, PackageEntryLoadError
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
        self.processhive = None
        self.curdir = "" # 基本ディレクトリ
        self.pkgmanager = None
        self.cmdpackages = []
        self.typemodule = None

    def initialize(self, *, ui, module_dir="", current_dir=None):
        self.ui = ui

        if current_dir is None:
            self.set_current_dir_desktop()
        else:
            self.set_current_dir(current_dir)

        self.processhive = ProcessHive()
        chamber = self.processhive.addnew(self.ui.get_input_prompt())
        #self.processhive.new_desktop("desk1")

        #self.pkgmanager = PackageManager(module_dir)
        #self.pkgmanager.add_to_import_path()

        self.typemodule = TypeModule()
        self.typemodule.add_fundamental_types()
        
        if hasattr(self.ui, "init_with_app"):
            self.ui.init_with_app(self)
        
        self.ui.activate_new_chamber(chamber)
    
    def get_ui(self):
        return self.ui

    def get_type_module(self):
        return self.typemodule
 
    #
    # クラスパッケージを走査する
    #
    # パッケージを導入
    """
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
    """

    #
    # アプリの実行
    #
    def run(self):
        if self.ui is None:
            raise ValueError("App UI must be initialized")
        self.mainloop()

    def exit(self):
        # 停止指示を出す
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
    def eval_object_message(self, message: str):        
        if message == "exit":
            # 終了コマンド
            self.exit()
            return
        elif not message:
            return

        # 実行
        chamber, newchm = self.processhive.new(self, message)

        # 表示を更新する
        if newchm:
            self.ui.activate_new_chamber(chamber)
        else:
            self.ui.update_active_chamber(chamber, updatemenu=False)
        
    # プロセスをスレッドで実行しアクティブにする
    def new_desktop(self, name: str):
        #chamber = self.processhive.new_desktop(name)
        #return chamber
        return 

    #
    # プロセススレッド
    #
    # アクティブプロセスの選択
    def get_active_chamber(self):
        return self.processhive.get_active()
        
    def is_active_chamber(self, index: int):
        return self.processhive.get_active_index() == index

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
            if index=="desktop":
                chm = self.processhive.get_last_active_desktop()
            else:
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
    
    #
    def select_desktop(self, index=None):
        if index is None:
            chm = self.select_chamber("desktop")
        else:
            chm = self.select_chamber(index)
        if chm is None:
            raise ValueError("Desktop Chamber is not found")
        return chm.get_desktop()

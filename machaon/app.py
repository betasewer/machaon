#!/usr/bin/env python3
# coding: utf-8

import configparser
import os
import sys
import shutil
import subprocess

from typing import Optional, List, Any, Text

from machaon.core.object import Object, ObjectCollection
from machaon.core.type import TypeModule
from machaon.process import ProcessInterrupted, Process, Spirit, ProcessHive, ProcessChamber
from machaon.package.package import Package, PackageManager, PackageLoadError, PackageNotFoundError, create_package
from machaon.types.shellplatform import is_osx, is_windows, shellpath
from machaon.types.shell import Path

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
        self.basicdir = "" # 設定ファイルなどを置くディレクトリ
        self.pkgmanager = None
        self.pkgs = []
        self.typemodule = None
        self.objcol = ObjectCollection()
        self._extapps = None # 外部アプリコンフィグファイル
        self._startupmsgs = []

    def initialize(self, *, ui, basic_dir=None, **uiargs):
        if isinstance(ui, str):
            if ui == "tk":
                from machaon.ui.tk import tkLauncher
                ui = tkLauncher(**uiargs)
            else:
                raise ValueError("不明なUIタイプです")

        self.ui = ui

        if basic_dir is None:
            basic_dir = os.path.join(shellpath().get_known_path("documents", approot=self), "machaon")
        self.basicdir = basic_dir

        package_dir = self.get_package_dir()
        self.pkgmanager = PackageManager(package_dir, os.path.join(self.basicdir, "packages.ini"))
        self.pkgmanager.add_to_import_path()
        self.pkgs = []

        self.typemodule = TypeModule()
        self.typemodule.add_fundamental_types()
        
        self.processhive = ProcessHive()
        
        if hasattr(self.ui, "init_with_app"):
            self.ui.init_with_app(self)
        
        self.ui.activate_new_chamber()
        
        self.ui.init_startup_message()
    
    def get_ui(self):
        return self.ui

    def get_type_module(self):
        return self.typemodule
    
    def get_basic_dir(self):
        return self.basicdir
    
    def get_package_dir(self):
        return os.path.join(self.basicdir, "packages")
    
    def get_store_dir(self):
        return os.path.join(self.basicdir, "store")
    
    def get_credential_dir(self):
        return os.path.join(self.basicdir, "credential")
    
    def get_GUID_names_file(self):
        p = os.path.join(self.basicdir, "guid.ini")
        if os.path.exists(p):
            return p
        p = os.path.join(os.path.dirname(__file__), "types\\windows", "guid.ini")
        if not os.path.exists(p):
            raise ValueError("Default guid.init does not exist")
        return p
 
    #
    # クラスパッケージ
    #
    def add_package(self, 
        name, 
        package=None,
        *,
        module=None,
        locked=False,
        delayload=False, 
        type=None,
        separate=True,
        hashval=None,
    ):
        """
        パッケージ定義を追加する。
        Params:
            name(str): パッケージ名
            package(str|Repository): モジュールを含むパッケージの記述　[リモートリポジトリホスト|module|local|local-archive]:[ユーザー/リポジトリ|ファイルパス等]
            module(str): トップモジュール名
            locked(bool): Trueの場合、認証情報を同時にロードする
            delayload(bool): 参照時にロードする
            type(int): モジュールの種類
            separate(bool): site-packageにインストールしない
            hashval(str): パッケージハッシュ値の指定
        """
        newpkg = create_package(name, package, module, type=type, separate=separate, hashval=hashval)
        for pkg in self.pkgs:
            if pkg.name == newpkg.name:
                pkg.assign_definition(newpkg)
                break
        else:
            self.pkgs.append(newpkg)
        
        if locked:
            src = newpkg.get_source()
            from machaon.package.auth import create_credential
            cred = create_credential(self, repository=src)
            src.add_credential(cred)

        if not delayload:
            self.load_pkg(newpkg)
        
        return newpkg
    
    def add_dependency(self,
        name,
        package=None,
        *,
        locked=False,
        separate=True,
        hashval=None,
    ):
        """
        依存パッケージを追加する。
        Params:
            name(str): パッケージ名
            package(str|Repository): モジュールを含むパッケージの記述　[リモートリポジトリホスト|module|local|local-archive]:[ユーザー/リポジトリ|ファイルパス等]
            locked(bool): Trueの場合、認証情報を同時にロードする
            separate(bool): site-packageにインストールしない
            hashval(str): パッケージハッシュ値の指定
        """
        from machaon.package.package import PACKAGE_TYPE_DEPENDENCY
        spectype = PACKAGE_TYPE_DEPENDENCY
        return self.add_package(name, package, locked=locked, type=spectype, separate=separate, hashval=hashval)

    # パッケージ概要を取得する
    def get_package(self, name, *, fallback=True):
        for pkg in self.pkgs:
            if pkg.name == name:
                return pkg
        if not fallback:
            raise PackageNotFoundError(name)
        return None
    
    def enum_packages(self):
        for pkg in self.pkgs:
            yield pkg
    
    # パッケージをローカル上で展開・削除・更新する
    def install_package(self, package: Package):
        yield from self.pkgmanager.install(package, newinstall=True)
    
    def uninstall_package(self, package: Package):
        yield from self.pkgmanager.uninstall(package)
    
    def update_package(self, package: Package):
        yield from self.pkgmanager.install(package, newinstall=False)
    
    # パッケージにアップデートが必要か
    def query_package_status(self, package: Package, *, isinstall=False):
        if isinstall:
            if not package.is_remote_source():
                return "ready"
            if self.pkgmanager.is_installed(package.name): # ローカルにあるかだけ確認
                return "ready"
            else:
                return "none"
        else:
            return self.pkgmanager.query_status(package) # 通信して最新か確かめる

    def load_pkg(self, package: Package, *, force=False):
        """ パッケージオブジェクトから型をロードする """
        if not force and package.is_load_succeeded():
            return True
        
        package.reset_loading()
        for typedef in package.load_type_definitions():
            self.typemodule.define(typedef)
        package.finish_loading()

        return package.is_load_succeeded()
    
    def unload_pkg(self, package):
        """ パッケージオブジェクトの型スコープを削除する """
        if package.once_loaded():
            self.typemodule.remove_scope(package.scope)
        return True
   
    def add_credential(self, cred):
        """ 
        ダウンロードの認証情報をパッケージに追加する。  
        Params:
            target(str): 対象［ホスト名:ユーザー名］
            cred(Any): *認証オブジェクト
        """
        mark = False
        for pkg in self.pkgs:
            src = pkg.get_source()
            if not src.match_credential(cred):
                continue
            src.add_credential(cred)
            mark = True
        
        if not mark:
            raise ValueError("認証情報はどのパッケージにも設定されませんでした")
    
    #
    # 開始直後に実行されるメッセージ
    #
    def add_startup_message(self, *lines):
        self._startupmsgs.extend(lines)
    
    def do_startup_message(self):
        for line in self._startupmsgs:
            self.eval_object_message(line)
        self._startupmsgs.clear()

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
    # コマンド処理の流れ
    #
    def eval_object_message(self, message: str):        
        if not message:
            return
        elif message == "exit":
            # 終了コマンド
            self.exit()
            return
        
        atnewchm = False

        head, *_tails = message.split(maxsplit=1)
        if head == "+":
            # 新規チャンバーを追加してアクティブにする
            atnewchm = True
            message = message[1:].lstrip()
        
        if not message:
            return

        # 実行
        process = self.processhive.new_process(message)
        process.start_process(self) # メッセージを実行する

        # 表示を更新する
        if atnewchm:
            self.ui.activate_new_chamber(process)
        else:
            chamber = self.processhive.append_to_active(process)
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
    
    def addnew_chamber(self, initial_prompt=None):
        return self.processhive.addnew(initial_prompt)
    
    #
    def find_process(self, index):
        # アクティブなチャンバーから検索する
        actchm = self.get_active_chamber()        
        pr = actchm.get_process(index)
        if pr is not None:
            return pr
        # ほかのチャンバーから検索する
        for chm in self.get_chambers():
            if chm is actchm:
                continue
            pr = chm.get_process(index)
            if pr is not None:
                return pr
        return None
    
    #
    def select_object_collection(self):
        return self.objcol

    #
    # 外部アプリ
    #
    @property
    def _external_apps(self):
        if self._extapps is None:
            p = os.path.join(self.basicdir, "apps.ini")
            if os.path.isfile(p):
                cfg = configparser.ConfigParser()
                cfg.read(p)
                self._extapps = cfg
        return self._extapps
    
    def _has_external_app(self, section):
        if self._external_apps:
            return self._external_apps.has_section(section)
        return False

    def open_by_text_editor(self, filepath, line=None, column=None):
        """ テキストエディタで開く。
        Params:
            filepath(str): ファイルパス
            line(int): 行番号
            column(int): 文字カラム番号
        """
        if self._has_external_app("text-editor"):
            editor = None
            lineopt = None
            charopt = None
            
            editor = self._external_apps.get_option("text-editor", "path")
            if line is not None and self._external_apps.has_option("text-editor", "line"):
                lineopt = self._external_apps.get_option("text-editor", "line").format(line)
            if column is not None and self._external_apps.has_option("text-editor", "column"):
                charopt = self._external_apps.get_option("text-editor", "column").format(column)
        
            args = []
            args.append(editor)
            args.append(filepath)
            if lineopt is not None:
                args.append(lineopt)
            if charopt is not None:
                args.append(charopt)
            subprocess.Popen(args, shell=False)
        
        else:
            from machaon.types.shellplatform import shellpath
            shellpath().open_by_system_text_editor(filepath, line, column)

#
# 
#
def deploy_directory(path):
    """
    machaonディレクトリを配備する。
    Params:
        path(Path): 配備先のディレクトリ
    """
    machaon = path / "machaon"
    packages = machaon / "packages"
    credentials = machaon / "credential"
    store = machaon / "store"
    local = machaon / "local"
    
    # ディレクトリの作成
    for p in (packages, credentials, store, local):
        p.makedirs()
    
    # 空ファイルの配置
    configs = Path(__file__).dir() / "configs"
    machaon.copy_from(configs / "readme.txt")
    machaon.copy_from(configs / "apps.ini")
    credentials.copy_from(configs / "credential.ini")
    
    # スタートアップスクリプトの配置
    if is_osx():
        main = path.copy_from(configs / "main.py")
        # main.pyのパスを書き込んだ立ち上げスクリプトを生成
        deploy_osx_start_command(main)
    
    elif is_windows():
        path.copy_from(configs / "main.py")

def deploy_osx_start_command(main):
    from machaon.types.file import TextFile
    starter = main.with_name("start.command")
    configs = Path(__file__).dir() / "configs"
    starter_template = TextFile(configs / "osx" / "start.command").text()
    with TextFile(starter, encoding="utf-8").write_stream() as fo:
        fo.write(starter_template.format(main))
    # 実行権限を与える
    os.chmod(starter.get(), 0o755)
    return starter


def transfer_deployed_directory(app, src, destdir):
    """
    machaonディレクトリを移動する。
    Params:
        src(Path): 移動元のmachaonディレクトリ
        destdir(Path): 移動先のディレクトリ（存在しないパスか、空の環境）
    """
    destmachaon = destdir / "machaon"
    if destmachaon.isdir():
        for dirpath, _dirnames, filenames in os.walk(destmachaon.get()):
            if len(filenames)>0:
                raise ValueError("移動先に{}が存在します。全てのファイルを削除してください".format(os.path.join(dirpath, filenames[0])))
    
    shutil.move(src.get(), destmachaon.get())

    main = destdir / "main.py"
    shutil.move((src.up() / "main.py").get(), main.get())
    
    if is_osx():
        oldcmd = destdir / "start.command"
        if oldcmd.isfile():
            oldcmd.remove()
        deploy_osx_start_command(main)


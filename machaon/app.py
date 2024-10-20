#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import shutil
from collections import namedtuple

from machaon.core.object import Object, ObjectCollection
from machaon.core.type.typemodule import TypeModule
from machaon.core.error import ErrorSet
from machaon.core.context import InvocationContext
from machaon.process import Process, ProcessSentence, Spirit, TempSpirit, ProcessHive, ProcessChamber, ProcessSentence
from machaon.package.package import PackageManager
from machaon.package.auth import CredentialDir
from machaon.platforms import is_osx, is_windows, shellpath
from machaon.types.shell import Path
from machaon.ui.keycontrol import HotkeySet, KeyController
from machaon.ui.external import ExternalApps

#
StartupVariable = namedtuple("StartupVariable", ["name", "value", "typename"])

#
#
#
class AppRoot:
    """
    アプリのUI、設定情報、グローバルなオブジェクトの辞書を保持する
    """
    def __init__(self):
        self.ui = None

        self.basicdir = "" # 設定ファイルなどを置くディレクトリ
        self.pkgmanager = None
        self.pkgoptions = {}

        self.processhive = ProcessHive()
        self.typemodule = TypeModule()
        self.objcol = ObjectCollection()

        self.keycontrol = KeyController()
        self.extapps = ExternalApps()

        self._startupmsgs = []
        self._startupvars = []
        self._startupignores = {}
        self._startuperrors = ErrorSet("アプリケーション初期化")

    def initialize(self, *, ui, basic_dir=None, ignore_args=False, ignore_packages=None, ignore_hotkeys=None, **uiargs):
        """ 初期化前に初期設定を指定する """
        if not ignore_args:
            # コマンドライン引数を読み込む
            from machaon.ui.main import initialize_app_args
            initargs = initialize_app_args(self, ui=ui, basic_dir=basic_dir, **uiargs)
            ui = initargs.pop("ui")
            basic_dir = initargs.pop("basic_dir")
        else:
            initargs = uiargs
        
        # UIを設定する
        if ui is None:
            ui = "shell"
        from machaon.ui import new_launcher
        self.ui = new_launcher(ui, **initargs)

        # パス
        if basic_dir is None:
            basic_dir = get_default_basic_dir()
        self.basicdir = basic_dir

        # 設定フラグ
        self.ignore_at_startup("packages", ignore_packages)
        self.ignore_at_startup("hotkey", ignore_hotkeys)

    def initialize_as_server(self, **args):
        """ サーバー実行用に初期化し、サーバーアプリを返す """
        self.initialize(ui="headless", ignore_hotkeys=True, **args)
        from machaon.ui.server.macasocket import machaon_server
        return machaon_server(self)

    def get_ui(self):
        return self.ui

    def get_type_module(self):
        return self.typemodule
    
    def get_basic_dir(self):
        return Path(self.basicdir)
    
    def get_package_dir(self):
        return Path(self.basicdir) / "packages"
    
    def get_store_dir(self):
        return Path(self.basicdir) / "store"
    
    def get_credential_dir(self):
        return CredentialDir(Path(self.basicdir) / "credential")
    
    def get_log_dir(self):
        # デフォルトで存在しないディレクトリ
        return (Path(self.basicdir) / "log").makedirs()

    def get_temp_dir(self, **kwargs):
        from machaon.types.shell import UserTemporaryDirectory
        return UserTemporaryDirectory(self.basicdir, **kwargs)

    def get_external_applist(self):
        return self.get_basic_dir() / "apps.ini"
    
    def get_GUID_names_file(self):
        p = self.get_basic_dir() / "guid.ini"
        if p.exists():
            return p
        return None
    
    def get_keybind_file(self):
        p = self.get_basic_dir() / "keybind.ini"
        if p.exists():
            return p
        return None

    def get_local_dir(self, appname):
        return (self.get_basic_dir() / "local" / appname).makedirs()

    def get_local_config(self, appname, filename, *, fallback=False):
        p = self.get_local_dir(appname) / filename
        if not p.isfile():
            if fallback:
                return None
            raise ValueError("{}は存在しません".format(p))
        import configparser
        cfg = configparser.ConfigParser()
        cfg.read(p, encoding="utf-8")
        return cfg

    #
    # 
    #
    def ignore_at_startup(self, name, b=True):
        """ 起動を無視するフラグを立てる """
        if b is None:
            return
        self._startupignores[name] = b

    def is_ignored_at_startup(self, name):
        """ 起動を無視するフラグを調べる """
        return self._startupignores.get(name)
    
    def boot_ui(self):
        """ UIを立ち上げる """
        if self.ui is None:
            raise ValueError("App UI must be initialized")
        if hasattr(self.ui, "init_with_app"):
            self.ui.init_with_app(self)
        self.ui.activate_new_chamber() # 空のチャンバーを追加する
    
    def boot_core(self, spirit=None, *, fundamentals=False):
        """ コア機能を立ち上げる """
        if fundamentals: # 既に初期化済みでない場合はここで
            # 基本型をロードする
            try:
                self.typemodule.add_fundamentals() 
            except Exception as e:
                self._startuperrors.add(e, message="基本型のロード")

        # パッケージマネージャの初期化
        self.pkgmanager = PackageManager(
            self.get_package_dir(),
            self.get_credential_dir(),
            self.pkgoptions
        )
        if not self.is_ignored_at_startup("packages"):
            try:
                package_list_dir = self.get_basic_dir()
                self.pkgmanager.load_packages(package_list_dir)
                self.pkgmanager.load_database(package_list_dir / "packages.ini")
                self.pkgmanager.add_to_import_path()
                self.pkgmanager.check_after_loading()
            except Exception as e:
                self._startuperrors.add(e, message="パッケージマネージャの初期化")

        # 標準モジュールのロードを予約する
        self.typemodule.reserve_adding_types("default")
        
        # ホットキーの監視を有効化する
        if KeyController.available and not self.is_ignored_at_startup("hotkey"):
            try:
                self.keycontrol.start(self)
                if spirit: 
                    spirit.post("message", "入力リスナーを立ち上げました")
            except Exception as e:
                self._startuperrors.add(e, message="ホットキーの監視")

        self._startuperrors.throw_if_failed()

    def boot_startup_variables(self, context):
        """ スタートアップ変数をロードする """
        if self.is_ignored_at_startup("variables"):
            return
        count = 0
        for v in self._startupvars:
            o = context.new_object(v.value, conversion=v.typename)
            self.objcol.push(v.name, o)
            count += 1
        self._startupvars.clear()
        return count
    
    #
    # クラスパッケージ
    #    
    # パッケージの追加・削除を行うマネージャ
    def package_manager(self):
        return self.pkgmanager
    
    def add_package_option(self, pkgname, *, 
        no_dependency = None
    ):
        """ 
        パッケージのインストール時にローカルなオプションを設定する 
        Params:
            no_dependency: 依存パッケージを自動でインストールしない
        """
        opts = self.pkgoptions.setdefault(pkgname, {})
        opts["no_dependency"] = no_dependency

    #
    # メッセージ
    #
    def add_startup_message(self, line):
        """ 開始直後に自動で実行されるメッセージ """
        self._startupmsgs.append(line)
    
    def post_stray_message(self, tag, value=None, **options):
        """ アクティブなチャンバーにプロセス独立のメッセージを投稿する """
        chm = self.chambers().get_active()
        if chm is not None:
            chm.post_chamber_message(tag, value, **options)
        else:
            self._startupmsgs.append("'{}: {}' =".format(tag, value))

    def add_startup_variable(self, name, value, typename=None):
        """ 開始直後に自動で追加される引数 """
        self._startupvars.append(StartupVariable(name, value, typename))
    

    #
    # グローバルなホットキー
    #
    def add_hotkey(self, label, *, key, message):
        """
        グローバルなホットキーを定義する。
        Params:
            label(str): 定義名
            key(str): キーの組み合わせ
            message(str): 実行するメッセージ
        """
        self.keycontrol.add_hotkey(label, key, message)

    def add_hotkey_set(self, target, *, ignition, function_method=None):
        """
        一連のグローバルなホットキーを定義する。
        Params:
            target(str): HotKeySetを返す関数のシンボル
            ignition(str): 共通の修飾キー
            function_method(str): メッセージ関数に適用するメソッド　デフォルトでclipboard-apply
        """
        from machaon.core.importer import attribute_loader
        loadfn = attribute_loader(target)()
        keyset = loadfn()
        if not isinstance(keyset, HotkeySet):
            raise TypeError("{}はHotKeySet型のオブジェクトを返さなければなりません".format(target))
        function_method = function_method or "apply-clipboard"
        keyset.install(self, ignition, function_method)

    def enum_hotkeys(self):
        """
        グローバルなホットキーの定義をリストアップする
        Returns:
            List[Tuple[str, str]]: キーとメッセージの組のリスト 
        """
        return self.keycontrol.enum_hotkeys()

    def push_key(self, k):
        """
        キーを押して離す
        Params:
            key(str):
        """
        self.keycontrol.push(k)
    
    #
    # アプリの実行
    #
    def run(self, *, ignore_args=False):
        # UIを作成
        self.boot_ui()

        # 自動実行メッセージを立ち上げるメッセージを仕込む
        startupmsgs = ["@@startup", *self._startupmsgs] # 初期化処理を行うメッセージを先頭に追加する
        chm = self.chambers().get_active()
        chm.post_chamber_message("eval-message-seq", messages=startupmsgs, chamber=chm)
        self._startupmsgs.clear()

        # 基本型を先に登録：初期化処理メッセージを解読するために必要
        self.typemodule.add_fundamentals() 

        # メインループ
        self.ui.run_mainloop()

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

    def interrupt(self):
        # 全てのプロセスに停止フラグを立てる
        self.processhive.interrupt_all()

    #
    # コマンド処理の流れ
    #
    def eval_object_message(self, sentence: ProcessSentence, *, norun=False):
        """ メッセージを実行しプロセスを起動する 
        Returns:
            Int: 起動されたプロセスID
        """
        if sentence.is_empty():
            return None
        elif sentence.at_exit():
            # 終了コマンド
            self.exit()
            return None

        # 実行
        process = self.processhive.new_process(sentence)
        context = self.create_root_context(process)

        # 表示を更新する
        if sentence.at_new_chamber():
            self.ui.activate_new_chamber(process)
        else:
            chamber = self.processhive.get_active()
            if chamber.add(process) is None:
                return None # 他のプロセスが実行中

        runner = AppProcessStarter(process, context)
        if not norun:
            runner() # メッセージを実行する
        return runner
    
    def create_root_context(self, process=None):
        """ 実行コンテキストを作成する """
        spirit = Spirit(self, process)
        context = InvocationContext(
            input_objects=self.objcol, 
            type_module=self.typemodule,
            spirit=spirit,
            herepath=self.get_basic_dir()
        )
        return context

    def create_process(self, message=None):
        """ 未開始のプロセスを生成する """
        if message is not None:
            sentence = ProcessSentence(message)
        else:
            sentence = None
        return self.processhive.new_process(sentence)

    def temp_spirit(self, **kwargs):
        """ プロセスを介さないスピリットを作成 """
        return TempSpirit(self, **kwargs)
 
    #
    # プロセススレッド
    #
    def chambers(self):
        return self.processhive

    def find_process(self, index):
        # アクティブなチャンバーから検索する
        actchm = self.chambers().get_active()
        pr = actchm.get_process(index)
        if pr is not None:
            return pr
        # ほかのチャンバーから検索する
        for chm in self.chambers().get_chambers():
            if chm is actchm:
                continue
            pr = chm.get_process(index)
            if pr is not None:
                return pr
        return None

    #
    # 外部アプリ
    #
    def open_by_text_editor(self, filepath, line=None, column=None):
        """ テキストエディタで開く。
        Params:
            filepath(str): ファイルパス
            line(int): 行番号
            column(int): 文字カラム番号
        """
        self.extapps.open_by_text_editor(self, filepath, line, column)


def get_default_basic_dir():
    d = Path.known("documents")
    if d is None:
        d = Path.known("home")
    return (d / "machaon").get()

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
    configs = Path(__file__).dir() / "configs" / "deploy"
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

    else:
        # generic
        path.copy_from(configs / "main.py")


def deploy_osx_start_command(main):
    from machaon.types.file import TextFile
    starter = main.with_name("start.command")
    configs = Path(__file__).dir() / "configs" / "deploy"
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


class AppProcessStarter:
    def __init__(self, process, context):
        self.process: Process = process
        self.context: InvocationContext = context

    def __call__(self):
        return self.process.start_process(self.context) 

#
#
#
class AppStarter:
    def __init__(self, root: AppRoot):
        self.root = root
        self._adder = None

    def __getitem__(self, name):
        if self._adder is None:
            raise ValueError()
        def _add(*args, **kwargs):
            self._adder(args, kwargs, name)
            return self
        return _add

    def _set_adder(self, adder):
        self._adder = adder
    
    def hotkeys(self):
        @self._set_adder
        def _add_hotkey(args, kwargs, label):
            self.root.add_hotkey(label, *args, **kwargs)
        return self
    
    def messages(self, *lines):
        for line in lines:
            self.root.add_startup_message(line)
        return self

    def end(self):
        return self.root


def create_app(*args, **kwargs):
    root = AppRoot()
    root.initialize(*args, **kwargs)
    return AppStarter(root)


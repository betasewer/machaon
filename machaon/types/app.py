#!/usr/bin/env python3
# coding: utf-8
import os
from machaon.core.importer import PyModuleLoader
from machaon.package.package import PackageManager, create_module_package
from machaon.types.package import AppPackageType
from machaon.app import AppRoot, deploy_directory, transfer_deployed_directory

logo = """
8b    d8    db     dP""b8 88  88    db     dP"Yb  88b 88 
88b  d88   dPYb   dP   `" 88  88   dPYb   dP   Yb 88Yb88 
88YbdP88  dP__Yb  Yb      888888  dP__Yb  Yb   dP 88 Y88 
88 YY 88 dP""""Yb  YboodP 88  88 dP""""Yb  YbodP  88  Y8
  message-oriented style Python application environment                         
"""[1:]

class RootObject:
    """ @type
    アプリケーションを表すグローバルなオブジェクト。
    """

    def __init__(self, context):
        self.context = context
    
    @property
    def root(self) -> AppRoot:
        return self.context.root

    #
    # メソッド
    #
    def startup(self, spirit):
        """ @task
        起動画面を表示し、パッケージをロードする。
        """
        isfullform = self.root.get_ui().is_async
        if isfullform:
            spirit.post('message', "Welcome to")
            spirit.post('message-em', logo)

        if isfullform:
            spirit.post("message", "言語エンジンを準備します")
        self.root.boot_core(spirit)

        if not self.root.is_ignored_at_startup("packages"):
            if isfullform:
                spirit.post("message", "パッケージをロードします")
            for pkg in self.root.enum_packages():
                spirit.post("message", "{}".format(pkg.name), nobreak=True)
                self.root.load_pkg(pkg)
                status = AppPackageType().status(pkg, spirit)
                spirit.post("message", " -> {}".format(status))

            try:
                self.root.check_pkg_loading()
            except Exception as e:
                spirit.post("error", str(e))

        count = self.root.load_startup_variables(self.context)
        if count > 0:
            spirit.post("message", "{}個の変数がロード済みです".format(count))

        if isfullform:
            spirit.post("message", "")
            spirit.post("message", "ヘルプ")
            spirit.post("message", "")

    def load_using_packages(self, app, *names):
        """ @task alias-name [using]
        モジュールを読み込む
        Params:
            +names(Str):
        """
        defmods = []
        pkgs = []
        from machaon.core.symbol import DefaultModuleNames
        for name in names:
            if name in DefaultModuleNames:
                defmods.append(name)
            else:
                pkg = self.root.get_package(name)
                if pkg is None:
                    # パッケージを追加する
                    pkg = create_module_package(name)
                    self.root.add_package(pkg)
                pkgs.append(pkg)
        
        # 読み込みを行う
        if defmods:
            app.post("message", "標準モジュール = '{}'".format(", ".join(defmods)))
            self.root.get_type_module().add_default_modules(defmods)
        
        for pkg in pkgs:
            app.post("message", "パッケージ = '{}' ".format(pkg.name), nobreak=True)
            self.root.load_pkg(pkg)
            app.post("message", " -> {}".format(AppPackageType().status(pkg, app)))
        
        self.root.check_pkg_loading()

    def types(self, spirit):
        """ @task
        使用可能な型を列挙する。
        Params:
        Returns:
            Sheet[](name, doc, describer): 型のリスト
        """
        with spirit.progress_display():
            for name, t, error in self.context.type_module.enum(geterror=True):
                spirit.interruption_point(progress=1)
                entry = {
                    "name" : name,
                }
                if error is not None:
                    entry["doc"] = "!!!型の読み込みに失敗!!!"
                    entry["describer"] = error
                else:
                    entry["doc"] = t.doc
                    entry["describer"] = t.get_describer_qualname()
                yield entry
        
    def subtypes(self, spirit):
        """ @task
        使用可能な型を列挙する。
        Params:
        Returns:
            Sheet[ObjectCollection](name, doc, scope, location): 型のリスト
        """
        with spirit.progress_display():
            for scopename, name, t, error in self.context.type_module.enum_all_subtypes(geterror=True):
                spirit.interruption_point(progress=1)
                entry = {
                    "name" : name,
                }
                if error is not None:
                    entry["doc"] = "!!!" + error.summarize()
                    entry["type"] = error
                else:
                    entry["doc"] = t.doc
                    entry["scope"] = scopename
                    entry["location"] = t.get_describer_qualname()
                yield entry
    
    def vars(self):
        """@method
        全ての変数を取得する。
        Returns:
            ObjectCollection: 辞書
        """
        return self.context.input_objects
    
    def store_objects(self):
        """ @method alias-name [store]
        machaonフォルダのファイル名を列挙する。
        Returns:
            Sheet[Str]: 名前のリスト
        """
        from machaon.core.persistence import enum_persistent_names
        return enum_persistent_names(self.root)

    def packages(self):
        """ @method
        パッケージを取得する。
        Returns:
            Sheet[Package](name, source, scope, status): パッケージリスト
        """
        return list(self.root.enum_packages())
    
    def startup_errors(self):
        """ @method
        パッケージ読み込みのエラーを取得する。
        Returns:
            Sheet[Error]: エラーリスト
        """
        for pkg in self.root.enum_packages():
            yield from pkg.get_load_errors()
    
    def context_(self):
        """ @method alias-name [context]
        現在の呼び出しコンテキストを取得する。
        Returns:
            Context: 
        """
        return self.context
    
    def spirit_(self):
        """ @method alias-name [spirit]
        現在の呼び出しコンテキストのSpiritを取得する。
        Returns:
            Any:
        """
        return self.context.spirit

    #
    # クリアする
    #
    def _clear_processes(self, app, pred):
        """ プロセスの実行結果とプロセス自体を削除する。 """
        chm = self.root.chambers().get_active()
        pids = chm.drop_processes(pred=pred)
        app.get_ui().drop_screen_text(pids)
        
    def clear(self, app):
        """ @method spirit [cla]
        現在のチャンバーの全ての実行結果を削除する。
        """
        self._clear_processes(app, None)
    
    def clear_except_last(self, app):
        """ @method spirit [cl]
        直前のプロセスを除いてすべてを削除する。
        """
        chm = self.root.chambers().get_active()
        index = chm.last_process.get_index()
        def is_lastpr(pr):
            return pr.get_index() != index
        self._clear_processes(app, is_lastpr)

    def clear_failed(self, app):
        """ @method spirit [claf]
        エラーを返した実行結果をすべて削除する。
        """
        def is_failed(pr):
            return pr.is_failed()
        self._clear_processes(app, is_failed)
    
    #
    # 
    #
    def keymap(self):
        """ @method
        ショートカットキーの一覧を表示する。 
        Returns:
            Sheet[](key, command):
        """
        # ショートカットキー
        keymap = self.root.get_ui().get_keymap()
        rets = []
        for cmd in keymap.all_commands():
            keys = [("+".join(x.key), x.when) for x in cmd.keybinds]
            if keys:
                key = ", ".join(["{} [{}]".format(*x) for x in keys])
            else:
                key = "割り当てなし"

            rets.append({
                "command" : cmd.command,
                "key" : key
            })
        
        # グローバルホットキー
        for hkey in self.root.enum_hotkeys():
            rets.append({
                "command" : "{}: {}".format(hkey.get_label(), hkey.get_message()),
                "key" : hkey.get_key()
            })

        return rets

    def push_key(self, k):
        """ @method
        キーボードのキーを押す。
        Params:
            k(str):
        """ 
        self.root.push_key(k)
    
    #
    #
    #
    def dump_screen(self, app, path):
        """ @task
        アクティブなチャンバーに表示されたテキストをファイルに書き出す。
        Params:
                path(Path): 出力ファイル名
        """
        t = self.root.get_ui().get_screen_texts()
        with open(path.get(), "w", encoding="utf-8") as fo:
            fo.write(t)
        
    def inspect_message(self, app):
        """ @task
        アクティブなチャンバーの処理が済んだメッセージを詳細な形式で表示する。
        """
        chm = self.root.chambers().get_active()
        for msg in chm.get_handled_messages():
            lines = []
            lines.append('"{}"'.format(msg.text))
            lines.append("tag={}".format(msg.tag))
            for k, v in msg.args.items():
                lines.append("{}={}".format(k, v))
            app.post("message", "\n".join(lines) + "\n")

    def use_ansi(self, b=True):
        """ @method
        出力でANSIエスケープシーケンスを使用する。
        Params:
            b?(bool):
        """
        ui = self.root.get_ui()
        if hasattr(ui, "use_ansi"):
            ui.use_ansi(b)

    def themes(self):
        """ @method 
        UIのカラーテーマの一覧を表示する。
        Returns:
            Sheet[ShellTheme](name):
        """
        from machaon.ui.theme import theme_constructors
        for ctor in theme_constructors.values():
            yield ctor()
        
    #
    #
    #
    def deploy(self, app, path):
        """ @task
        machaonディレクトリを配置する。
        Params:
            path(Path):
        """
        deploy_directory(path)
    
    def trans_deploy(self, app, path):
        """ @task
        machaonディレクトリを移譲する。
        Params:
            path(Path): 新たにmachaonが配備されるディレクトリ
        """
        from machaon.types.shell import Path
        transfer_deployed_directory(app, Path(self.root.get_basic_dir()), path)
    
    def machaon_update(self, context, app, forceinstall=False):
        """ @task context
        machaonをリポジトリからダウンロードして更新する。
        Params:
            forceinstall?(bool): 
        """
        # インストールディレクトリ
        curmodule = PyModuleLoader("machaon")
        location = curmodule.load_filepath()
        if location is None:
            raise ValueError("インストール先が不明です")
        
        installdir = os.path.normpath(os.path.join(os.path.dirname(location), ".."))
        lock = os.path.normpath(os.path.join(installdir, "..", ".machaon-update-lock"))
        if os.path.isfile(lock):
            raise ValueError("{}: 上書きしないようにロックされています".format(lock))

        # パッケージを定義する
        from machaon.package.package import create_package, package_extraction, run_pip
        pkg = create_package("machaon", "github:betasewer/machaon")
        status = self.root.query_package_status(pkg)
        if status == "latest":
            app.post("message", "最新の状態です")
            if not forceinstall:
                return
        elif status == "unknown":
            app.post("error", "不明：パッケージの状態の取得に失敗")
            if not forceinstall:
                return
        elif status == "notfound" or status == "none":
            pass
        else:
            app.post("message", "より新しいバージョンが存在します")

        # ダウンロードしてインストールする
        def operation(pkg, _options):
            with package_extraction(pkg) as extraction:
                for status in extraction:
                    if status == PackageManager.EXTRACTED_FILES:
                        if status.path is None:
                            return
                        yield PackageManager.PIP_INSTALLING
                        yield from run_pip(installtarget=status.path, installdir=installdir, options=["--upgrade"])
                    else:
                        yield status
        
        if AppPackageType().display_download_and_install(app, pkg, operation):
            app.post("message", "machaonを更新しました。次回起動時に反映されます")

    def update_all(self, context, app):
        """ @task context
        すべてのパッケージに更新を適用する。
        """
        apppkg = AppPackageType()
        for pkg in self.root.enum_packages():
            apppkg.update(pkg, context, app)

    def stringify(self):
        """ @meta """
        return "<root>"
    
    def test_colors(self, app, text="サンプルテキスト"):
        """ @task
        テキストの色をテストする。
        Params:
            text?(str): 
        """
        app.post("message", "=== カラーテスト")
        with app.indent_post("    "):
            app.post("message", text)
            app.post("message-em", "[強調]" + text)
            app.post("input", "[入力]" + text)
            app.post("hyperlink", "[リンク]" + text)
            app.post("warn", "[注意]" + text)
            app.post("error", "[エラー発生]" + text)
        app.post("message", "===")
    
    def test_progress(self, app):
        """@task
        プログレスバーをテストする。
        """
        app.start_progress_display(total=50)
        for _ in range(50):
            app.interruption_point(progress=1, wait=0.5)
        app.finish_progress_display()

    def test_graphic(self, app):
        """ @task
        図形を描画する。
        """
        app.post("canvas", app.new_canvas("cv1", width=200, height=400)
            .rectangle_frame(coord=(2,2,100,200), color="#00FF00")
            .rectangle_frame(coord=(50,50,200,250), color="#FF0000", dash=",")
            .rectangle_frame(coord=(10,100,90,300), color="#0000FF")
        )
        app.post("canvas", app.new_canvas("cv2", width=200, height=400)
            .oval(coord=(10,10,200,400), color="#004444")
            .rectangle(coord=(2,2,100,200), color="#00FF00")
            .rectangle(coord=(50,50,200,250), color="#FF0000", stipple="grey50")
            .rectangle(coord=(10,100,90,300), color="#0000FF")
        )

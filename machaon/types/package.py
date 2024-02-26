import os

from machaon.core.importer import PyModuleInstance, module_loader, walk_modules
from machaon.package.package import Package, PackageManager


class AppPackageType:
    """ @type trait [Package]
    プログラムパッケージを操作するための型。
    ValueType: 
        machaon.package.package.Package
    """
    def get_manager(self, spirit_or_context) -> PackageManager:
        return spirit_or_context.root.package_manager()

    def name(self, package: Package):
        """ @method
        パッケージ名
        Returns:
            Str:
        """
        return package.name
    
    def status(self, package: Package, spirit):
        """ @method spirit
        パッケージの状態を示す文字列
        Returns:
            Str:
        """
        is_installed = self.get_manager(spirit).is_installed(package)

        if package.is_ready():
            if is_installed:
                return "準備完了"
            else:
                return "準備完了 (インストールの記録なし)"
        else:
            if is_installed:
                return "利用不可（インストールの記録あり）"
            else:
                return "利用不可"
    
    def update_status(self, package: Package, spirit):
        """ @task
        更新状態を示す文字列。
        リモートソースに接続して最新かどうか確認する。
        Returns:
            Str:
        """
        installstatus = self.get_manager(spirit).query_update_status(package, fallback=False)
        if "none" == installstatus:
            return "ローカルに存在しません"
        elif "old" == installstatus:
            return "アップデートがあります"
        elif "latest" == installstatus:
            return "最新の状態です"
        
        return "unexpected status：{}".format(installstatus)

    def source(self, package: Package):
        """ @method
        ソースを示す文字列
        Returns:
            Str:
        """
        return package.get_source_signature()
    
    def entrypoint(self, package: Package):
        """ @method
        エントリポイントとなるモジュール
        Returns:
            Str:
        """
        return package.entrypoint
    
    def hash(self, package: Package, context):
        """ @method context
        インストールされているバージョンのハッシュ値
        Returns:
            Str:
        """
        h = self.get_manager(context).get_installed_hash(package)
        if not h:
            return "<no-hash>"
        return h

    def latest_hash(self, package: Package, app):
        """ @task
        パッケージの最新のハッシュ値
        Returns:
            Str:
        """
        h = package.load_latest_hash()
        if not h:
            return "<no-hash>"
        return h

    def location(self, package: Package, app):
        """ @task
        ファイルシステム上の場所
        Returns:
            Path:
        """
        return self.get_manager(app).get_installed_location(package)
    
    def install(self, package: Package, app, *options):
        """ @task
        パッケージをインストールし、ロードする。
        Params:
            *options(str):
        """
        self.display_update(package, app, options=options, forceinstall=True)
    
    def update(self, package: Package, app, *options):
        """ @task
        パッケージを更新し、再ロードする。
        Params:
            *options(Str):
        """
        self.display_update(package, app, options=options, forceupdate=True)
        
    # 
    def display_download_and_install(self, app, routine):
        for state in routine:
            # ダウンロード中
            if state == PackageManager.DOWNLOAD_START:
                app.post("message", "パッケージのダウンロードを開始 --> {}".format(state.url))
                app.start_progress_display(total=state.total)
            elif state == PackageManager.DOWNLOADING:
                app.interruption_point(progress=state.size)
            elif state == PackageManager.DOWNLOAD_END:
                app.finish_progress_display()
            elif state == PackageManager.DOWNLOAD_ERROR:
                app.post("error", "ダウンロードに失敗しました：\n  {}".format(state.error))
                return False

            # インストール処理
            elif state == PackageManager.PIP_INSTALLING:
                app.post("message", "pipを呼び出し")
            elif state == PackageManager.PIP_MSG:
                app.post("message", "  " + state.msg)
            elif state == PackageManager.PIP_END:
                if state.returncode == 0:
                    app.post("message", "pipによるインストールが成功し、終了しました")
                elif state.returncode is None:
                    pass
                else:
                    app.post("error", "pipによるインストールが失敗しました コード={}".format(state.returncode))
                    return False
        return True
        
    def display_update(self, package: Package, app, options=None, *, forceinstall=False, forceupdate=False):
        if not package.is_remote_source():
            app.post("message", "リモートソースの指定がありません")
            return

        app.post("message-em", "パッケージ'{}'の更新を開始".format(package.name))
        rep = package.get_source()
        if rep:
            app.post("message", "ソース = {}".format(rep.get_source()))
        
        # パッケージの状態を調べる
        status = self.get_manager(app).query_update_status(package)
        if status == "none":
            app.post("message", "新たにインストールします")
        elif status == "old":
            app.post("message", "より新しいバージョンが存在します")
            if not forceinstall and not forceupdate:
                return
        elif status == "latest":
            app.post("message", "最新の状態です")
            if not forceinstall and not forceupdate:
                return
        elif status == "unknown":
            app.post("error", "不明：パッケージの状態の取得に失敗")
            return

        # ダウンロード・インストール処理
        install_type = PackageManager.INSTALL_TARGET_VERSION
        if forceupdate:
            install_type = PackageManager.INSTALL_LATEST_VERSION
        
        self.display_download_and_install(app, 
            self.get_manager(app).install(package, install_type, options)
        )

        # 追加依存モジュールを表示する
        inimodule = package.load_initial_declaration()
        for name, ready in inimodule.check_extra_packages_ready().items():
            if not ready:
                app.post("warn", "パッケージ'{}'がありません。手動で追加する必要があります".format(name))

        app.post("message-em", "パッケージ'{}'の更新が完了".format(package.name))
        return

    def uninstall(self, package: Package, app):
        """ @task
        パッケージをアンインストールする。
        """
        if package.is_module_source():
            app.post("message", "このパッケージはアンインストールできません")
            return
    
        app.post("message-em", "パッケージ'{}'のアンインストールを開始".format(package.name))

        for state in self.get_manager(app).uninstall(package):
            if state == PackageManager.UNINSTALLING:
                app.post("message", "ファイルを削除")
            elif state == PackageManager.PIP_UNINSTALLING:
                app.post("message", "pipを呼び出し")
            elif state == PackageManager.PIP_MSG:
                app.post("message", "  " + state.msg)
            elif state == PackageManager.PIP_END:
                if state.returncode == 0:
                    app.post("message", "pipによるアンインストールが成功し、終了しました")
                elif state.returncode is None:
                    pass
                else:
                    app.post("error", "pipによるアンインストールが失敗しました コード={}".format(state.returncode))
                    return

        app.post("message", "削除完了")
    
    def stringify(self, package):
        """ @meta """
        return "<Package {}>".format(package.name)



#
#
#
class Module():
    """ @type [PyModule]
    Pythonのモジュール。
    """
    def __init__(self, m) -> None:
        self._m = m
    
    def mloader(self):
        return PyModuleInstance(self._m)
    
    def constructor(self, value):
        """ @meta 
        Params:
            Any:
        """
        from machaon.types.shell import Path
        if isinstance(value, str):
            # モジュール名
            loader = module_loader(value)
            return Module(loader.load_module())
        elif isinstance(value, Path):
            # パス
            loader = module_loader(value.basename(), location=value.get())
            return Module(loader.load_module())
        elif isinstance(value, type(os)):
            # モジュールインスタンス
            return Module(value)
        else:
            raise TypeError("")
    
    def name(self):
        """ @method
        モジュール名
        Returns:
            Str:
        """
        return self._m.__name__
    
    def location(self):
        """ @method
        ファイルの場所
        Returns:
            Path:
        """
        mod = self.mloader()
        return mod.load_filepath()
    
    def version(self):
        """ @method
        バージョン番号
        Returns:
            Str:
        """
        return self._m.__version__
    
    def module(self):
        """ @method
        モジュール。
        Returns:
            Any:
        """
        return self._m

    def __getitem__(self, name):
        """
        モジュールのメンバを得る。
        """
        return getattr(self._m, name)

    def scan(self, app):
        """ @task
        このモジュールに定義された型を収集しログを表示する。登録はしない。
        Returns:
            Sheet[ObjectCollection]:
        Decorates:
            @ view: typename qualname error
        """
        mod = self.mloader()
        elems = list(mod.scan_print_type_definitions(app))
        return elems

    def walk(self, app):
        """ @task
        サブモジュール名を検索して列挙する。
        Returns:
            Tuple[str]:
        """
        mod = self.mloader()
        if mod.is_package():
            p = mod.load_filepath()
            if p is None:
                return
            if os.path.isfile(p):
                d = os.path.dirname(p)
            else:
                d = p
            for loader in walk_modules(d, self.name()):
                name = loader.get_name()
                yield name
        else:
            yield mod.get_name()

    def walkscan(self, app):
        """ @task
        パッケージに定義された型を収集しログを表示する。登録はしない。
        Returns:
            Sheet[Dict]:
        Decorates:
            @ view: typename qualname error
        """
        elems = []
        mod = self.mloader()
        for modloader in mod.load_all_module_loaders():
            for df in modloader.scan_print_type_definitions(app):
                elems.append(df)
        return elems
    
    def extra_requires(self):
        """ @method [extra]
        このモジュールが追加で依存するパッケージ名。
        Returns:
            Sheet[Dict]: 
        Decorates:
            @ view: name ready
        """
        mod = self.mloader()
        return [{"name":x, "ready":y} for x, y in mod.check_extra_packages_ready().items()]

    def load_definition(self, context, name):
        """@task nospirit context
        属性を取得し、値がクラスであれば型定義として読み込む。
        Params:
            name(Str): 属性名
        Returns:
            Type: 読み込まれた型
        """
        m = self.mloader()
        v = m.load_attr(name)
        if not isinstance(v, type):
            raise ValueError("'{}'はクラスではありません: {}".format(name, v))
        return context.type_module.define(v)





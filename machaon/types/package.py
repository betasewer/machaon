import os

from machaon.core.importer import PyModuleInstance, module_loader, walk_modules
from machaon.package.package import Package, PackageManager


class AppPackageType:
    """ @type trait [Package]
    プログラムパッケージを操作するための型。
    ValueType: 
        machaon.package.package.Package
    """
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
        loadstatus = self.loading_status(package)
        installstatus = spirit.root.query_package_status(package, isinstall=True)

        if "notfound" == loadstatus:
            if "notfound" == installstatus:
                return "インストールされていない"
            else:
                return "インストールされたがモジュールが見つからない"
        if "delayed" == loadstatus:
            if "notfound" == installstatus:
                return "インストールされていない"
            else:
                return "読み込み待機中"
        if "failed" == loadstatus:
            if "notfound" == installstatus:
                return "インストールされていない"
            else:
                errors = []
                if package.is_load_failed():
                    errcnt = len(package.get_load_errors())
                    errors.append("{}件のエラー".format(errcnt))
                
                return "モジュールのロードに失敗 ({})".format("／".join(errors))
            
        if loadstatus.startswith("ready"):
            if "notfound" == installstatus:
                return "インストールされていないが利用可能"
            else:
                errors = []
                if package.is_load_failed():
                    errcnt = len(package.get_load_errors())
                    errors.append("{}件のエラー".format(errcnt))
                
                errexmodules = sum([1 for b in package.check_required_modules_ready().values() if not b])
                if errexmodules > 0:
                    errors.append("{}個の追加依存パッケージが不足".format(errexmodules))

                if not errors:
                    return "準備完了"
                else:
                    return "利用可能 ({})".format("／".join(errors))
        
        return "unexpected status：{}{}".format(loadstatus, installstatus)
    
    def loading_status(self, package: Package):
        """ @method
        モジュールのロード状態を示す文字列。
        Returns:
            Str:
        """
        loadstatus = "ready"
        if not package.is_ready():
            loadstatus = "notfound"
        elif not package.once_loaded():
            loadstatus = "delayed"
        elif package.is_load_failed():
            count = package.get_module_count()
            if count == 0:
                loadstatus = "failed"
            else:
                errcnt = len(package.get_load_errors())
                loadstatus = "ready ({} error)".format(errcnt)
        return loadstatus
    
    def update_status(self, package: Package, spirit):
        """ @task
        更新状態を示す文字列。
        リモートソースに接続して最新かどうか確認する。
        Returns:
            Str:
        """
        installstatus = spirit.root.query_package_status(package)
        if "none" == installstatus:
            return "ローカルに存在しません"
        elif "old" == installstatus:
            return "アップデートがあります"
        elif "latest" == installstatus:
            return "最新の状態です"
        
        return "unexpected status：{}".format(installstatus)

    def errors(self, package: Package):
        """ @method
        前回のロード時に発生したエラー
        Returns:
            Sheet[Error]: 
        """
        return package.get_load_errors()

    def scope(self, package: Package):
        """ @method
        型を展開するスコープ
        Returns:
            Str:
        """
        return package.scope
    
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
        h = context.root.pkgmanager.get_installed_hash(package)
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
        return app.root.package_manager().get_installed_location(package)
    
    def install(self, package: Package, context, app, *options):
        """ @task context
        パッケージをインストールし、ロードする。
        Params:
            *options(str):
        """
        self.display_update(package, context, app, forceinstall=True, options=options)
    
    def update(self, package: Package, context, app, *options):
        """ @task context
        パッケージを更新し、再ロードする。
        Params:
            *options(Str):
        """
        self.display_update(package, context, app, options=options)
        
    # 
    def display_download_and_install(self, app, package:Package, operation, options=None):
        for state in operation(package, options):
            # ダウンロード中
            if state == PackageManager.DOWNLOAD_START:
                url = package.get_source().get_download_url()
                app.post("message", "パッケージのダウンロードを開始 --> {}".format(url))
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
        
    def display_update(self, package: Package, context, app, forceinstall=False, options=None):
        if not package.is_remote_source():
            app.post("message", "リモートソースの指定がありません")
            return
        
        approot = app.get_root()

        app.post("message-em", "パッケージ'{}'の更新を開始".format(package.name))
        rep = package.get_source()
        if rep:
            app.post("message", "ソース = {}".format(rep.get_source()))
        
        # パッケージの状態を調べる
        operation = approot.package_manager().update
        status = approot.query_package_status(package)
        if status == "none":
            app.post("message", "新たにインストールします")
            operation = approot.package_manager().install
        elif status == "old":
            app.post("message", "より新しいバージョンが存在します")
        elif status == "latest":
            app.post("message", "最新の状態です")
            if not forceinstall:
                return
        elif status == "unknown":
            app.post("error", "不明：パッケージの状態の取得に失敗")
            return

        # ダウンロード・インストール処理
        self.display_download_and_install(app, package, operation, options)

        # 型をロードする
        approot.load_pkg(package)

        # 追加依存モジュールを表示する
        for name, ready in package.check_required_modules_ready().items():
            if not ready:
                app.post("warn", "モジュール'{}'がありません。手動で追加する必要があります".format(name))

        if operation is approot.package_manager().install:
            app.post("message-em", "パッケージ'{}'のインストールが完了".format(package.name))
        else:
            app.post("message-em", "パッケージ'{}'の更新が完了".format(package.name))
            
        return
    
    def uninstall(self, package, context, app):
        """ @task context
        パッケージをアンインストールする。
        """
        if package.is_module_source():
            app.post("message", "このモジュールはアンインストールできません")
            return

        approot = app.get_root()

        app.post("message-em", " ====== パッケージ'{}'のアンインストール ====== ".format(package.name))

        for state in approot.package_manager().uninstall(package):
            if state == PackageManager.UNINSTALLING:
                app.post("message", "ファイルを削除")
            elif state == PackageManager.PIP_UNINSTALLING:
                app.post("message", "pipを呼び出し")
            elif state == PackageManager.PIP_MSG:
                app.post("message", "  " + state.msg)

        if package.is_type_modules():
            app.post("message", "スコープ'{}'を取り除きます".format(package.scope))
            approot.unload_pkg(package)

        app.post("message", "削除完了")
    
    def load(self, package, context):
        """ @method context
        パッケージに定義された全ての型を読み込む。
        """
        context.root.load_pkg(package)

    def reload(self, package, context):
        """ @method context
        以前読み込んだ定義を破棄し、再度読み込みをおこなう。
        """
        context.root.unload_pkg(package)
        context.root.load_pkg(package, force=True)        
    
    def scan(self, package, app):
        """ @task
        パッケージに定義された型を収集しログを表示する。登録はしない。
        Returns:
            Sheet[ObjectCollection](typename, qualname, error):
        """
        elems = []
        for mod in package.load_module_loaders():
            for df in mod.scan_print_type_definitions(app):
                elems.append(df)
        return elems
    
    def extra_requires(self, package):
        """ @method [extra]
        このパッケージが追加で依存するモジュール名。
        Returns:
            Sheet[ObjectCollection](name, ready):
        """
        return [{"name":x, "ready":y} for x, y in package.check_required_modules_ready().items()]

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
            Sheet[ObjectCollection](typename, qualname, error):
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
        d = context.type_module.add_definition(v)
        return d.load_type() # 即座にロードする





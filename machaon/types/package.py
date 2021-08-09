from typing import Type
from machaon.package.package import PackageManager
from types import ModuleType

class AppPackageType:
    """
    プログラムパッケージを操作するための型。
    ValueType: 
        machaon.package.package.Package
    """
    def name(self, package):
        """ @method
        パッケージ名
        Returns:
            Str:
        """
        return package.name
    
    def status(self, package, spirit):
        """ @method spirit
        パッケージの状態を示す文字列
        Returns:
            Str:
        """
        loadstatus = self.loading_status(package)
        installstatus = spirit.root.query_package_status(package, isinstall=True)

        if "notfound" == loadstatus:
            if "notfound" == installstatus:
                return "未インストール"
            else:
                return "インストールされたモジュールが見つからない"
        if "delayed" == loadstatus:
            if "notfound" == installstatus:
                return "アンインストール済"
            else:
                return "読み込み待機中"
        if "failed" == loadstatus:
            if "notfound" == installstatus:
                return "アンインストール済"
            else:
                return "全モジュールのロードに失敗"
        if loadstatus.startswith("ready"):
            if "notfound" == installstatus:
                return "利用可能"
            else:
                errors = []
                if package.is_load_failed():
                    errcnt = len(package.get_load_errors())
                    errors.append("{}件のモジュールのロードエラー".format(errcnt))
                
                errexmodules = sum([1 for b in package.check_required_modules_ready().values() if not b])
                if errexmodules > 0:
                    errors.append("{}件の追加依存パッケージのロードエラー".format(errexmodules))

                if not errors:
                    return "準備完了"
                else:
                    return "利用可能 ({})".format("／".join(errors))
        
        return "unexpected status：{}{}".format(loadstatus, installstatus)
    
    def loading_status(self, package):
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
    
    def update_status(self, package, spirit):
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

    def errors(self, package):
        """ @method
        前回のロード時に発生したエラー
        Returns:
            Sheet[Error]: 
        """
        return package.get_load_errors()

    def scope(self, package):
        """ @method
        型を展開するスコープ
        Returns:
            Str:
        """
        return package.scope
    
    def source(self, package):
        """ @method
        ソースを示す文字列
        Returns:
            Str:
        """
        return package.get_source_signature()
    
    def entrypoint(self, package):
        """ @method
        エントリポイントとなるモジュール
        Returns:
            Str:
        """
        return package.entrypoint
    
    def hash(self, package, context):
        """ @method context
        インストールされているバージョンのハッシュ値
        Returns:
            Str:
        """
        h = context.root.pkgmanager.get_installed_hash(package)
        if not h:
            return "<no-hash>"
        return h

    def latest_hash(self, package, app):
        """ @task
        パッケージの最新のハッシュ値
        Returns:
            Str:
        """
        h = package.load_latest_hash()
        if not h:
            return "<no-hash>"
        return h
    
    def install(self, package, context, app):
        """ @task context
        パッケージをインストールし、ロードする。
        """
        self._update(package, context, app, forceinstall=True)
    
    def update(self, package, context, app):
        """ @task context
        パッケージを更新し、再ロードする。
        """
        self._update(package, context, app)

    # 
    def _update(self, package, context, app, forceinstall=False):
        if not package.is_remote_source():
            app.post("message", "リモートソースの指定がありません")
            return
        
        approot = app.get_root()

        app.post("message-em", "パッケージ'{}'の更新を開始".format(package.name))
        rep = package.get_source()
        if rep:
            app.post("message", "ソース = {}".format(rep.get_source()))
        
        operation = approot.update_package
        status = approot.query_package_status(package)
        if status == "none":
            app.post("message", "新たにインストールします")
            operation = approot.install_package
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
        for state in operation(package):
            # ダウンロード中
            if state == PackageManager.DOWNLOAD_START:
                app.post("message", "パッケージのダウンロードを開始 --> {}".format(rep.get_download_url()))
                app.start_progress_display(total=state.total)
            elif state == PackageManager.DOWNLOADING:
                app.interruption_point(progress=state.size)
            elif state == PackageManager.DOWNLOAD_END:
                app.finish_progress_display(total=state.total)
            elif state == PackageManager.DOWNLOAD_ERROR:
                app.post("error", "ダウンロードに失敗しました：\n  {}".format(state.error))
                return

            # インストール処理
            elif state == PackageManager.PIP_INSTALLING:
                app.post("message", "pipを呼び出し")
            elif state == PackageManager.PIP_MSG:
                app.post("message", "> " + state.msg)
            elif state == PackageManager.PIP_END:
                if state.returncode == 0:
                    app.post("message", "pipによるインストールが成功し、終了しました")
                elif state.returncode is None:
                    pass
                else:
                    app.post("error", "pipによるインストールが失敗しました コード={}".format(state.returncode))
                    return

            elif state == PackageManager.PRIVATE_REQUIREMENTS:
                app.post("warn", "次の依存パッケージを手動でインストールする必要があります：")
                for name in state.names:
                    app.message("  " + name)

        # 型をロードする
        approot.load_pkg(package)

        # 追加依存モジュールを表示する
        for name, ready in package.check_required_modules_ready().items():
            if not ready:
                app.post("warn", "モジュール'{}'がありません。後で追加する必要があります".format(name))

        if operation is approot.install_package:
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

        for state in approot.uninstall_package(package):
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
            Sheet[ObjectCollection]: (typename, qualname, error)
        """
        elems = []
        for mod in package.load_module_loaders():
            modqualname = str(mod)
            app.post("message", "モジュール {}".format(modqualname))

            defs = []
            err = None
            try:
                for typedef in mod.scan_type_definitions():
                    typename = typedef.typename
                    qualname = typedef.get_describer_qualname()
                    defs.append({
                        "typename" : typename,
                        "qualname" : qualname
                    })
            except Exception as e:
                err = e
            
            if defs:
                app.post("message", "　型定義を{}個発見".format(len(defs)))
            if err:
                app.post("error", "  ロードエラー:{}".format(err))
                defs.append({
                    "qualname" : modqualname,
                    "error" : err
                })
            
            elems.extend(defs)
        
        return elems
    
    def extra_requires(self, package):
        """ @method [extra]
        このパッケージが追加で依存するモジュール名。
        Returns:
            Sheet[ObjectCollection]: (name, ready)
        """
        return [{"name":x, "ready":y} for x, y in package.check_required_modules_ready().items()]


#
#
#
class Module():
    """
    Pythonのモジュール型。
    """
    def __init__(self, m) -> None:
        self._m = m

    def constructor(self, context, value):
        """ @meta """
        if isinstance(value, str):
            from machaon.core.importer import module_loader
            loader = module_loader(value)
            return Module(loader.load_module())
        elif isinstance(value, ModuleType):
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
        spec = self._m.__spec__
        if not spec.has_location:
            raise ValueError("ビルトインモジュールなので場所を参照できません")
        return spec.origin
    
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
    
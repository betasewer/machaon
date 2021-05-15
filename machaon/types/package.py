from machaon.package.package import PackageManager

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
        ロード状態を示す文字列
        Returns:
            Str:
        """
        loadstatus = "ready"
        if not package.is_ready():
            loadstatus = "none"
        elif not package.once_loaded():
            loadstatus = "delayed"
        elif package.is_load_failed():
            loadstatus = "failed"
        
        installstatus = spirit.root.query_package_status(package, isinstall=True)

        if "none" == loadstatus:
            if "none" == installstatus:
                return "未インストール"
            else:
                return "モジュールが見つからない"
        if "delayed" == loadstatus:
            if "none" == installstatus:
                return "アンインストール済"
            else:
                return "読み込み待機中"
        if "failed" == loadstatus:
            if "none" == installstatus:
                return "アンインストール済"
            else:
                return "読み込みエラー"
        if "ready" == loadstatus:
            if "none" == installstatus:
                return "アンインストール済"
            else:
                return "準備完了"
        
        return "unexpected status：{}{}".format(loadstatus, installstatus)
    
    def update_status(self, package, spirit):
        """ @task
        アップデート状態を示す文字列
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

    def load_errors(self, package):
        """ @method
        前回のロード時に発生したエラー
        Returns:
            Tuple:
        """
        return [str(x) for x in package.get_load_errors()]

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

        if operation is approot.install_package:
            app.post("message-em", "パッケージ'{}'のインストールが完了".format(package.name))
        else:
            app.post("message-em", "パッケージ'{}'の更新が完了".format(package.name))
            
        return
    
    def uninstall(self, package, context, app):
        """ @task context
        パッケージをアンインストールする。
        """
        approot = app.get_root()

        app.post("message-em", " ====== パッケージ'{}'のアンインストール ====== ".format(package.name))

        for state in approot.uninstall_package(package):
            if state == PackageManager.UNINSTALLING:
                app.post("message", "ファイルを削除")
            elif state == PackageManager.PIP_UNINSTALLING:
                app.post("message", "pipを呼び出し")
            elif state == PackageManager.PIP_MSG:
                app.post("message", "  " + state.msg)

        if package.is_modules():
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

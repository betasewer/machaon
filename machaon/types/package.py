from machaon.package.package import PackageManager

class AppPackageType:
    """ @type
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
    
    def status(self, package):
        """ @method
        ロード状態を示す文字列
        Returns:
            Str:
        """
        if not package.once_loaded():
            return "利用不可: 待機中"
        if package.is_load_failed():
            return "利用不可: エラー"
        else:
            return "準備完了"

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
        approot = app.get_app()

        app.post("message-em", " ====== パッケージ'{}'のインストール ====== ".format(package.name))
        rep = package.get_source()
        if rep:
            app.post("message", "  --> {}".format(rep.get_source()))
        
        operation = approot.update_package
        status = approot.get_package_status(package)
        if status == "none":
            app.post("message-em", "新たにインストールします")
            operation = approot.install_package
        elif status == "old":
            app.post("message-em", "より新しいバージョンが存在します")
        elif status == "latest":
            app.post("message", "最新の状態です")
            if not forceinstall:
                return
        elif status == "unknown":
            app.post("error", "状態不明：リモートリポジトリの読み込みに失敗")
            return

        # ダウンロード・インストール処理
        app.post("message", "パッケージの取得を開始")
        for state in operation(package):
            # ダウンロード中
            if state == PackageManager.DOWNLOAD_START:
                app.start_progress_display(total=state.total)
            elif state == PackageManager.DOWNLOADING:
                app.interruption_point(progress=state.size)
            elif state == PackageManager.DOWNLOAD_END:
                app.finish_progress_display(total=state.total)
            elif state == PackageManager.DOWNLOAD_ERROR:
                app.post("error", "ダウンロードでエラー発生：{}".format(state.error))
                app.post("error", "インストール失敗")
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
                app.post("warn", "次の依存パッケージを後で手動でインストールする必要があります：")
                for name in state.names:
                    app.message("  " + name)

        # 型をロードする
        package.unload(approot)

        if operation is approot.install_package:
            if package.is_modules():
                app.post("message-em", "モジュール'{}'のインストールが完了".format(package.scope))
            else:
                app.post("message-em", "パッケージ'{}'のインストールが完了".format(package.name))
        else:
            if package.is_modules():
                app.post("message-em", "モジュール'{}'の更新が完了".format(package.scope))
            else:
                app.post("message-em", "パッケージ'{}'の更新が完了".format(package.name))
            
        return
    
    def uninstall(self, package, context, app):
        """ @task context
        パッケージをアンインストールする。
        """
        approot = app.get_app()

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
            package.unload(approot)

        app.post("message", "削除完了")
    
    def load(self, package, context):
        """ @method context
        パッケージに定義された全ての型を読み込む。
        """
        package.load(context.root)


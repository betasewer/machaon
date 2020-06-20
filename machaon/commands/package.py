from machaon.package.package import package_manager
from machaon.engine import NotAvailableCommandSet

#
#
#
def package_install(app, package_index, forceupdate=False):
    approot = app.get_app()

    # 現在のパッケージ、コマンドセットを取得
    package, oldcmdset = approot.get_package_and_commandset(package_index)
    if package is None:
        return

    newinstall = isinstance(oldcmdset, NotAvailableCommandSet)
    
    app.message_em("パッケージ'{}'".format(package.name))
    rep = package.get_repository()
    if rep:
        app.message("  ソース：{}".format(rep.get_repository_url()))
    
    if newinstall:
        app.message_em("インストールします")
    else:
        status = approot.get_package_status(package)
        if status == "none":
            app.message_em("インストールします")
            newinstall = True
        elif status == "old":
            app.message("より新しいバージョンが存在します")
        elif status == "latest":
            app.message("最新の状態です")
            if not forceupdate:
                return

    # ダウンロード・インストール処理
    app.message("パッケージの取得を開始")
    for state in approot.operate_package(package, install=newinstall, update=not newinstall):
        # 中断
        if state == package_manager.ALREADY_INSTALLED:
            app.warn("インストールされた記録がありますが、ファイルを上書きします")
        
        # ダウンロード中
        elif state == package_manager.DOWNLOAD_START:
            app.start_progress_display(total=state.total)
        elif state == package_manager.DOWNLOADING:
            app.interruption_point(progress=state.size)
        elif state == package_manager.DOWNLOAD_END:
            app.finish_progress_display(total=state.total)

        # インストール処理
        elif state == package_manager.PIP_INSTALLING:
            app.message("pipを呼び出し")
        elif state == package_manager.PIP_MSG:
            app.message("> " + state.msg)
        elif state == package_manager.PIP_END:
            if state.returncode == 0:
                app.message("pipによるインストールが成功し、終了しました")
            elif state.returncode is None:
                pass
            else:
                app.error("pipによるインストールが失敗しました コード={}".format(state.returncode))
                return

        elif state == package_manager.PRIVATE_REQUIREMENTS:
            app.warn("後ほど、依存する非公開パッケージを手動でインストールする必要があります：")
            for name in state.names:
                app.message(name)

    # コマンドエンジンの更新
    newcmdset = approot.build_commandset(package_index, package)
    if newinstall:
        app.message_em("コマンドセット'{}'のインストールが完了".format(newcmdset.name))
    else:
        if oldcmdset.name != newcmdset.name:
            app.message_em("コマンドセット'{}' --> '{}'の更新が完了".format(oldcmdset.name, newcmdset.name))
        else:
            app.message_em("コマンドセット'{}'の更新が完了".format(newcmdset.name))

#
#
#
def package_uninstall(app, package_index):
    approot = app.get_app()
    
    package, cmdset = approot.get_package_and_commandset(package_index)
    if package is None:
        return
        
    app.message_em("パッケージをアンインストールします")
    app.message("コマンドセット'{}'は削除されます".format(cmdset.name))

    for state in approot.operate_package(package, uninstall=True):
        if state == package_manager.NOT_INSTALLED:
            app.warn("インストールされた記録がありませんが、ファイルを削除します")

        elif state == package_manager.UNINSTALLING:
            app.message("ファイルを削除")
        elif state == package_manager.PIP_UNINSTALLING:
            app.message("pipを呼び出し")
        elif state == package_manager.PIP_MSG:
            app.message("> " + state.msg)

    app.message("コマンドエンジンから取り除きます")
    approot.disable_commandset(package_index, package)
    app.message("削除完了")

#
#
#
def command_package(spi, action, forceupdate=False, index=None):
    approot = spi.get_app()

    action = action.lower()
    if action == "update":
        if index is None:
            _ = [package_install(spi, i, forceupdate) for i in range(approot.count_package())]
        else:
            package_install(spi, index, forceupdate)
    elif action == "remove":
        if index is None:
            _ = [package_uninstall(spi, i) for i in range(approot.count_package())]
        else:
            package_uninstall(spi, index)
    else:
        spi.error("不明なアクションです")

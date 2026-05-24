from typing import cast

import argparse
import fnmatch
import re
import time
import datetime

from ..core.milestones import milestone
from ..types.shell import Path
from ..package.package import PackageManager, Package
from ..package.auth import CredentialDir

def _extract_version_from_dist_dir(dist_dir: Path) -> list[str]:
    """ ビルド局の *.tar.gz ファイル名からバージョンを判別する """
    if not dist_dir.isdir():
        return []
    versions = []
    for f in dist_dir.listdirfile():
        m = re.search(r"-(\d[\w.]*)\.tar\.gz$", f.name())
        if m:
            versions.append(m.group(1))
    return versions


def _format_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    elif size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size:,} bytes"


def _handle_pm_event(dsh: 'Dashboard', event):
    """ PackageManagerが返すmilestone_messageを整形して出力する """
    if milestone.match_type(event, PackageManager.DOWNLOAD_START):
        url = event.url
        total = event.total
        size_info = f"({_format_size(total)})" if total else ""
        dsh.put(f"  ダウンロード開始: {url} {size_info}")
    elif milestone.match_type(event, PackageManager.DOWNLOADING):
        dsh.put(f"  ダウンロード中... {_format_size(event.size)}", end="\r")
    elif milestone.match_type(event, PackageManager.DOWNLOAD_END):
        total = event.total
        if total is None:
            dsh.put(f"  ダウンロード完了")
        else:
            dsh.put(f"  ダウンロード完了: {_format_size(total)}")
    elif milestone.match_type(event, PackageManager.DOWNLOAD_ERROR):
        dsh.put(f"  エラー: {event.error}")
    elif milestone.match_type(event, PackageManager.EXEC_START):
        dsh.put(f"  実行: [{event.name}] {event.command}")
    elif milestone.match_type(event, PackageManager.EXEC_END):
        rc = event.returncode
        status = "成功" if rc == 0 else f"失敗 ({rc})"
        dsh.put(f"  終了: [{event.name}] {status}")
    elif milestone.match_type(event, PackageManager.MESSAGE):
        dsh.put(f"  {event.msg}")


class Action:
    def __init__(self, command_name: str, description: str):
        self.command_name = command_name
        # 引数パーサーを初期化する
        self.parser = argparse.ArgumentParser(
            prog=command_name,
            description=description,
            add_help=False
        )
    
    def get_description(self) -> str:
        """ コマンドの説明を取得する """
        return self.parser.description or ""
    
    def add_arg_package_pattern(self):
        self.parser.add_argument("patterns", nargs="*", help="パッケージ名のパターン")

    def execute(self, dsh: 'Dashboard', pm: PackageManager, args):
        """ ダッシュボードのアクションを実行する """
        raise NotImplementedError()
    
    def parse_args(self, args: str):
        try:
            return self.parser.parse_args(args.split())
        except SystemExit:
            return None
        
    def select_packages(self, dsh: 'Dashboard', pm: PackageManager, patterns: list[str]) -> list[Package]:
        """ パターンリストに一致するパッケージを選択する """
        if not patterns:
            return list(pm.getall())
        result = []
        seen: set[str] = set()
        for pattern in patterns:
            matched = [pkg for pkg in pm.getall() if fnmatch.fnmatch(pkg.name, pattern)]
            if not matched and len(patterns) > 1:
                dsh.put(f"パターン '{pattern}' に一致するパッケージはありません。")
            for pkg in matched:
                if pkg.name not in seen:
                    seen.add(pkg.name)
                    result.append(pkg)
        if not result:
            raise ValueError("一致するパッケージがありませんでした。")
        return result


class FetchPackageAction(Action):
    """ パッケージを取得するアクション """
    def __init__(self, name) -> None:
        super().__init__(name, "パッケージを取得します")
        self.add_arg_package_pattern()
        self.parser.add_argument("--latest", "-l", 
                                 action="store_true", 
                                 help="ターゲットコミットではなく最新のコミットを取得する")

    def execute(self, dsh: 'Dashboard', pm: PackageManager, args):
        """ パッケージをダウンロードする """
        if not args.patterns:
            if not dsh.confirm("全パッケージを取得します。よろしいですか？"):
                return
        pkgs = self.select_packages(dsh, pm, args.patterns)
        for pkg in pkgs:
            dsh.put(f"パッケージ '{pkg.name}' を取得します...")
            for event in pm.fetch(pkg, latest=args.latest):
                _handle_pm_event(dsh, event)
                if milestone.match_type(event, PackageManager.FINISHED):
                    dsh.put(f"取得完了: '{pkg.name}'")


class BuildPackageAction(Action):
    """ パッケージをビルドするアクション """
    def __init__(self, name) -> None:
        super().__init__(name, "パッケージをビルドします")
        self.add_arg_package_pattern()

    def execute(self, dsh: 'Dashboard', pm: PackageManager, args):
        """ パッケージをビルドする """
        if not args.patterns:
            if not dsh.confirm("全パッケージをビルドします。よろしいですか？"):
                return
        pkgs = self.select_packages(dsh, pm, args.patterns)
        for pkg in pkgs:
            dsh.put(f"パッケージ '{pkg.name}' をビルドします...")
            for event in pm.build(pkg):
                _handle_pm_event(dsh, event)
                if milestone.match_type(event, PackageManager.FINISHED):
                    if event.name == "fetch":
                        dsh.put(f"  取得完了: '{pkg.name}'")
                    elif event.name == "build":
                        dsh.put(f"ビルド完了: '{pkg.name}'")


def _package_type_label(pkg) -> str:
    from ..package.package import (
        PACKAGE_TYPE_IMPORT, PACKAGE_TYPE_DIST,
        PACKAGE_TYPE_MODULES, PACKAGE_TYPE_RESOURCE, PACKAGE_TYPE_UNDEFINED
    )
    return {
        PACKAGE_TYPE_IMPORT:   "ソースパッケージ",
        PACKAGE_TYPE_DIST:     "配布パッケージ",
        PACKAGE_TYPE_MODULES:  "単体モジュール",
        PACKAGE_TYPE_RESOURCE: "リソースファイル",
        PACKAGE_TYPE_UNDEFINED:"（不明）",
    }.get(pkg._type, str(pkg._type))


class StatusPackageAction(Action):
    """ パッケージの定義と状態を詳細表示するアクション """
    def __init__(self, name) -> None:
        super().__init__(name, "パッケージの状態を表示します")
        self.add_arg_package_pattern()

    def execute(self, dsh: 'Dashboard', pm: PackageManager, args):
        """ パッケージの定義と状態を表示する """
        packages = self.select_packages(dsh, pm, args.patterns)
        for pkg in packages:
            dsh.put(f"{'='*50}")
            dsh.put(f"[{pkg.name}]")

            # --- .packages 定義情報 ---
            dsh.put(f"  定義リスト    : {pkg.listname or '(不明)'}")
            
            private = "[非公開]" if pkg.is_private_source() else ""
            dsh.put(f"  ソース        : {pkg.source_signature} {private}")

            dsh.put(f"  タイプ        : {_package_type_label(pkg)}")
            target = pkg.get_target_commit()
            target_str = target[:7] if target else "HEAD"
            dsh.put(f"  ターゲット    : {target_str}")

            # --- フェッチ状態 ---
            if pkg.is_fetched():
                timestamp = cast(datetime.datetime|None, pkg._fetch_state.get("timestamp"))
                ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp is not None else "(時刻不明)"
                commit = pkg.get_fetched_commit()
                short_commit = commit[:7] if commit else "(コミット不明)"
                dirname = pkg._fetch_state.get("dirname") or "不明"
                dsh.put(f"  取得          : {short_commit}  {ts_str}  ({dirname})")
            else:
                dsh.put(f"  取得          : 未")

            # --- ビルド状態 ---
            if not pkg.is_modules():
                dsh.put(f"  ビルド        : 不要")
            elif pkg.is_dist_built():
                timestamp = cast(datetime.datetime|None, pkg._dist_state.get("timestamp"))
                ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S") if timestamp is not None else "(時刻不明)"
                commit = cast(str|None, pkg._dist_state.get("commit"))
                short_commit = commit[:7] if commit else "(コミット不明)"
                needs = pkg.needs_build()
                rebuild = "  ※再ビルド必要" if needs else ""
                
                dist_dir = pkg.get_dist_location(pm)
                dist_dir_name = dist_dir.name() if dist_dir else "(不明)"
                dsh.put(f"  ビルド        : {short_commit}  {ts_str}{rebuild}  ({dist_dir_name})")

                versions = []
                if dist_dir:
                    versions = _extract_version_from_dist_dir(dist_dir)
                if versions:
                    dsh.put(f"  バージョン    : {', '.join(versions)}")
                else:
                    dsh.put(f"  バージョン    : なし")
            else:
                dsh.put(f"  ビルド        : 未")

        dsh.put(f"{'='*50}")


class ListPackagesAction(Action):
    """ パッケージ一覧を表示するアクション """
    def __init__(self, name) -> None:
        super().__init__(name, "パッケージ一覧を表示します")
        self.add_arg_package_pattern()

    def execute(self, dsh: 'Dashboard', pm: PackageManager, args):
        """ パッケージの一覧を表示する """
        packages = self.select_packages(dsh, pm, args.patterns)
        dsh.put(f"{len(packages)} 件のパッケージ:")
        for pkg in packages:
            dsh.put(f"  {pkg.name}")


class UploadAction(Action):
    """ インデックスサーバにアップロードする  """
    def __init__(self, command_name: str):
        super().__init__(command_name, "インデックスサーバにビルド済パッケージをアップロードします")
        self.parser.add_argument("url")
        self.parser.add_argument("--username", "-u", help="ユーザ名")
        self.parser.add_argument("--password", "-p", help="パスワード")
    
    def execute(self, dsh: 'Dashboard', pm: PackageManager, args):
        url = args.url
        user = args.username
        pssw = args.password
        for event in pm.upload(url, user, pssw):
            _handle_pm_event(dsh, event)                
            if milestone.match_type(event, PackageManager.FINISHED):
                dsh.put(f"アップロード完了: '{url}'")


class HelpAction(Action):
    """ コマンドのヘルプを表示するアクション """
    def __init__(self, name) -> None:
        super().__init__(name, "コマンドのヘルプを表示します")
        self.parser.add_argument("command", nargs="?", default=None, help="コマンド名（省略時は一覧表示）")

    def execute(self, dsh: 'Dashboard', pm: PackageManager, args):
        """ コマンドのヘルプを表示する """
        import io
        actions = dsh.actions()
        if args.command is None:
            dsh.put("コマンド:")
            for name, action in actions.items():
                desc = action.get_description()
                dsh.put(f"  {name:<10} {desc}")
        else:
            action = actions.get(args.command)
            if action is None:
                dsh.put(f"'{args.command}' は不明なコマンドです。")
                return
            buf = io.StringIO()
            action.parser.print_help(file=buf)
            dsh.put(buf.getvalue())


#
#
#
class Dashboard:
    def __init__(self, pkg_manager: PackageManager):
        self.pm = pkg_manager
        actions = (
            BuildPackageAction("build"),
            FetchPackageAction("fetch"),
            ListPackagesAction("list"),
            StatusPackageAction("status"),
            UploadAction("upload"),
            HelpAction("help"),
        )
        self._chart = {action.command_name: action for action in actions}

    def actions(self):
        """ コマンドチャートを取得する """
        return self._chart

    @classmethod
    def start(cls, basic_dir: 'Path'):
        """ ダッシュボードを初期化する """
        creds = CredentialDir(basic_dir)
        pm = PackageManager(basic_dir, creds)
        pm.init()
        pm.load_packages(basic_dir)
        return cls(pm)

    def put(self, s, end="\n"):
        """ ダッシュボードに文字列を出力する """
        print(s, end=end, flush=True)

    def confirm(self, message: str) -> bool:
        """ 確認プロンプトを表示し、y/n で応答を求める """
        self.put(f"{message} [yes/no]: ", end="")
        answer = input().strip().lower()
        return answer in ("y", "yes")

    def mainloop(self, *, initial=None):
        """ ダッシュボードのメインループ """
        while True:
            if initial is not None:
                command = initial
                initial = None
            else:
                command = input(">> ")
            command = command.lower().strip()
            verb, sep, argseq = command.partition(" ")

            if command == "":
                self.put("コマンドを入力してください。help: ヘルプを表示します。exit: ダッシュボードを終了します。")
                continue

            if verb == 'exit':
                self.put("さようなら！")
                break
            
            action = self._chart.get(verb, None)
            if action is None:
                self.put(f"{verb}：不明なコマンドです。")
                continue
            
            args = action.parse_args(argseq)
            if args is None:
                continue
            try:
                action.execute(self, self.pm, args)
            except ValueError as e:
                self.put(f"エラー: {e}")

            # 1秒ごとに更新する
            time.sleep(0.2)


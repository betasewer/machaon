import os
import shutil
import sys
import datetime
import configparser
import re
import importlib
from typing import Dict, Any, Sized, Union, List, Optional, Iterator, cast, Literal, Iterable

from machaon.core.importer import module_loader
from machaon.core.error import ErrorSet
from machaon.core.milestones import milestone
from machaon.types.shell import Path
from machaon.types.file import TextFile
from machaon.types.config import ConfigClass, ConfigSection, Config
from machaon.package.repository import RepositoryArchive, RepositoryURLError, REPO_DELIM_HOST
from machaon.package.archive import BasicArchive, LocalFile
from machaon.package.auth import CredentialDir


PACKAGE_TYPE_IMPORT     = 0x1 # ビルドされるパッケージ
PACKAGE_TYPE_DIST       = 0x2 # ビルド済み配布パッケージ
PACKAGE_TYPE_RESOURCE   = 0x3 # その他のファイル
PACKAGE_TYPE_MODULES    = 0x4 # ビルド不要なモジュール
PACKAGE_TYPE_UNDEFINED  = 0xFF

FETCH_TARGET_COMMIT_SPECIFIED  = 1 # パッケージで指定されたコミットを取得する 
FETCH_TARGET_COMMIT_LATEST     = 2 # リポジトリで最新のコミットを取得する

class PACKAGE_LOAD_END:
    pass

#
# エラー
#
class PackageNotFoundError(Exception):
    def __str__(self):
        name = self.args[0]
        msg = "パッケージ'{}'は存在しません".format(name)
        if ":" not in name:
            msg += ": リスト名を後に続けた完全な名前で指定してください"
        return msg

class PackageStateDatabaseNotLoadedError(Exception):
    pass



#
#
#
class Package:
    IMPORT_PACKAGE = PACKAGE_TYPE_IMPORT
    DIST_PACKAGE = PACKAGE_TYPE_DIST
    MODULES = PACKAGE_TYPE_MODULES
    RESOURCE = PACKAGE_TYPE_RESOURCE
    UNDEFINED = PACKAGE_TYPE_UNDEFINED

    def __init__(self, 
        name: str, 
        source: Any, 
        type: int,
        target_commit: str|None,
        listname: str|None,
        fetch_state: ConfigSection,
        dist_state: ConfigSection
    ):
        self.name: str = name                         # machaon上での識別名
        self.source: BasicArchive = source            # パッケージの取得源を表すオブジェクト
        self.listname: str|None = listname            # パッケージ定義リストの識別名
        self._type = type                             # パッケージの種類
        self._target_commit = target_commit           # 定義で指定のコミットハッシュ
        self._fetch_state = fetch_state               # ダウンロード状態にアクセスするセクションオブジェクト
        self._dist_state = dist_state                 # 配布物のビルド状態にアクセスするセクションオブジェクト

    @property
    def source_name(self):
        return self.source.get_name() 

    @property
    def source_signature(self):
        return self.source.get_source()
    
    def is_private_source(self) -> bool:
        if isinstance(self.source, RepositoryArchive):
            return self.source.cred is not None
        return False
    
    def get_source(self) -> BasicArchive:
        return self.source
    
    def is_remote_source(self) -> bool:
        return isinstance(self.source, RepositoryArchive)

    def get_target_commit(self):
        """ 定義で指定されたコミットハッシュを取り出す """
        return self._target_commit

    def is_fetched(self) -> bool:
        """ ローカルにダウンロードされているか """
        if not self.is_remote_source():
            return True
        return self._fetch_state.get("timestamp") is not None
    
    def is_dist_built(self) -> bool:
        """ 配布物がビルドされているか """
        if not self.is_modules():
            return False
        return self._dist_state.get("timestamp") is not None
    
    def load_latest_commit(self, *, fallback=True) -> Optional[str]:
        """ リポジトリに最新のコミットハッシュを問い合わせる """
        if not isinstance(self.source, RepositoryArchive):
            raise ValueError("source is not a RepositoryArchive")
        try:
            commit = self.source.query_latest_commit()
        except RepositoryURLError:
            if not fallback:
                raise 
            return None 
        return commit

    def is_modules(self) -> bool:
        """ モジュールパッケージか """
        return self._type == PACKAGE_TYPE_MODULES or self._type == PACKAGE_TYPE_IMPORT or self._type == PACKAGE_TYPE_DIST

    def is_resource(self) -> bool:
        """ モジュールではないファイルの集合体 """
        return self._type == PACKAGE_TYPE_RESOURCE
    
    def is_undefined(self) -> bool:
        """ 未定義のパッケージか """
        return self._type == PACKAGE_TYPE_UNDEFINED

    #
    # パッケージの状態を調べる
    #
    def get_fetched_location(self, pm: 'PackageManager') -> Optional[Path]:
        """ パッケージがダウンロードされたパス """
        if not self.is_fetched():
            return None
         # データベースから展開先のディレクトリ名を取り出す
        dirname = self._fetch_state.get("dirname")
        if dirname is None:
            return None
        return pm.repositories_dir / cast(str, dirname)
    
    def get_fetched_commit(self) -> Optional[str]:
        """ ダウンロードされたコミットハッシュ """
        if not self.is_fetched():
            return None
        commit = self._fetch_state.get("commit")
        if commit is None:
            return None
        return cast(str, commit)

    def get_dist_location(self, pm: 'PackageManager') -> Optional[Path]:
        """ パッケージがビルドされた配布物のパス """
        if not self.is_dist_built():
            return None
         # データベースから展開先のディレクトリ名を取り出す
        dirname = self._dist_state.get("dirname")
        if dirname is None:
            return None
        return pm.dist_dir / cast(str, dirname)
    
    def needs_build(self) -> Optional[bool]:
        """ 配布物とダウンロードされたものを比較して、ビルドの必要があるか調べる """
        if not self.is_fetched():
            return False
        if not self.is_dist_built():
            return True
        # コミットハッシュを比較する
        fetched_commit = cast(str|None, self._fetch_state.get("commit"))
        dist_commit = cast(str|None, self._dist_state.get("commit"))
        if fetched_commit is not None and dist_commit is not None:
            return fetched_commit != dist_commit
        elif fetched_commit is None and dist_commit is None:
            return True
        elif fetched_commit is not None and dist_commit is None:
            return True
        else:
            return False
        
    #
    # 高レベルな操作
    #
    def extraction(self, fetch_target_type: int, *, creds:'CredentialDir|None'=None):
        """ パッケージ展開オブジェクトを作成する """
        rep = self.get_source()
        if isinstance(rep, RepositoryArchive):
            if fetch_target_type == FETCH_TARGET_COMMIT_LATEST:
                target_commit = self.get_target_commit()
            elif fetch_target_type == FETCH_TARGET_COMMIT_SPECIFIED:
                target_commit = None
            else:
                raise ValueError("Invalid commit type: " + str(fetch_target_type))
        
            return RemotePackageExtraction(rep, target_commit)
        elif isinstance(rep, BasicArchive):
            return ArchivePackageExtraction(rep)
        else:
            return LocalPackageExtraction(rep)

    def query_update_status(self, *, fallback=True) -> str:
        """ 最新のコミットがダウンロードされているか、通信して問い合わせる """
        if not self.is_remote_source():
            return "latest"
        # hashを比較して変更を検知する
        installed_commit = self.get_fetched_commit()
        if installed_commit is None:
            return "notfound"
        latest_commit = self.load_latest_commit(fallback=fallback) # リモートリポジトリに最新のコミットハッシュを問い合わせる
        if latest_commit is None:
            return "unknown"
        if installed_commit == latest_commit:
            return "latest"
        else:
            return "old"


#
# パッケージ定義ファイル
#
PackageDefsConfig = ConfigClass("package-defs", {
    "package.*": {
        "repository": str,   # ホスト名/リポジトリ名:ブランチ名
        "path?": str,        # (optional) リポジトリ内のサブディレクトリを示すパス
        "resource?": bool,   # (optional) リソースパッケージか
        "nobuild?": bool,    # (optional) ビルド不要なモジュールか
    },
    "host.*": {
        "site": str,         # サイト名 [github|bitbucket]
        "username": str,     # ユーザ名
        "auth?": str,        # (optional) 認証タイプ [ホストによって異なる。空文字列でなければ認証ありとみなす]
        "key?": str,         # (optional) 認証キー
        "authuser?": str     # (optional) 認証ユーザ名 (authuserキーがない場合はusernameが使われる)
    }
})

class PackagingLineFromConfig:
    """
    パッケージ定義ファイルからパッケージオブジェクトを作り出す
    """
    def __init__(self, listname: str, creds: CredentialDir):
        self._hosts: dict[str, ConfigSection] = {}
        self._listname = listname
        self._creds = creds

    def add_host(self, name, config: ConfigSection):
        self._hosts[name] = config
        
        # 認証情報を追加する
        auth = config.get("auth")
        if auth:
            keys = { 
                "key": config.get("key"),
                "authuser": config.get("authuser")
            }
            self._creds.add_authentication(name, config["username"], auth, keys)
    
    def create_package(self, name, config: ConfigSection, fetch_state: ConfigSection, dist_state: ConfigSection):
        repo = cast(str, config["repository"])
        host, sep, repo = repo.partition(REPO_DELIM_HOST)
        if not sep:
            raise ValueError("repository: '{}' ホスト名とリポジトリ名を'{}'で区切って指定してください".format(repo, REPO_DELIM_HOST))
        if host not in self._hosts:
            raise ValueError("repository: '{}' ホスト'{}'は定義されていません".format(repo, host))
        hostcfg = self._hosts[host]

        # パッケージの種別を決定する
        pkgtype = PACKAGE_TYPE_IMPORT
        if config["resource"]:
            pkgtype = PACKAGE_TYPE_RESOURCE
        elif config["nobuild"]:
            pkgtype = PACKAGE_TYPE_MODULES
        elif repo.endswith(".whl"):
            pkgtype = PACKAGE_TYPE_DIST # 未実装

        # コミットハッシュの指定
        repo, sep, commit = repo.partition("+")
        if not sep:
            commit = None
    
        # 認証
        cred = self._creds.search(host)
        if cred and config.get("key"):
            cred = cred.rebind_repository(repo, {"key": config.get("key")})

        # ホストに応じたソースオブジェクトを作成する
        if hostcfg["site"] == "github" or hostcfg["site"] == "github.com":
            from machaon.package.repository import GithubRepArchive
            reposource = GithubRepArchive(repo, username=hostcfg["username"], subpath=config["path"], cred=cred)
        elif hostcfg["site"] == "bitbucket" or hostcfg["site"] == "bitbucket.org":
            from machaon.package.repository import BitbucketRepArchive
            reposource = BitbucketRepArchive(repo, username=hostcfg["username"], subpath=config["path"], cred=cred)
        else:
            raise ValueError("repository: '{}' ホスト'{}'はサポートされていません".format(repo, hostcfg["site"]))

        pkg = Package(name, reposource, type=pkgtype, target_commit=commit, 
                    listname=self._listname, fetch_state=fetch_state, dist_state=dist_state)
        return pkg

    @classmethod
    def package_source(cls, pkg: Package):
        """ パッケージのソースを表す文字列を生成する """
        if isinstance(pkg.source, RepositoryArchive):
            return pkg.source.get_source()
        else:
            return pkg.source.get_name()

#
#
#
PackageStateDatabaseCfg = ConfigClass("package-state-database", {
    "fetch.*": {
        "package": str,     # パッケージ定義の名前
        "commit": str,      # コミット
        "timestamp": datetime.datetime,   # 実行日時
        "dirname": str
    },
    "dist.*": {
        "package": str,     # パッケージ定義の名前
        "commit": str,      # コミット
        "timestamp": datetime.datetime,   # 実行日時
        "dirname": str
    }
})

class PackageStateDatabase:
    def __init__(self):
        self._db = None
        self._path = None

    def must_be_opened(self):
        if self._db is None:
            raise PackageStateDatabaseNotLoadedError()
        return self._db

    def load(self, path: Path, *, force=False):
        if not force and self._db is not None:
            return
        if path.isfile():
            # ファイルを読み込む
            self._db = PackageStateDatabaseCfg.load_file(path)
        else:
            # 空データ
            self._db = PackageStateDatabaseCfg.new()
        self._path = path
        return True
    
    def _add_state(self, db: Config, state: str, pkg: Package, commit: str|None):
        sectname = "{}.{}".format(state, pkg.name)
        db.set_value(sectname + "/package", pkg.name)
        db.set_value(sectname + "/commit", commit or "")
        db.set_value(sectname + "/timestamp", datetime.datetime.now())
        return sectname

    def update_on_fetch(self, pkg: Package, dirname: str, commit: str|None):
        # ダウンロード完了を記帳する
        db = self.must_be_opened()
        sect = self._add_state(db, "fetch", pkg, commit)
        db.set_value(sect + "/dirname", dirname)
        self.save()

    def update_on_dist(self, pkg: Package, dirname: str):
        # 配布物のビルド完了を記帳する
        db = self.must_be_opened()
        sect = self._add_state(db, "dist", pkg, pkg.get_fetched_commit())
        db.set_value(sect + "/dirname", dirname)
        self.save()
    
    def remove(self, package_name: str):
        # あるパッケージの全工程の記録を削除する
        db = self.must_be_opened()
        sectnames = [
            "fetch.{}".format(package_name),
            "dist.{}".format(package_name)
        ]
        for sectname in sectnames:
            db.remove(sectname)
        self.save()

    def state(self, package_name: str, state_name: Literal["fetch", "dist"]) -> ConfigSection:
        # パッケージの状態を確認できるオブジェクトを返す
        db = self.must_be_opened()
        sectname = "{}.{}".format(state_name, package_name)
        return db.section(sectname)

    def save(self):
        db = self.must_be_opened()
        if self._path is None:
            raise ValueError("No path to save")
        db.write_file(self._path)


#
# パッケージの定義と状態を一元的に管理する
#
class PackageManager:
    def __init__(self, directory: Path, credentials: CredentialDir|None = None):
        # ディレクトリを作成する
        self._dir = Path(directory).normalize()
        self.repositories_dir.makedirs()
        self.dist_dir.makedirs()
        # パッケージ
        self.packages: list[Package] = []
        self._creds: CredentialDir = credentials or CredentialDir(self._dir / "credentials") # 認証情報
        # 更新データベース
        self.state_db = PackageStateDatabase()

    @property
    def repositories_dir(self): # リポジトリの展開先の場所
        return self._dir / "repositories"
    
    @property
    def dist_dir(self): # 配布物の場所
        return self._dir / "dist"
    
    def init(self, *, force=False):
        """ 初期化処理を行う """
        # データベースをロードする
        errset = ErrorSet("パッケージマネージャの初期化")

        dbpath = self._dir / "packages.ini"
        try:
            self.state_db.load(dbpath, force=force)
        except Exception as e:
            errset.add(e)
        
        errset.throw_if_failed()

        # machaonパッケージを追加する
        _machaon_pkg = _machaon_package(self.state_db.must_be_opened())
        self.packages.append(_machaon_pkg)
    
    #
    # リポジトリ定義の読み込み
    #
    def load_packages(self, pkglistdir:Path):
        """ リポジトリリストからパッケージ定義を読み込む """
        errset = ErrorSet("パッケージディレクトリ'{}'の読み込み".format(pkglistdir))

        if not pkglistdir.isdir():
            errset.add(FileNotFoundError(pkglistdir))
            return # パスが見つからず
        
        # リストファイルのディレクトリを読み込む
        for f in pkglistdir.listdirfile():
            if f.name().startswith(".") or not f.hasext(".packages"):
                continue
            try:
                self.load_packages_from_file(f)
            except Exception as e:
                errset.add(e)
        errset.throw_if_failed()

    def load_packages_from_file(self, configfile: Path):
        """ パッケージ定義ファイルからパッケージをロードする """
        errset = ErrorSet("パッケージ定義'{}'の読み込み".format(configfile))
        
        # リストファイルを読み込む
        repolist = None
        try:
            repolist = PackageDefsConfig.load_file(configfile)
        except Exception as e:
            errset.add(e)

        if repolist is not None:
            listname = configfile.basename()
            packaging = PackagingLineFromConfig(listname, self._creds)
            for host in repolist.sections(category="host"):        
                packaging.add_host(host.name, host)
            
            for pkgsect in repolist.sections(category="package"):
                pkgname = pkgsect.name
                # 重複はスキップ
                pkgexists = any(p.name == pkgname for p in self.packages)
                if pkgexists:
                    continue
                try:
                    fetch_state = self.state_db.state(pkgname, "fetch")
                    dist_state = self.state_db.state(pkgname, "dist")
                    pkg = packaging.create_package(pkgname, pkgsect, fetch_state, dist_state)
                    self.packages.append(pkg)
                except Exception as e:
                    errset.add(e, message="セクション'{}'".format(pkgsect.key))

        errset.throw_if_failed()

    def get(self, name: str, *, fallback=True) -> Optional[Package]:
        """ パッケージを完全な名前で取得する """
        for pkg in self.packages:
            if pkg.name == name:
                return pkg
        if not fallback:
            raise PackageNotFoundError(name)
        return None
    
    def getall(self) -> Iterator[Package]:
        """ 全てのパッケージ """
        for pkg in self.packages:
            yield pkg

    def add(self, pkg: Package):
        """ 後から追加する """
        self.packages.append(pkg)


    #
    # パッケージをローカルに導入する
    #
    def fetch_package(self, pkg: Package, fetch_target_type: int):
        """ パッケージをローカルにダウンロードする """
        with pkg.extraction(fetch_target_type, creds=self._creds) as extractor:
            fetched_commit: str|None = None
            localpath = None
            for status in extractor:
                if milestone.match_type(status, PackageManager.EXTRACTED_COMMIT):
                    # コミットのハッシュが得られた
                    fetched_commit = cast(str, status.commit)
                
                elif milestone.match_type(status, PackageManager.EXTRACTED_FILES):
                    # 展開が完了した
                    localpath = status.path
                    
                else:
                    yield status
                    continue

            # 展開が完了
            if localpath is None:
                return
            
            # フォルダにコピーする
            foldername = os.path.basename(localpath)
            destdir: Path = self.repositories_dir / foldername
            destdir.rmtree() # 既に同名のフォルダがあれば削除する
            shutil.copytree(localpath, destdir)

            # データベースに記帳する -> パッケージオブジェクトでも更新された状態が取得できる
            self.state_db.update_on_fetch(pkg, destdir.name(), fetched_commit)
            yield PackageManager.FINISHED(name="fetch", success=True)

    def build_package(self, pkg: Package):
        # ダウンロードされたファイルを取得する
        localpath = pkg.get_fetched_location(self)
        if localpath is None:
            yield PackageManager.NOT_FETCHED
            return

        # ビルドを実行する
        build_success = False
        destpath = self.dist_dir / pkg.name
        for status in run_py_build(localpath.get(), destpath.get()):
            if milestone.match_type(status, PackageManager.EXEC_END):
                # ビルドが完了した
                build_success = status.returncode == 0
            yield status

        if not build_success:
            return

        # データベースに記帳する -> パッケージオブジェクトでも更新された状態が取得できる
        self.state_db.update_on_dist(pkg, destpath.name())
        yield PackageManager.FINISHED(name="build", success=True)

    #
    # ダウンロード、インストール、更新、アンインストール、ビルド
    #
    def fetch(self, pkg: Package, latest=False):
        if latest:
            yield from self.fetch_package(pkg, FETCH_TARGET_COMMIT_LATEST)
        else:
            yield from self.fetch_package(pkg, FETCH_TARGET_COMMIT_SPECIFIED)

    def build(self, pkg: Package):
        if not pkg.is_modules():
            # ビルド不要
            return
        if not pkg.is_fetched():
            yield from self.fetch_package(pkg, FETCH_TARGET_COMMIT_SPECIFIED)
        yield from self.build_package(pkg)

    def remove(self, pkg: Package):
        if not pkg.is_modules():
            # アンインストール不要
            return
        
        # ダウンロードフォルダ・配布フォルダからディレクトリを削除する
        fetch_dir = pkg.get_fetched_location(self)
        if fetch_dir is not None:
            fetch_dir.rmtree()
            yield PackageManager.MESSAGE(msg="削除：{}".format(fetch_dir))
        dist_dir = pkg.get_dist_location(self)
        if dist_dir is not None:
            dist_dir.rmtree()
            yield PackageManager.MESSAGE(msg="削除：{}".format(dist_dir))
        
        # データベースから取り除く
        self.state_db.remove(pkg.name)

    def upload(self, url: str, username: str|None = None, password: str|None = None):
        # 一括で送信する
        targets = []
        for d in self.dist_dir.listdirdir():
            if d.name().startswith("."):
                continue
            targets.append(d / "*")
        yield from run_py_twine([x.get() for x in targets], url, username or ".", password or ".")
        yield PackageManager.FINISHED(name="upload", success=True)

    #
    # 進行状態を示すマイルストーン
    #
    ALREADY_INSTALLED = milestone()

    @milestone.dataclass
    class DOWNLOAD_START:
        total: int|None
        url: str

    @milestone.dataclass
    class DOWNLOADING:
        total: int|None
        size: int

    @milestone.dataclass
    class DOWNLOAD_END:
        total: int|None

    @milestone.dataclass
    class DOWNLOAD_ERROR:
        error: Exception

    @milestone.dataclass
    class EXTRACTED_COMMIT:
        commit: str

    @milestone.dataclass
    class EXTRACTED_FILES:
        path: str

    NOT_FETCHED = milestone()

    @milestone.dataclass
    class EXEC_START:
        name: str
        command: str

    @milestone.dataclass
    class EXEC_END:
        name: str
        returncode: int

    @milestone.dataclass
    class MESSAGE:
        msg: str

    @milestone.dataclass
    class FINISHED:
        name: str
        success: bool

#
#
#
def _machaon_package(cfg: Config) -> Package:
    """ 最新のmachaonパッケージを参照する """
    from machaon.package.repository import GithubRepArchive
    repo = GithubRepArchive("betasewer/machaon:master", cred=None)
    return Package(
        name="machaon",
        source=repo,
        type=PACKAGE_TYPE_IMPORT,
        target_commit=None,
        listname="<default>",
        fetch_state=cfg.section("fetch.machaon"),
        dist_state=cfg.section("dist.machaon")
    )

#
# パッケージのダウンロード・展開オブジェクト
#
class LocalPackageExtraction:
    """ ローカルフォルダを展開する """
    def __init__(self, rep):
        if not isinstance(rep, LocalFile):
            raise TypeError("rep")
        self.rep: LocalFile = rep

    def __enter__(self):
        return self
    
    def __exit__(self, et, ev, tb):
        pass
    
    def __iter__(self):
        # 単にパスを取得する
        localpath = self.rep.get_local_path()
        yield PackageManager.EXTRACTED_FILES(path=localpath)

class ArchivePackageExtraction:
    """ ローカルアーカイブファイルを展開する """
    def __init__(self, rep):
        self.rep = rep
        from machaon.types.shell import TemporaryDirectory
        self.tempdir = TemporaryDirectory()
        self._enter = False

    def __enter__(self):
        self.tempdir.__enter__()
        self._enter = True
        return self

    def __exit__(self, et, ev, tb):
        self.tempdir.__exit__(et, ev, tb)
        self._enter = False

    def must_be_entered(self):
        if not self._enter:
            raise ValueError("Not Entered")

    def __iter__(self):
        self.must_be_entered()

        rep: BasicArchive = self.rep
        arcfilepath = rep.get_arcfilepath(self.tempdir.get())
        out = self.tempdir.path() / "content"
        out.makedirs()
        localpath = rep.extract(arcfilepath, out.get())
        yield PackageManager.EXTRACTED_FILES(path=localpath)
    
class RemotePackageExtraction:
    """ リモートリポジトリからダウンロードして展開する """
    def __init__(self, rep, target_commit):
        self._rep_archive = ArchivePackageExtraction(rep)
        self.target_commit = target_commit
        
    def __enter__(self):
        self._rep_archive.__enter__()
        return self

    def __exit__(self, et, ev, tb):
        self._rep_archive.__exit__(et, ev, tb)
    
    def __iter__(self):
        self._rep_archive.must_be_entered()
        
        # リモートアーカイブをダウンロードする
        rep: RepositoryArchive = self._rep_archive.rep
        try:
            url = rep.get_download_url(self.target_commit)
            total = rep.query_download_size(self.target_commit)
            yield PackageManager.DOWNLOAD_START(total=total, url=url)

            arcfilepath = rep.get_arcfilepath(self._rep_archive.tempdir.get())
            for size in rep.download_iter(arcfilepath, self.target_commit):
                yield PackageManager.DOWNLOADING(size=size, total=total)
                
            yield PackageManager.DOWNLOAD_END(total=total)

        except RepositoryURLError as e:
            yield PackageManager.DOWNLOAD_ERROR(error=e.get_basic())
            return
        
        # 得られたコミットハッシュを取得する
        if self.target_commit is not None:
            fetched_commit = self.target_commit
        else:
            fetched_commit = rep.query_latest_commit()
        yield PackageManager.EXTRACTED_COMMIT(commit=fetched_commit)
        
        # ローカルアーカイブの処理を行う
        yield from self._rep_archive.__iter__()
    

def _run_py_main(module: str, args: list[str]):
    """ Pythonのモジュールの__main__を実行する """
    import runpy

    yield PackageManager.EXEC_START(name=module, command=module + " " + " ".join(args))

    # コマンドライン引数を置換する
    orig_args = sys.argv[:]
    try:
        sys.argv[1:] = args
        runpy.run_module(module, { "sys": sys }, run_name="__main__", alter_sys=True)
    except SystemExit as e:
        if e.code is not None:
            # 異常終了した
            try:
                ecode = int(e.code)
            except:
                ecode = -1
            if ecode != 0:
                yield PackageManager.EXEC_END(name=module, returncode=ecode)
                return
    finally:
        sys.argv = orig_args
    
    # 正常に終了した
    yield PackageManager.EXEC_END(name=module, returncode=0)
    return


def run_py_build(sourcedir: str, destdir: str):
    """
    Pythonのビルドコマンドを実行する
    """
    if not module_loader("build").exists():
        yield PackageManager.MESSAGE(msg="モジュール 'build' が無く、ビルドできません。")
        return
    yield from _run_py_main("build", [sourcedir, "-o", destdir])


def run_py_twine(dist: Iterable[str], url: str, username: str, password: str):
    """
    ビルド済みパッケージを送信する
    """
    if not module_loader("twine").exists():
        yield PackageManager.MESSAGE(msg="'twine' パッケージが無く、送信を行えません。")
        return
    cmd = ["upload",
            "--repository-url", url, 
            "--username", username,
            "--password", password,
            *dist
        ]
    yield from _run_py_main("twine", cmd)



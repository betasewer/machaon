import os
import shutil
import sys
import tempfile
import configparser
import re
import importlib
from typing import Dict, Any, Sized, Union, List, Optional, Iterator

from machaon.core.importer import module_loader, PyBasicModuleLoader, PyModuleLoader
from machaon.core.error import ErrorSet
from machaon.types.shell import Path
from machaon.types.file import TextFile
from machaon.milestone import milestone, milestone_msg
from machaon.package.repository import RepositoryArchive, RepositoryURLError
from machaon.package.archive import BasicArchive, LocalFile
from machaon.package.auth import CredentialDir




#
class DatabaseNotLoadedError(Exception):
    pass

PACKAGE_TYPE_MODULES = 0x1
PACKAGE_TYPE_DEPENDENCY = 0x2
PACKAGE_TYPE_RESOURCE = 0x3
PACKAGE_TYPE_UNDEFINED = 0x4
PACKAGE_TYPE_SINGLE_MODULE = 0x5

class PACKAGE_LOAD_END:
    pass

#
#
#
class Package:
    MODULES = PACKAGE_TYPE_MODULES
    SINGLE_MODULE = PACKAGE_TYPE_SINGLE_MODULE
    DEPENDENCY = PACKAGE_TYPE_DEPENDENCY
    RESOURCE = PACKAGE_TYPE_RESOURCE
    UNDEFINED = PACKAGE_TYPE_UNDEFINED

    def __init__(self, 
        name: str, 
        source: Any, 
        type: int = None,
        module: Optional[str] = None, 
        separate = True,
        commit = None
    ):
        self.name: str = name
        self.source: BasicArchive = source
        self.separate: bool = separate
        self.entrypoint: Optional[str] = module
        self._type = type or PACKAGE_TYPE_MODULES
        self._hash = commit or None
        self._remote_creds: CredentialDir = None
        
        if self.is_module_source() and self.entrypoint is None:
            raise ValueError("Package: 'module'でエントリポイントモジュール名を指定してください")
    
    @property
    def source_name(self):
        if self.source is None:
            raise ValueError("No source")
        return self.source.get_name() 

    def get_source_signature(self):
        if self.source is None:
            raise ValueError("No source")
        return self.source.get_source()
    
    def get_source(self) -> BasicArchive:
        return self.source
    
    def is_remote_source(self) -> bool:
        return isinstance(self.source, RepositoryArchive)

    def is_module_source(self) -> bool:
        return getattr(self.source, "is_module", False) is True
    
    def is_installation_separated(self) -> bool:
        return self.separate

    def get_target_hash(self):
        return self._hash
    
    def load_latest_hash(self, *, fallback=True) -> Optional[str]:
        if self.source is None:
            return None
        if not isinstance(self.source, RepositoryArchive):
            raise ValueError("source is not a RepositoryArchive")
        try:
            hash_ = self.source.query_hash(cred=self.find_remote_credential())
        except RepositoryURLError:
            if not fallback:
                raise 
            return None 
        return hash_

    def is_type_modules(self) -> bool:
        return self._type == PACKAGE_TYPE_MODULES or self._type == PACKAGE_TYPE_SINGLE_MODULE

    def is_dependency_modules(self) -> bool:
        return self._type == PACKAGE_TYPE_DEPENDENCY
    
    def is_resource(self) -> bool:
        return self._type == PACKAGE_TYPE_RESOURCE
    
    def is_undefined(self) -> bool:
        return self._type == PACKAGE_TYPE_UNDEFINED
    
    def is_ready(self) -> bool:
        """ エントリポイントのモジュールが読み込み可能かチェックする """
        if self._type == PACKAGE_TYPE_RESOURCE:
            return False
        elif self._type == PACKAGE_TYPE_MODULES:        
            # エントリポイントのモジュールが読み込み可能かチェックする
            if self.entrypoint is None:
                raise ValueError("エントリモジュールが指定されていません")

            # 親モジュールから順に確認する
            mparts = self.entrypoint.split(".")
            for i in range(len(mparts)):
                mp = ".".join(mparts[0:i+1])
                spec = importlib.util.find_spec(mp)
                if spec is None:
                    return False
            return True
    
    #
    # モジュールロード
    #
    def load_initial_declaration(self):
        """ イニシャルモジュールの宣言をロードする """
        # モジュールのdocstringを読みに行く
        initial_module = self.get_initial_module()
        if initial_module is None:
            raise ValueError("エントリモジュールが指定されていません")
        initial_module.load_module_declaration()
        return initial_module

    def get_initial_module(self):
        if self.entrypoint is None:
            return None
        return module_loader(self.entrypoint)
    

    #
    #
    #
    def set_remote_credentials(self, creds):
        """ 認証が必要なパッケージとする """
        self._remote_creds = creds

    def find_remote_credential(self):
        """ 認証オブジェクトを作成する """
        if self._remote_creds is None:
            return None
        return self._remote_creds.search_from_repository(self.get_source())
    
    #
    def extraction(self, target_commit=None):
        """ パッケージ展開オブジェクトを作成する """
        rep = self.get_source()
        if isinstance(rep, RepositoryArchive):
            return RemotePackageExtraction(rep, target_commit, self.find_remote_credential())
        elif isinstance(rep, BasicArchive):
            return ArchivePackageExtraction(rep)
        else:
            return LocalPackageExtraction(rep)


def create_package(name, package, module=None, host=None, *, separate=True, package_type=None):
    """
    文字列の指定を受けてモジュールパッケージの種類を切り替え、読み込み前のインスタンスを作成する。
    """
    remote_reporitory_classes = {
        "github": ("machaon.package.repository", "GithubRepArchive"),
        "bitbucket": ("machaon.package.repository", "BitbucketRepArchive"),
    }

    pkgtype = package_type
    commit = None
    if isinstance(package, str):
        if host is None:
            host, sep, desc = package.partition(":")
            if not sep:
                raise ValueError("package: '{}' ':'でパッケージの種類を指定してください".format(package))
        else:
            desc = package

        if host in remote_reporitory_classes:
            # コミットハッシュの指定
            desc, sep, commit = desc.partition("+")
            from machaon.core.importer import attribute_loader
            klass = attribute_loader(remote_reporitory_classes[host][0], attr=remote_reporitory_classes[host][1])()
            pkgsource = klass(desc)
        elif host == "package":
            from machaon.package.archive import LocalModule
            module = desc
            pkgsource = LocalModule(module)
        elif host == "module":
            from machaon.package.archive import LocalModule
            module = desc
            pkgsource = LocalModule(module)
            if pkgtype is None:
                pkgtype = PACKAGE_TYPE_SINGLE_MODULE
        elif host == "file":
            from machaon.package.archive import LocalFile
            pkgsource = LocalFile(desc)
            if pkgtype is None:
                pkgtype = PACKAGE_TYPE_SINGLE_MODULE
        elif host == "package-arc":
            from machaon.package.archive import LocalArchive
            pkgsource = LocalArchive(desc)
        else:
            raise ValueError("package: '{}' サポートされていないホストです".format(host))
    else:
        pkgsource = package
    
    return Package(name, pkgsource, module=module, type=pkgtype, separate=separate, commit=commit)


def create_module_package(module):
    return create_package("module-{}".format(module), "module:{}".format(module), module)



#
class PackageNotFoundError(Exception):
    def __str__(self):
        name = self.args[0]
        msg = "パッケージ'{}'は存在しません".format(name)
        if ":" not in name:
            msg += ": リスト名を後に続けた完全な名前で指定してください"
        return msg

class PackageLoadError(Exception):
    def __init__(self, s, e=None):
        super().__init__(s, e)
    
    def child_exception(self):
        return super().args[1]
    
    def get_string(self):
        return super().args[0]

class PackageModuleLoadError(Exception):
    def __init__(self, e, name):
        super().__init__(e, name)
    
    def child_exception(self):
        return super().args[0]
    
    def get_module_name(self):
        return super().args[1]
    
#
#
#
class PackageLocalOption:
    def __init__(self, *, no_dependency=None):
        self.no_dependency = no_dependency or False

    def make_pip_options(self, opts: list):
        if self.no_dependency:
            opts.append("--no-deps")

#
#
#
class PackageDistInfo:
    def __init__(self, *, toplevel=None, infodir=None, is_resource=False):
        self.toplevel = toplevel
        self.infodir = infodir
        self.is_resource: bool = is_resource

#
#
#
class PackageFilePath:
    DELIMITER = "/"

    def __init__(self, package: str, path: Path):
        if not isinstance(path, Path):
            path = Path(path)
        self.package: str = package
        self.path: Path = path

    @classmethod
    def parse(cls, s: str):
        pkg, sep, path = s.partition(cls.DELIMITER)
        if not sep:
            raise ValueError(s)
        return cls(pkg, Path(path))

    def stringify(self):
        return self.package + self.DELIMITER + self.path.get()
    
    def join(self, path):  
        return PackageFilePath(self.package, self.path / path)


class PackageItem:
    def __init__(self, package: 'Package', path: PackageFilePath):
        self.package = package
        self.path = path

    def stringify(self):
        return self.path.stringify()

    def join(self, path):  
        return PackageItem(self.package, self.path.join(path))
    
    def as_module_name(self) -> str:
        """ モジュール名を復元する """
        p = self.path.path.without_ext()
        return ".".join([self.package.entrypoint, *p.split()])

#
#
#
class PackageManager:    
    ALREADY_INSTALLED = milestone()
    DOWNLOAD_START = milestone_msg("total", "url")
    DOWNLOADING = milestone_msg("size")
    DOWNLOAD_END = milestone_msg("total")
    DOWNLOAD_ERROR = milestone_msg("error")
    EXTRACTED_FILES = milestone_msg("path")
    NOT_INSTALLED = milestone()
    UNINSTALLING = milestone()
    PIP_INSTALLING = milestone()
    PIP_UNINSTALLING = milestone()
    PIP_END = milestone_msg("returncode")
    MESSAGE = milestone_msg("msg")

    INSTALL_TARGET_VERSION = 1
    INSTALL_LATEST_VERSION = 2

    def __init__(self, directory: Path, credentials: CredentialDir, options: dict=None):
        self.dir = Path(directory)
        # パッケージ
        self.packages = []
        self._creds: CredentialDir = credentials # 認証情報
        # 更新データベース
        self.database = None # type: configparser.ConfigParser
        self._dbpath = None
        # ローカルオプション
        if options is not None:
            self._options = {k:PackageLocalOption(**values) for k,values in options.items()}
        else:
            self._options = {}

    def add_to_import_path(self):
        """ パッケージディレクトリをモジュールパスに追加する """
        p = self.dir.get()
        if p not in sys.path:
            sys.path.insert(0, p)
    
    #
    # パッケージ更新データベース
    #
    def load_database(self, databasepath: Path, *, force=False):
        if not force and self.database is not None:
            return
        
        if databasepath.isfile():
            # ファイルを読み込む
            cfg = configparser.ConfigParser()
            with TextFile(databasepath, encoding="utf-8").read_stream() as fi:
                cfg.read_file(fi.stream)
            self.database = cfg
        else:
            # 空データ
            self.database = configparser.ConfigParser()
        self._dbpath = databasepath
        return True

    def add_database(self, pkg: Package, target_commit=None, toplevel=None, infodir=None):
        self.check_database()
        if pkg.name not in self.database:
            self.database[pkg.name] = {}
        
        self.database.set(pkg.name, "source", pkg.get_source_signature())
        if target_commit is not None:
            self.database.set(pkg.name, "hash", target_commit)
        
        separated = pkg.is_installation_separated()
        if separated is not None:
            self.database.set(pkg.name, "separate", str(separated))
        if toplevel is not None:
            self.database.set(pkg.name, "toplevel", toplevel)
        if infodir is not None:
            self.database.set(pkg.name, "infodir", str(infodir))
            
        self.save_database()
    
    def remove_database(self, name):
        self.check_database()
        self.database.remove_section(name)
        self.save_database()
    
    def save_database(self):
        if self.database is None:
            raise DatabaseNotLoadedError()
        self.dir.makedirs()
        with open(self._dbpath, "w", encoding="utf-8") as fo:
            self.database.write(fo)
        #print("save setting file '{}'".format(self._dbpath))
    
    def check_database(self):
        if self.database is None:
            raise DatabaseNotLoadedError()
             
    def is_installed(self, pkg):
        self.check_database()
        if isinstance(pkg, Package):
            if not pkg.is_remote_source():
                return True
            pkgname = pkg.name
        elif isinstance(pkg, str):
            pkgname = pkg
        else:
            raise TypeError(repr(pkg))
        return self.database.has_section(pkgname)
    
    #
    # リポジトリリスト
    #
    def load_packages(self, pkglistdir:Path, *, force=False):
        """ リポジトリリストからパッケージ定義を読み込む """
        if not force and self.packages:
            return
        
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
        # リストファイルを読み込む
        repolist = configparser.ConfigParser()
        with TextFile(configfile, encoding="utf-8").read_stream() as fi:
            repolist.read_file(fi.stream)
        
        errset = ErrorSet("パッケージ定義'{}'の読み込み".format(configfile))
        listname = configfile.basename()
        for sectname in repolist.sections():
            try:
                pkgname = "{}:{}".format(sectname, listname)
                repo = repolist.get(sectname, "repository", fallback=None)
                if repo is None:
                    continue

                module = None
                pkgtype = None
                isresource = repolist.get(sectname, "resource", fallback=False)
                if isresource:
                    pkgtype = PACKAGE_TYPE_RESOURCE
                else:
                    module = repolist.get(sectname, "module", fallback=sectname)

                pkg = create_package(pkgname, repo, module, package_type=pkgtype)

                private = repolist.get(sectname, "private", fallback=False)
                if private:
                    pkg.set_remote_credentials(self._creds)
            except Exception as e:
                errset.add(e, message="セクション'{}'".format(sectname))

            self.packages.append(pkg)
        
        errset.throw_if_failed()

    def get(self, name, *, fallback=True) -> Optional[Package]:
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
    # 
    #
    def get_item(self, path: PackageFilePath, *, fallback=True) -> Optional[PackageItem]:
        """ """
        pkg = self.get(path.package, fallback=fallback)
        if pkg is None:
            return None
        return PackageItem(pkg, path)
    
    def get_item_path(self, item: PackageItem) -> Path:
        loc = self.get_installed_location(item.package)
        return loc / item.path.path

    #
    #
    #
    def install(self, pkg: Package, install_type: int, pip_options=None):
        if pkg.is_module_source():
            # インストールは不要
            return
        
        # インストールするコミットを決定する
        if install_type == PackageManager.INSTALL_TARGET_VERSION:
            target_commit = pkg.get_target_hash()
        elif install_type == PackageManager.INSTALL_LATEST_VERSION:
            target_commit = None
        else:
            raise ValueError("Invalid install type: " + install_type)

        # ダウンロードと展開を行う
        localpath = None
        with pkg.extraction(target_commit) as extractor:
            for status in extractor:
                if status == PackageManager.EXTRACTED_FILES:
                    # 展開が完了した
                    localpath = status.path
                    if localpath is None:
                        return
                    
                    # インストールする
                    if pkg.is_type_modules():
                        installation = self.package_installation(pkg, localpath, pip_options)
                    elif pkg.is_dependency_modules() or pkg.is_resource():
                        installation = self.files_installation(pkg, localpath)
                    else:
                        return
                    distinfo = None
                    for insstatus in installation:
                        if isinstance(insstatus, PackageDistInfo):
                            distinfo = insstatus
                            continue
                        yield insstatus
                    
                    # インストールされたコミットのハッシュを得る
                    if target_commit is None:
                        installed_commit = pkg.load_latest_hash()
                    else:
                        installed_commit = target_commit
                    
                    if distinfo is not None:
                        # 新規インストールに成功
                        # インストール完了後、パッケージの情報を修正する
                        #if distinfo.toplevel is not None:
                        #    if pkg.entrypoint is None:
                        #        pkg.entrypoint = distinfo.toplevel
                        # データベースに書き込む 
                        self.add_database(pkg, installed_commit, toplevel=distinfo.toplevel, infodir=distinfo.infodir)
                    else:
                        # 更新のインストールに成功
                        self.add_database(pkg, installed_commit)
                else:
                    yield status
                    continue

        # モジュールファインダーに新しいモジュールの存在を気づかせる
        importlib.invalidate_caches()

    def package_installation(self, pkg, localpath, pip_options=None):     
        """ Pythonパッケージをpipによってインストールする """
        newinstall = pkg.name not in self.database
        if newinstall:
            isseparate = pkg.is_installation_separated()
        else:
            isseparate = self.database.getboolean(pkg.name, "separate", fallback=True)
        installdir = self.dir if isseparate else None

        pip_options = list(pip_options) if pip_options else []
        if pkg.name in self._options:
            self._options[pkg.name].make_pip_options(pip_options)
        
        yield from run_pip(installtarget=localpath, installdir=installdir, options=pip_options)

        if newinstall:
            # pipが作成したデータを見に行く
            if pkg.is_installation_separated():
                distinfo = _read_pip_dist_info(self.dir, pkg.get_source().get_name())
                yield distinfo
        else:
            pass

    def files_installation(self, pkg: Package, localpath):
        """ 展開ディレクトリに含まれるファイルをすべてコピーする """ 
        localname, _sep, _defsname = pkg.name.partition(":")
        installdir = (self.dir / localname).makedirs()        
        yield PackageManager.MESSAGE.bind(msg="コピー：{} -> {}".format(localpath, installdir))
        for localp in Path(localpath).listdir():
            if localp.isfile():
                destp = localp.copy_to(installdir, overwrite=True)
            elif localp.isdir():
                destdir = installdir / localp.name()
                destp = shutil.copytree(localp, destdir, dirs_exist_ok=True)
            else:
                continue
            yield PackageManager.MESSAGE.bind(msg="コピー：    {}".format(destp.name()))

        distinfo = PackageDistInfo(is_resource=pkg.is_resource())
        distinfo.infodir = installdir
        yield distinfo

    def update(self, pkg, options=None):
        return self.install(pkg, PackageManager.INSTALL_LATEST_VERSION, options)

    def uninstall(self, pkg: Package):
        if pkg.is_module_source():
            # アンインストールは不要
            return
        if not self.is_installed(pkg):
            return
        
        separate = self.database.getboolean(pkg.name, "separate", fallback=False)
        if separate:
            # 手動でディレクトリを削除する
            toplevel = self.database.get(pkg.name, "toplevel", fallback=None)
            if toplevel:
                p = self.dir / toplevel
                p.rmtree()
                yield PackageManager.MESSAGE(msg="削除：{}".format(p))
            infodir = self.database.get(pkg.name, "infodir", fallback=None)
            if infodir:
                p = self.dir / infodir
                p.rmtree()
                yield PackageManager.MESSAGE(msg="削除：{}".format(p))
        else:
            # pipにアンインストールさせる
            yield PackageManager.PIP_UNINSTALLING
            yield from run_pip(
                uninstalltarget=pkg.name,
                options=["--yes"]
            )
            
        self.remove_database(pkg.name)
    
    def get_installed_hash(self, pkg) -> Optional[str]:
        """ インストールされたバージョンのハッシュ値 """
        if not self.is_installed(pkg.name):
            return None
        entry = self.database[pkg.name]
        if "hash" not in entry:
            return None
        return entry["hash"]

    def get_installed_location(self, pkg: Package) -> Path:
        """ パッケージがインストールされたパス """
        if not self.is_installed(pkg.name):
            return None
        if pkg.is_type_modules():
            separated_install = self.database.get(pkg.name, "separate", fallback=False)
            if separated_install:
                toplevel = self.database.get(pkg.name, "toplevel", fallback=False)
                if toplevel:
                    return self.dir / toplevel
                raise ValueError("'toplevel' is defined in package.ini: {} (type module)".format(pkg.name))
            else:
                raise NotImplementedError()
        elif pkg.is_dependency_modules() or pkg.is_resource():
            infodir = self.database.get(pkg.name, "infodir", fallback=None)
            if infodir:
                return Path(infodir)
            raise ValueError("'infodir' is defined in package.ini: {} (dependency)".format(pkg.name))
        else:
            raise ValueError("unsupported package type")

    
    def query_update_status(self, pkg: Package, *, fallback=True) -> str:
        """ パッケージが最新か、通信して確かめる """
        if not pkg.is_remote_source():
            return "latest"
        # hashを比較して変更を検知する
        installed_hash = self.get_installed_hash(pkg)
        if installed_hash is None:
            return "notfound"
        latest_hash = pkg.load_latest_hash(fallback=fallback) # リモートリポジトリに最新のハッシュ値を問い合わせる
        if latest_hash is None:
            return "unknown"
        if installed_hash == latest_hash:
            return "latest"
        else:
            return "old"
        
    def get_core_package(self):
        """ machaonをパッケージとして取得する """
        return create_package("machaon", "betasewer/machaon", module="machaon", host="github")

    def update_core(self, *, location=None):
        """ machaonをアップデートする """
        # インストールディレクトリ
        if location is None:
            curmodule = PyModuleLoader("machaon")
            modlocation = curmodule.load_filepath()
            if modlocation is None:
                raise ValueError("machaonのインストール先が不明です")
            installdir = (Path(modlocation).dir() / "..").normalize()
        else:
            installdir = Path(location)

        lock = (installdir / ".." / ".machaon-update-lock").normalize()
        if lock.exists():
            raise ValueError("{}: 上書きしないようにロックされています".format(lock))

        with self.get_core_package().extraction() as extraction:
            for status in extraction:
                if status == PackageManager.EXTRACTED_FILES:
                    if status.path is None:
                        return
                    yield PackageManager.PIP_INSTALLING
                    yield from run_pip(installtarget=status.path, installdir=installdir, options=["--upgrade"])
                else:
                    yield status
    
    def check_after_loading(self):
        """ 読み込まれたパッケージを確認する """
        errs = ErrorSet("パッケージマネージャの初期化")
        for pkgname, _opt in self._options.items():
            if self.get(pkgname) is None:
                errs.add(None, message="ローカルオプション'{}'には対応するパッケージがありません".format(pkgname))
        errs.throw_if_failed()
    

#
#
#
#
#
class LocalPackageExtraction:
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
        yield PackageManager.EXTRACTED_FILES.bind(path=localpath)


class ArchivePackageExtraction:
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
        yield PackageManager.EXTRACTED_FILES.bind(path=localpath)
    

class RemotePackageExtraction(ArchivePackageExtraction):
    def __init__(self, rep, target_commit, cred):
        super().__init__(rep)
        self.cred = cred
        self.target_commit = target_commit
        
    def __iter__(self):
        self.must_be_entered()
        
        # リモートアーカイブをダウンロードする
        rep: RepositoryArchive = self.rep
        try:
            url = rep.get_download_url(self.target_commit)
            total = rep.query_download_size(self.target_commit, self.cred)
            yield PackageManager.DOWNLOAD_START.bind(total=total, url=url)

            arcfilepath = rep.get_arcfilepath(self.tempdir.get())
            for size in rep.download_iter(arcfilepath, self.target_commit, self.cred):
                yield PackageManager.DOWNLOADING.bind(size=size, total=total)
                
            yield PackageManager.DOWNLOAD_END.bind(total=total)

        except RepositoryURLError as e:
            yield PackageManager.DOWNLOAD_ERROR.bind(error=e.get_basic())
            return
        
        # ローカルアーカイブの処理を行う
        yield from super().__iter__()
    





def run_pip(installtarget=None, installdir=None, uninstalltarget=None, options=()):
    yield PackageManager.PIP_INSTALLING
    
    cmd = [sys.executable, "-m", "pip"]

    if installtarget is not None:
        cmd.extend(["install", installtarget, "--upgrade"])
        if installdir is not None:
            cmd.extend(["-t", os.fspath(installdir)])
    elif uninstalltarget is not None:
        cmd.extend(["uninstall", uninstalltarget])
    else:
        raise ValueError("specify installtarget or uninstalltarget")
    
    if options:
        cmd.extend(options)
    
    yield PackageManager.MESSAGE.bind(msg=" ".join(cmd))

    from machaon.shellpopen import popen_capture
    proc = popen_capture(cmd)
    for msg in proc:
        if msg.is_output():
            yield PackageManager.MESSAGE.bind(msg=msg.text)
        if msg.is_finished():
            yield PackageManager.PIP_END.bind(returncode=msg.returncode)

#
#
#
def _read_pip_dist_info(directory: Path, pkg_name):
    """ pipがdist-infoフォルダに収めたパッケージの情報を読みとる """
    pkg_name = canonicalize_package_name(pkg_name)
    infodir = None
    for d in directory.listdirdir():
        if d.name().endswith(".dist-info"):
            p = d / "METADATA"
        elif d.name().endswith(".egg-info"):
            p = d / "PKG-INFO"
        else:
            continue
        
        if not p.isfile():
            continue
        
        namedata = None
        with open(p, "r", encoding="utf-8") as fi:
            for l in fi:
                key, _, value = [x.strip() for x in l.partition(":")]
                if key == "Name":
                    namedata = value
                    break
            else:
                continue

        if namedata and canonicalize_package_name(namedata) == pkg_name:
            infodir = d
            break
    else:
        raise PipDistInfoFolderNotFound()
    
    #
    distinfo = PackageDistInfo()
    distinfo.infodir = infodir
    
    p = infodir / "top_level.txt"
    with open(p, "r", encoding="utf-8") as fi:
        distinfo.toplevel = fi.read().strip()
    
    return distinfo

#
pep_503_normalization = re.compile(r"[-_.]+")
def canonicalize_package_name(name):
    return pep_503_normalization.sub("-", name).lower()

#
class PipDistInfoFolderNotFound(Exception):
    pass




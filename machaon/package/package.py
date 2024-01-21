import os
import shutil
import sys
import tempfile
import configparser
import re
import importlib
from typing import Dict, Any, Sized, Union, List, Optional, Iterator

from machaon.core.type.typemodule import TypeModule
from machaon.core.importer import module_loader, PyBasicModuleLoader, PyModuleLoader
from machaon.core.error import ErrorSet
from machaon.types.shell import Path
from machaon.types.file import TextFile
from machaon.milestone import milestone, milestone_msg
from machaon.package.repository import RepositoryArchive, RepositoryURLError
from machaon.package.archive import BasicArchive
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
        hashval = None, 
    ):
        self.name: str = name
        self.source: BasicArchive = source
        self.separate: bool = separate
        
        if type is None: 
            type = PACKAGE_TYPE_MODULES
        self._type = type

        self.entrypoint: Optional[str] = module

        self._hash = hashval
        self._remote_creds: CredentialDir = None
    
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

    def get_hash(self):
        return self._hash
    
    def load_latest_hash(self) -> Optional[str]:
        if self.source is None:
            return None
        try:
            _hash = self.source.query_hash()
        except RepositoryURLError:
            _hash = None 
        self._hash = "" if _hash is None else _hash
        return self._hash

    def is_type_modules(self) -> bool:
        return self._type == PACKAGE_TYPE_MODULES or self._type == PACKAGE_TYPE_SINGLE_MODULE

    def is_dependency_modules(self) -> bool:
        return self._type == PACKAGE_TYPE_DEPENDENCY
    
    def is_undefined(self) -> bool:
        return self._type == PACKAGE_TYPE_UNDEFINED
    
    def is_ready(self) -> bool:
        """ エントリポイントのモジュールが読み込み可能かチェックする """
        if self._type == PACKAGE_TYPE_RESOURCE:
            return False
        if self.entrypoint is None:
            raise ValueError("エントリモジュールが指定されていません")

        # エントリパスの親モジュールから順に確認する
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
    def load_declaration(self):
        """ イニシャルモジュールの宣言をロードする """
        # モジュールのdocstringを読みに行く
        initial_module = self.get_initial_module()
        initial_module.load_module_declaration()
        return initial_module

    def get_initial_module(self):
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
    def extraction(self):
        """ パッケージ展開オブジェクトを作成する """
        rep = self.get_source()
        if isinstance(rep, RepositoryArchive):
            return RemotePackageExtraction(rep, self.find_remote_credential())
        elif isinstance(rep, BasicArchive):
            return ArchivePackageExtraction(rep)
        else:
            return LocalPackageExtraction(rep)


def create_package(name, package, module=None, **kwargs):
    """
    文字列の指定を受けてモジュールパッケージの種類を切り替え、読み込み前のインスタンスを作成する。
    """
    pkgtype = None
    if isinstance(package, str):
        host, sep, desc = package.partition(":")
        if not sep:
            raise ValueError("package: '{}' ':'でパッケージの種類を指定してください".format(package))
        if host == "github":
            from machaon.package.repository import GithubRepArchive
            pkgsource = GithubRepArchive(desc)
        elif host == "bitbucket":
            from machaon.package.repository import BitbucketRepArchive
            pkgsource = BitbucketRepArchive(desc)
        elif host == "package":
            from machaon.package.archive import LocalModule
            module = desc
            pkgsource = LocalModule(module)
        elif host == "module":
            from machaon.package.archive import LocalModule
            module = desc
            pkgsource = LocalModule(module)
            pkgtype = PACKAGE_TYPE_SINGLE_MODULE
        elif host == "file":
            from machaon.package.archive import LocalFile
            pkgsource = LocalFile(desc)
            pkgtype = PACKAGE_TYPE_SINGLE_MODULE
        elif host == "package-arc":
            from machaon.package.archive import LocalArchive
            pkgsource = LocalArchive(desc)
        else:
            raise ValueError("package: '{}' サポートされていないホストです".format(host))
    else:
        pkgsource = package
    
    if module is None:
        raise ValueError("package: 'module'でエントリポイントモジュール名を指定してください")
    if pkgtype is not None:
        kwargs["type"] = pkgtype
    return Package(name, pkgsource, module=module, **kwargs)


def create_module_package(module):
    return create_package("module-{}".format(module), "module:{}".format(module))



#
class PackageNotFoundError(Exception):
    pass

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
class PackageManager():    
    ALREADY_INSTALLED = milestone()
    DOWNLOAD_START = milestone_msg("total")
    DOWNLOADING = milestone_msg("size")
    DOWNLOAD_END = milestone_msg("total")
    DOWNLOAD_ERROR = milestone_msg("error")
    EXTRACTED_FILES = milestone_msg("path")
    NOT_INSTALLED = milestone()
    UNINSTALLING = milestone()
    PIP_INSTALLING = milestone()
    PIP_UNINSTALLING = milestone()
    PIP_MSG = milestone_msg("msg")
    PIP_END = milestone_msg("returncode")

    def __init__(self, directory: Path, pkglistdir: Path, databasepath: Path, credentials: CredentialDir):
        self.dir = Path(directory)
        # パッケージ
        self._pkglistdir = Path(pkglistdir)
        self.packages = []
        self._creds: CredentialDir = credentials # 認証情報
        self._core = create_package("machaon", "github:betasewer/machaon")
        # 更新データベース
        self.database = None # type: configparser.ConfigParser
        self._dbpath = Path(databasepath)

    def add_to_import_path(self):
        """ パッケージディレクトリをモジュールパスに追加する """
        p = self.dir.get()
        if p not in sys.path:
            sys.path.insert(0, p)
    
    #
    # パッケージ更新データベース
    #
    def load_database(self, *, force=False):
        if not force and self.database is not None:
            return
        
        if self._dbpath.isfile():
            # ファイルを読み込む
            cfg = configparser.ConfigParser()
            with TextFile(self._dbpath, encoding="utf-8").read_stream() as fi:
                cfg.read_file(fi.stream)
            self.database = cfg
        else:
            # 空データ
            self.database = configparser.ConfigParser()
        return True

    def add_database(self, pkg: Package, toplevel=None, infodir=None):
        self.check_database()
        if pkg.name not in self.database:
            self.database[pkg.name] = {}
        
        self.database.set(pkg.name, "source", pkg.get_source_signature())
        self.database.set(pkg.name, "hash", pkg.load_latest_hash())
        
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
    def load_packages(self, *, force=False):
        """ リポジトリリストからパッケージ定義を読み込む """
        if not force and self.packages:
            return
        
        if not self._pkglistdir.isdir():
            return # パスが見つからず
        
        newpkgs = []
        
        # リストファイルのディレクトリを読み込む
        errset = ErrorSet("パッケージ定義の読み込み")
        for f in self._pkglistdir.listdirfile():
            if not f.hasext(".packages"):
                continue

            # リストファイルを読み込む
            repolist = configparser.ConfigParser()
            with TextFile(f, encoding="utf-8").read_stream() as fi:
                repolist.read_file(fi.stream)
            
            listname = f.basename()
            for sectname in repolist.sections():
                try:
                    pkgname = "{}.{}".format(listname, sectname)
                    repo = repolist.get(sectname, "repository", fallback=None)
                    module = repolist.get(sectname, "module", fallback=sectname)

                    if repo is None:
                        continue
                    pkg = create_package(pkgname, repo, module=module)

                    private = repolist.get(sectname, "private", fallback=False)
                    if private:
                        pkg.set_remote_credentials(self._creds)
                except Exception as e:
                    errset.add(e, message="定義'{}', セクション'{}'".format(f,sectname))

                newpkgs.append(pkg)
        
        self.packages = newpkgs
        errset.throw_if_failed()

    def get(self, name, *, fallback=True):
        for pkg in self.packages:
            if pkg.name == name:
                return pkg
        if not fallback:
            raise PackageNotFoundError(name)
        return None
    
    def getall(self):
        for pkg in self.packages:
            yield pkg

    def add(self, pkg: Package):
        """ 後から追加する """
        self.packages.append(pkg)

    #
    #
    #
    def install(self, pkg: Package, options=None, newinstall: bool=True):
        if pkg.is_module_source():
            # インストールは不要
            return

        # ダウンロードと展開を行う
        localpath = None
        with pkg.extraction() as extractor:
            for status in extractor:
                if status == PackageManager.EXTRACTED_FILES:
                    localpath = status.path
                    if localpath is None:
                        return

                    # pipにインストールさせる
                    yield PackageManager.PIP_INSTALLING

                    if not newinstall:
                        if pkg.name not in self.database:
                            newinstall = True

                    options = options or ()
                    if newinstall:
                        yield from run_pip(
                            installtarget=localpath, 
                            installdir=self.dir if pkg.is_installation_separated() else None,
                            options=options
                        )

                        # pipが作成したデータを見に行く
                        distinfo: Dict[str, str] = {}
                        if pkg.is_installation_separated():
                            distinfo = _read_pip_dist_info(self.dir, pkg.get_source().get_name())

                        # データベースに書き込む
                        self.add_database(pkg, **distinfo)

                    else:
                        isseparate = self.database.getboolean(pkg.name, "separate", fallback=True)   
                        yield from run_pip(
                            installtarget=localpath, 
                            installdir=self.dir if isseparate else None,
                            options=[*options, "--upgrade"]
                        )

                        # データベースに書き込む
                        self.add_database(pkg)
                
                else:
                    yield status
                    continue
        
        # インストール完了後、パッケージの情報を修正する
        if "toplevel" in self.database[pkg.name]:
            if pkg.entrypoint is None:
                pkg.entrypoint = self.database[pkg.name]["toplevel"]

    def update(self, pkg, options=None):
        return self.install(pkg, options, newinstall=False)

    def uninstall(self, pkg: Package):
        if pkg.is_module_source():
            # アンインストールは不要
            return
        
        separate = self.database.getboolean(pkg.name, "separate", fallback=False)
        if separate:
            # 手動でディレクトリを削除する
            yield PackageManager.UNINSTALLING
            toplevel = self.database.get(pkg.name, "toplevel", fallback=None)
            if toplevel:
                (self.dir / toplevel).rmtree()
            infodir = self.database.get(pkg.name, "infodir", fallback=None)
            if infodir:
                (self.dir / infodir).rmtree()
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
            raise ValueError("Bad Entry")
        return entry["hash"]

    def get_installed_location(self, pkg) -> Path:
        """ パッケージがインストールされたパス """
        if not self.is_installed(pkg.name):
            return None
        if self.database.get(pkg.name, "separate"):
            toplevel = self.database.get(pkg.name, "toplevel")
            if toplevel:
                return self.dir / toplevel
        else:
            raise NotImplementedError()
    
    def query_update_status(self, pkg: Package) -> str:
        """ パッケージが最新か、通信して確かめる """
        if not pkg.is_remote_source():
            return "latest"
        installed_hash = self.get_installed_hash(pkg)
        if installed_hash is None:
            return "notfound"
        # hashを比較して変更を検知する
        latest_hash = pkg.load_latest_hash() # リモートリポジトリに最新のハッシュ値を問い合わせる
        if latest_hash is None:
            return "unknown"
        if installed_hash == latest_hash:
            return "latest"
        else:
            return "old"
        
    def get_core_package(self):
        """ machaonをパッケージとして取得する """
        return self._core

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

        with self._core.extraction() as extraction:
            for status in extraction:
                if status == PackageManager.EXTRACTED_FILES:
                    if status.path is None:
                        return
                    yield PackageManager.PIP_INSTALLING
                    yield from run_pip(installtarget=status.path, installdir=installdir, options=["--upgrade"])
                else:
                    yield status
    


#
#
#
#
#
class LocalPackageExtraction:
    def __init__(self, rep):
        self.rep = rep

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
        
        arcfilepath = self.rep.get_arcfilepath(self.tempdir.get())
        out = self.tempdir.path() / "content"
        out.makedirs()
        localpath = self.rep.extract(arcfilepath, out.get())
        yield PackageManager.EXTRACTED_FILES.bind(path=localpath)
    

class RemotePackageExtraction(ArchivePackageExtraction):
    def __init__(self, rep, cred):
        super().__init__(rep)
        self.cred = cred
        
    def __iter__(self):
        self.must_be_entered()
        
        # リモートアーカイブをダウンロードする
        try:
            total = self.rep.query_download_size(self.cred)
            yield PackageManager.DOWNLOAD_START.bind(total=total)

            arcfilepath = self.rep.get_arcfilepath(self.tempdir.get())
            for size in self.rep.download_iter(arcfilepath, self.cred):
                yield PackageManager.DOWNLOADING.bind(size=size, total=total)
                
            yield PackageManager.DOWNLOAD_END.bind(total=total)

        except RepositoryURLError as e:
            yield PackageManager.DOWNLOAD_ERROR.bind(error=e.get_basic())
            return
        
        # ローカルアーカイブの処理を行う
        yield from super().__iter__()
    





def run_pip(installtarget=None, installdir=None, uninstalltarget=None, options=()):
    cmd = [sys.executable, "-m", "pip"]

    if installtarget is not None:
        cmd.extend(["install", installtarget])
    
    if uninstalltarget is not None:
        cmd.extend(["uninstall", uninstalltarget])
    
    if installdir is not None:
        cmd.extend(["-t", os.fspath(installdir)])
    
    if options:
        cmd.extend(options)
    
    yield PackageManager.PIP_MSG.bind(msg=" ".join(cmd))

    from machaon.shellpopen import popen_capture
    proc = popen_capture(cmd)
    for msg in proc:
        if msg.is_output():
            yield PackageManager.PIP_MSG.bind(msg=msg.text)
        if msg.is_finished():
            yield PackageManager.PIP_END.bind(returncode=msg.returncode)

#
#
#
def _read_pip_dist_info(directory: Path, pkg_name):
    """ pipがdist-infoフォルダに収めたパッケージの情報を読みとる """
    pkg_name = canonicalize_package_name(pkg_name)
    infodir = None
    for d in directory.listdirall():
        if not d.isdir():
            continue

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
    distinfo = {}
    distinfo["infodir"] = infodir
    
    p = infodir / "top_level.txt"
    with open(p, "r", encoding="utf-8") as fi:
        distinfo["toplevel"] = fi.read().strip()
    
    return distinfo

#
pep_503_normalization = re.compile(r"[-_.]+")
def canonicalize_package_name(name):
    return pep_503_normalization.sub("-", name).lower()

#
class PipDistInfoFolderNotFound(Exception):
    pass




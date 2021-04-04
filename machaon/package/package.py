import os
import shutil
import sys
import tempfile
import configparser
import re
import importlib
import inspect
import traceback
from typing import Dict, Any, Union, List, Optional

from machaon.core.importer import module_loader, attribute_loader, walk_modules, module_name_from_path
from machaon.milestone import milestone, milestone_msg
from machaon.package.repository import RepositoryURLError

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
class Package():
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
        self.source = source
        self.scope = self.name
        self.separate = separate
        
        if type is None: 
            type = Package.MODULES
        self._type = type

        self.entrypoint: Optional[str] = module

        self._hash = hashval

        self._loaded: List[Exception] = []
    
    def assign_definition(self, pkg):
        if not self.is_undefined():
            raise ValueError("既に定義されているパッケージです")
        self.name = pkg.name
        self.source = pkg.source
        self.scope = pkg.scope
        self.separate = pkg.separate
        self.entrypoint = pkg.entrypoint
        self._type = pkg._type
        self._hash = pkg._hash
        return self
    
    @property
    def source_name(self):
        if self.source is None:
            raise ValueError("No source")
        return self.source.name 

    def get_source_signature(self):
        if self.source is None:
            raise ValueError("No source")
        return self.source.get_source()
    
    def get_source(self):
        return self.source
    
    def get_hash(self):
        return self._hash

    def is_installation_separated(self) -> bool:
        return self.separate
    
    def load_hash(self) -> Optional[str]:
        if self.source is None:
            return None
        if self._hash is None:
            try:
                _hash = self.source.query_hash()
            except RepositoryURLError:
                _hash = None 
            self._hash = "" if _hash is None else _hash
        return self._hash

    def is_modules(self) -> bool:
        return self._type == PACKAGE_TYPE_MODULES or self._type == PACKAGE_TYPE_SINGLE_MODULE
    
    def is_undefined(self) -> bool:
        return self._type == PACKAGE_TYPE_UNDEFINED
    
    def is_installed(self) -> bool:
        if self._type == PACKAGE_TYPE_RESOURCE:
            return False
        if self.entrypoint is None:
            raise ValueError("entrypoint")

        # エントリパスの親モジュールから順に確認する
        mparts = self.entrypoint.split(".")
        for i in range(len(mparts)):
            mp = ".".join(mparts[0:i+1])
            spec = importlib.util.find_spec(mp)
            if spec is None:
                return False
        
        return True

    def iter_type_describers(self):
        """ パッケージ内のモジュールにあるすべての型定義クラスを得る """
        if self._type == PACKAGE_TYPE_UNDEFINED:
            raise PackageLoadError("パッケージの定義がありません")
        
        if self._type == PACKAGE_TYPE_MODULES:
            # __init__を読みに行く
            aloader = module_loader(self.entrypoint)
            try:
                moduleindex = aloader.load_attr("machaon_modules", fallback=True)
            except Exception as e:
                self._loaded.append(PackageLoadError(e))
                return False

            # 型が定義されたモジュールをロードする
            if moduleindex:
                # 指定されたモジュールのみ
                modules = [module_loader(x) for x in moduleindex]
            else:
                # サブモジュール全て
                modules = []
                basepkg = aloader.module_name
                basedir = os.path.dirname(aloader.load_filepath())

                # 再帰を避けるためにスタック上にあるソースファイルパスを調べる
                skip_names = []
                for fr in traceback.extract_stack():
                    fname = os.path.normpath(fr.filename)
                    if fname.startswith(basedir):
                        relname = module_name_from_path(fname, basedir, basepkg)
                        skip_names.append(relname)
                
                for loader in walk_modules(basedir, basepkg):
                    if loader.module_name in skip_names:
                        continue 
                    modules.append(loader)

        elif self._type == PACKAGE_TYPE_SINGLE_MODULE:
            loader = module_loader(self.entrypoint)
            modules = [loader]

        for modloader in modules:
            try:
                for klass in modloader.enum_type_describers():
                    yield klass
            except Exception as e:
                ex = PackageTypeDefLoadError(e, str(modloader))
                self._loaded.append(ex)
                continue
    
    def reset_loading(self):
        self._loaded.clear()
    
    def finish_loading(self):
        self._loaded.append(PACKAGE_LOAD_END)

    def once_loaded(self):
        return len(self._loaded) > 0
    
    def is_load_failed(self):
        if not self._loaded:
            return False
        return self._loaded[0] is not PACKAGE_LOAD_END
    
    def is_load_succeeded(self):
        if not self._loaded:
            return False
        return self._loaded[0] is PACKAGE_LOAD_END

    def get_load_errors(self) -> List[Exception]:
        errs = []
        for x in self._loaded:
            if x is PACKAGE_LOAD_END:
                break
            errs.append(x)
        return errs
    
    def get_last_load_error(self) -> Optional[Exception]:
        errors = self.get_load_errors()
        return errors[-1] if errors else None

    def unload(self, root):
        if self._type == PACKAGE_TYPE_UNDEFINED:
            raise PackageLoadError("パッケージの定義がありません")

        if not self._loaded:
            return

        if self._type == PACKAGE_TYPE_MODULES:
            root.typemodule.remove_scope(self.scope)

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
        elif host == "local":
            from machaon.package.archive import LocalModule
            pkgsource = LocalModule()
            module = desc
        elif host == "local-module":
            from machaon.package.archive import LocalModule
            pkgsource = LocalModule()
            module = desc
            pkgtype = PACKAGE_TYPE_SINGLE_MODULE
        elif host == "file-module":
            from machaon.package.archive import LocalFile
            pkgsource = LocalFile(desc)
            pkgtype = PACKAGE_TYPE_SINGLE_MODULE
        elif host == "archive":
            from machaon.package.archive import LocalArchive
            pkgsource = LocalArchive(desc)
        else:
            raise ValueError("package: '{}' サポートされていないホストです".format(host))
    else:
        pkgsource = package
    
    if pkgtype is not None:
        kwargs["type"] = pkgtype
    if module is None:
        module = pkgsource.get_default_module()
    return Package(name, pkgsource, module=module, **kwargs)

#
class PackageNotFoundError(Exception):
    pass

class PackageLoadError(Exception):
    def get_basic(self):
        return super().args[0]

class PackageTypeDefLoadError(Exception):
    def get_basic(self):
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
    PRIVATE_REQUIREMENTS = milestone_msg("names")
    NOT_INSTALLED = milestone()
    UNINSTALLING = milestone()
    PIP_INSTALLING = milestone()
    PIP_UNINSTALLING = milestone()
    PIP_MSG = milestone_msg("msg")
    PIP_END = milestone_msg("returncode")

    def __init__(self, directory, database="packages.ini"):
        self.dir = directory
        self.database = None # type: configparser.ConfigParser
        self._dbpath = os.path.join(directory, database)

    def load_database(self, force=False):
        if not force and self.database is not None:
            return
        
        if os.path.isfile(self._dbpath):
            # ファイルを読み込む
            cfg = configparser.ConfigParser()
            with open(self._dbpath, "r", encoding="utf-8") as fi:
                cfg.read_file(fi)
            self.database = cfg
        else:
            # 空データ
            self.database = configparser.ConfigParser()
        return True

    def add_database(self, pkg, toplevel=None, infodir=None):
        self.check_database()
        if pkg.name not in self.database:
            self.database[pkg.name] = {}
        
        self.database.set(pkg.name, "source", pkg.get_source_signature())
        self.database.set(pkg.name, "hash", pkg.load_hash())
        
        separated = pkg.is_installation_separated()
        if separated is not None:
            self.database.set(pkg.name, "separate", str(separated))
        if toplevel is not None:
            self.database.set(pkg.name, "toplevel", toplevel)
        if infodir is not None:
            self.database.set(pkg.name, "infodir", infodir)
            
        self.save_database()
    
    def remove_database(self, name):
        self.check_database()
        self.database.remove_section(name)
        self.save_database()
    
    def save_database(self):
        if self.database is None:
            raise DatabaseNotLoadedError()
        if not os.path.isdir(self.dir):
            os.makedirs(self.dir)
        with open(self._dbpath, "w", encoding="utf-8") as fo:
            self.database.write(fo)
        print("save setting file '{}'".format(self._dbpath))
    
    def create_undefined_empty_packages(self):
        pkgs = []
        for pkgname, section in self.database.items():
            if pkgname == "DEFAULT":
                continue
            pkg = Package(
                pkgname, 
                section["source"],
                PACKAGE_TYPE_UNDEFINED,
                section["separate"],
                hashval=section["hash"]
            )
            pkgs.append(pkg)
        return pkgs
    
    def check_database(self):
        if self.database is None:
            raise DatabaseNotLoadedError()
             
    def is_installed(self, pkg_name: str):
        self.check_database()
        if not isinstance(pkg_name, str):
            raise TypeError("pkg_name")
        return pkg_name in self.database

    #
    def install(self, pkg: Package, newinstall: bool):
        rep = pkg.get_source()

        tmpdir = ''
        def cleanup_tmpdir(d):
            shutil.rmtree(d)
            return ''

        if rep.is_remote:
            # ダウンロードする
            if not tmpdir: tmpdir = tempfile.mkdtemp()
            try:
                total = rep.query_download_size()
                yield PackageManager.DOWNLOAD_START.bind(total=total)

                arcfilepath = rep.get_arcfilepath(tmpdir)
                for size in rep.download_iter(arcfilepath):
                    yield PackageManager.DOWNLOADING.bind(size=size, total=total)
                    
                yield PackageManager.DOWNLOAD_END.bind(total=total)

            except RepositoryURLError as e:
                yield PackageManager.DOWNLOAD_ERROR.bind(error=e.get_basic())
                tmpdir = cleanup_tmpdir(tmpdir)
                return
            except Exception:
                tmpdir = cleanup_tmpdir(tmpdir)
                return

        localpath = None
        if rep.is_archive:
            # ローカルに展開する
            if not tmpdir: tmpdir = tempfile.mkdtemp()
            try:
                arcfilepath = rep.get_arcfilepath(tmpdir)
                out = os.path.join(tmpdir, "content")
                os.mkdir(out)
                localpath = rep.extract(arcfilepath, out)
            except Exception:
                cleanup_tmpdir(tmpdir)
                return
        else:
            # 単にパスを取得する
            localpath = rep.get_local_path()
            
        # pipにインストールさせる
        yield PackageManager.PIP_INSTALLING
        try:
            if newinstall:
                yield from _run_pip(
                    installtarget=localpath, 
                    installdir=self.dir if pkg.is_installation_separated() else None
                )

                # 非公開の依存パッケージを表示
                if os.path.isdir(localpath): # アーカイブの直接のインストールの場合は見に行かない
                    private_reqs = _read_private_requirements(localpath)
                    private_reqs = [name for name in private_reqs if not self.is_installed(name)]
                    if private_reqs:
                        yield PackageManager.PRIVATE_REQUIREMENTS.bind(names=private_reqs)
                
                # pipが作成したデータを見に行く
                distinfo: Dict[str, str] = {}
                if pkg.is_installation_separated():
                    distinfo = _read_pip_dist_info(self.dir, pkg.source_name)
            
                # データベースに書き込む
                self.add_database(pkg, **distinfo)

            else:
                isseparate = self.database.getboolean(pkg.name, "separate", fallback=False)   
                yield from _run_pip(
                    installtarget=localpath, 
                    installdir=self.dir if isseparate else None,
                    options=["--upgrade"]
                )

                # データベースに書き込む
                self.add_database(pkg)
        
        finally:
            tmpdir = cleanup_tmpdir(tmpdir)
        
    #
    def uninstall(self, pkg):
        separate = self.database.getboolean(pkg.name, "separate", fallback=False)
        if separate:
            # 手動でディレクトリを削除する
            yield PackageManager.UNINSTALLING
            toplevel = self.database[pkg.name]["toplevel"]
            shutil.rmtree(os.path.join(self.dir, toplevel))
            infodir = self.database[pkg.name]["infodir"]
            shutil.rmtree(os.path.join(self.dir, infodir))
        else:
            # pipにアンインストールさせる
            yield PackageManager.PIP_UNINSTALLING
            yield from _run_pip(
                uninstalltarget=pkg.name,
                options=["--yes"]
            )
            
        self.remove_database(pkg.name)
            
    def get_update_status(self, pkg) -> str:
        if not self.is_installed(pkg.name):
            return "none"
        # hashを比較して変更を検知する
        entry = self.database[pkg.name]
        hash_ = pkg.load_hash()
        if hash_ is None:
            return "unknown"
        if entry["hash"] == hash_:
            return "latest"
        else:
            return "old"
    
    def add_to_import_path(self):
        if self.dir not in sys.path:
            sys.path.insert(0, self.dir)

#
#
#
def _run_pip(installtarget=None, installdir=None, uninstalltarget=None, options=()):
    cmd = [sys.executable, "-m", "pip"]

    if installtarget is not None:
        cmd.extend(["install", installtarget])
    
    if uninstalltarget is not None:
        cmd.extend(["uninstall", uninstalltarget])
    
    if installdir is not None:
        cmd.extend(["-t", installdir])
    
    if options:
        cmd.extend(options)

    from machaon.shellpopen import popen_capture
    proc = popen_capture(cmd)
    for msg in proc:
        if msg.is_finished():
            yield PackageManager.PIP_END.bind(returncode=msg.returncode)
        elif msg.is_output():
            yield PackageManager.PIP_MSG.bind(msg=msg.text)

#
#
#
def _read_pip_dist_info(directory, pkg_name):
    """ pipがdist-infoフォルダに収めたパッケージの情報を読みとる """
    pkg_name = canonicalize_package_name(pkg_name)
    infodir = None
    for d in os.listdir(directory):
        if d.endswith(".dist-info"):
            p = os.path.join(directory, d, "METADATA")
        elif d.endswith(".egg-info"):
            p = os.path.join(directory, d, "PKG-INFO")
        else:
            continue
        
        if not os.path.isfile(p):
            continue
        
        namedata = None
        for l in _readfilelines(p):
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
    
    p = os.path.join(directory, infodir, "top_level.txt")
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

#
def _read_private_requirements(localdir):
    lines = []
    if localdir:
        reqs = os.path.join(localdir, "PRIVATE-REQUIREMENTS.txt")
        if os.path.isfile(reqs):
            lines = [l for l in _readfilelines(reqs)]
    return lines

#
def _readfilelines(p):
    with open(p, "r", encoding="utf-8") as fi:
        for l in fi:
            yield l



import os
import shutil
import sys
import subprocess
import tempfile
import configparser
import re
import importlib
from typing import Dict, Any, Union, List, Optional

from machaon.milestone import milestone, milestone_msg
from machaon.command import describe_command_package, describe_command, CommandPackage
from machaon.package.repository import RepositoryURLError

#
class DatabaseNotLoadedError(Exception):
    pass

#
#
#
class _internal_entrypoint:
    def __init__(self):
        self.pkg = None
    
    def describe(self, *args, **kwargs):
        self.pkg = describe_command_package(*args, **kwargs)
        return self.pkg

    def command(self, *args, **kwargs):
        return describe_command(*args, **kwargs)

    def get(self):
        return self.pkg

#
#
#
class package():
    COMMANDSET_MODULE = 1
    DEPENDENCY_MODULE = 2
    DATASTORE = 3

    def __init__(self, source, name=None, entrypoint=None, std=False, hashval=None, dependency=False, datastore=False):
        if not name:
            name = source.name
        self.name = name
        self.source = source
        self.separate = not std
        
        self._type = package.COMMANDSET_MODULE
        if dependency:
            self._type = package.DEPENDENCY_MODULE
        if datastore:
            self._type = package.DATASTORE

        # エントリポイントとなるモジュールを探す
        if self._type == package.COMMANDSET_MODULE:
            if not entrypoint:
                entrypoint = name
            entrypoint += ".__commands__"
            self.entrymodule = entrypoint
        else:
            self.entrymodule = None

        self._icmdset = None
        self._hash = hashval
    
    @property
    def dist_package_name(self):
        return self.source.name
    
    def get_source_signature(self) -> str:
        return self.source.get_source()
    
    def get_repository(self):
        return self.source

    def is_installation_separated(self) -> bool:
        return self.separate
    
    def load_hash(self) -> Optional[str]:
        if self._hash is None:
            try:
                _hash = self.source.query_hash()
            except RepositoryURLError:
                _hash = None 
            self._hash = "" if _hash is None else _hash
        return self._hash

    def is_commandset(self) -> bool:
        return self._type == package.COMMANDSET_MODULE
    
    def attach_commandset(self, index):
        if self._type != package.COMMANDSET_MODULE:
            raise ValueError("Not a commandset module package")
        if self._icmdset is not None:
            raise ValueError("Commandset has been attached already")
        self._icmdset = index
    
    def get_attached_commandset(self) -> Optional[int]:
        return self._icmdset
    
    def is_installed_module(self) -> bool:
        if self._type == package.DATASTORE:
            return False
        # 親モジュールから順に確認する
        mparts = self.entrymodule.split(".")
        for i in range(len(mparts)):
            mp = ".".join(mparts[0:i+1])
            spec = importlib.util.find_spec(mp)
            if spec is None:
                return False
        return True

    def load_command_builder(self) -> CommandPackage:
        spec = importlib.util.find_spec(self.entrymodule)
        if spec is None:
            raise ModuleNotFoundError(self.entrymodule)
        mod = importlib.util.module_from_spec(spec)
        entrypoint = _internal_entrypoint()
        setattr(mod, "commands", entrypoint)

        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            raise PackageEntryLoadError(e)
        
        return entrypoint.get()
    
#
class PackageEntryLoadError(Exception):
    def get_basic(self):
        return super().args[0]

#
#
#
class package_manager():    
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
        self.database = None
        self._dbpath = os.path.join(directory, database)
    
    def load_database(self, force=False):
        if not force and self.database is not None:
            return

        if not os.path.isfile(self._dbpath):
            self.database = configparser.ConfigParser()
            self.save_database()
            
        cfg = None
        with open(self._dbpath, "r", encoding="utf-8") as fi:
            cfg = configparser.ConfigParser()
            cfg.read_file(fi)

        self.database = cfg
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
        with open(self._dbpath, "w", encoding="utf-8") as fo:
            self.database.write(fo)
    
    def check_database(self):
        if self.database is None:
            raise DatabaseNotLoadedError()
             
    def is_installed(self, pkg_name: str):
        self.check_database()
        if not isinstance(pkg_name, str):
            raise TypeError("pkg_name")
        return pkg_name in self.database
                
    #
    def install(self, pkg: package, newinstall: bool):
        rep = pkg.get_repository()

        tmpdir = ''
        def cleanup_tmpdir(d):
            shutil.rmtree(d)
            return ''

        if rep.is_remote:
            # ダウンロードする
            if not tmpdir: tmpdir = tempfile.mkdtemp()
            try:
                total = rep.query_download_size()
                yield package_manager.DOWNLOAD_START.bind(total=total)

                arcfilepath = rep.get_arcfilepath(tmpdir)
                for size in rep.download_iter(arcfilepath):
                    yield package_manager.DOWNLOADING.bind(size=size, total=total)
                    
                yield package_manager.DOWNLOAD_END.bind(total=total)

            except RepositoryURLError as e:
                yield package_manager.DOWNLOAD_ERROR.bind(error=e.get_basic())
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
        yield package_manager.PIP_INSTALLING
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
                        yield package_manager.PRIVATE_REQUIREMENTS.bind(names=private_reqs)
                
                # pipが作成したデータを見に行く
                distinfo: Dict[str, str] = {}
                if pkg.is_installation_separated():
                    distinfo = _read_pip_dist_info(self.dir, pkg.dist_package_name)
            
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
            yield package_manager.UNINSTALLING
            toplevel = self.database[pkg.name]["toplevel"]
            shutil.rmtree(os.path.join(self.dir, toplevel))
            infodir = self.database[pkg.name]["infodir"]
            shutil.rmtree(os.path.join(self.dir, infodir))
        else:
            # pipにアンインストールさせる
            yield package_manager.PIP_UNINSTALLING
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

    from machaon.commands.shell import popen_capture_output, PopenEnd
    proc = popen_capture_output(cmd)
    for line in proc:
        if isinstance(line, PopenEnd):
            yield package_manager.PIP_END.bind(returncode=line.returncode)
        elif line:
            yield package_manager.PIP_MSG.bind(msg=line)
        

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



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
from machaon.command import describe_command_package, describe_command
from machaon.package.repository import rep_archive

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
    def __init__(self, source, name=None, package=None, entrypoint=None, separate=True, hashval=None):
        if not name:
            name = source.name
        self.name = name
        self.source = source
        self.separate = separate

        # エントリポイントとなるモジュールを探す
        if not package and not entrypoint:
            package = name
        if package and not entrypoint:
            entrypoint = package + ".__commands__"
        self.entrymodule = entrypoint 

        self._hash = hashval
    
    @property
    def dist_package_name(self):
        return self.source.name
    
    def get_host(self) -> str:
        return self.source.get_host()

    def get_id(self) -> str:
        return self.source.get_id()
        
    def get_signature(self) -> str:
        return "{}/{}:{}".format(self.source.get_host(), self.source.get_id(), self._hash)
    
    def get_repository(self):
        return self.source

    def is_installation_separated(self):
        return self.separate
    
    def load_hash(self) -> str:
        if self._hash is None:
            self._hash = self.source.query_hash()
        return self._hash
    
    def is_installed_module(self):
        # 親モジュールから順に確認する
        mparts = self.entrymodule.split(".")
        for i in range(len(mparts)):
            mp = ".".join(mparts[0:i+1])
            spec = importlib.util.find_spec(mp)
            if spec is None:
                return False
        return True

    def load_command_builder(self):
        spec = importlib.util.find_spec(self.entrymodule)
        mod = importlib.util.module_from_spec(spec)
        
        entrypoint = _internal_entrypoint()
        setattr(mod, "commands", entrypoint)

        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            raise e
        
        return entrypoint.get()
    
#
#
#
class package_manager():    
    ALREADY_INSTALLED = milestone()
    DOWNLOAD_START = milestone_msg("total")
    DOWNLOADING = milestone_msg("size")
    DOWNLOAD_END = milestone_msg("total")
    EXTRACTED_FILES = milestone_msg("path")
    PRIVATE_REQUIREMENTS = milestone_msg("names")
    NOT_INSTALLED = milestone()
    UNINSTALLING = milestone()
    PIP_INSTALLING = milestone()
    PIP_UNINSTALLING = milestone()
    PIP_MSG = milestone_msg("msg")

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
        
        self.database.set(pkg.name, "host", pkg.get_host())
        self.database.set(pkg.name, "id", pkg.get_id())
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
                
    def download_repository(self, rep, directory):
        total = rep.query_download_size()
        yield package_manager.DOWNLOAD_START.bind(total=total)

        for size in rep.download_iter(directory):
            yield package_manager.DOWNLOADING.bind(size=size, total=total)
            
        yield package_manager.DOWNLOAD_END.bind(total=total)
        
        # 解凍する
        with rep.open_archive(directory):
            rep.extract(directory)
        path = os.path.join(directory, rep.get_member_root())
        yield package_manager.EXTRACTED_FILES.bind(path=path)
    
    def is_installed(self, pkg_name):
        self.check_database()
        return pkg_name in self.database
                
    def install(self, pkg: package):
        if self.is_installed(pkg.name):
            yield package_manager.ALREADY_INSTALLED
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            # ローカルに展開する
            localdir = None
            rep = pkg.get_repository()
            if rep:
                for stat in self.download_repository(rep, tmpdir):
                    if stat == package_manager.EXTRACTED_FILES:
                        localdir = stat.path
                    yield stat
            
            # pipにインストールさせる
            yield package_manager.PIP_INSTALLING
            yield from _run_pip(
                installtarget=localdir, 
                installdir=self.dir if pkg.is_installation_separated() else None
            )
            
            # 非公開の依存パッケージを表示
            private_reqs = _read_private_requirements(localdir)
            if private_reqs:
                yield package_manager.PRIVATE_REQUIREMENTS.bind(names=private_reqs)
            
        # pipが作成したデータを見に行く
        distinfo: Dict[str, str] = {}
        if pkg.is_installation_separated():
            distinfo = _read_pip_dist_info(self.dir, pkg.dist_package_name)
        
        # データベースに書き込む
        self.add_database(pkg, **distinfo)
        
    def uninstall(self, pkg):
        if not self.is_installed(pkg.name):
            yield package_manager.NOT_INSTALLED
            return
        
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
                uninstalltarget=pkg.name
            )
            
        self.remove_database(pkg.name)
            
    def to_be_updated(self, pkg):
        if not self.is_installed(pkg.name):
            return True
        # hashを比較して変更を検知する
        entry = self.database[pkg.name]
        hash_ = pkg.load_hash()
        if entry["hash"] != hash_:
            return True
        return False
    
    def update(self, pkg):
        self.check_database()
        if pkg.name not in self.database:
            yield package_manager.NOT_INSTALLED
            return
            
        separate = self.database.getboolean(pkg.name, "separate", fallback=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            # レポジトリを展開
            localdir = None
            rep = pkg.get_repository()
            if rep:
                for stat in self.download_repository(rep, tmpdir):
                    if stat == package_manager.EXTRACTED_FILES:
                        localdir = stat.path
                    yield stat

            # pipにインストールさせる
            yield package_manager.PIP_INSTALLING
            yield from _run_pip(
                installtarget=localdir, 
                installdir=self.dir if separate else None,
                options=["--upgrade"]
            )
        
        self.add_database(pkg)
    
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

    from machaon.commands.shell import popen_capture_output
    proc = popen_capture_output(cmd)
    for line in proc:
        if line:
            yield package_manager.PIP_MSG.bind(msg=line)
        

#
#
#
def _read_pip_dist_info(directory, pkg_name):
    """ pipがdist-infoフォルダに収めたパッケージの情報を読みとる """
    distinfo = {}
    infodir = None
    infodirname = re.compile(r"{}-([\d\.]+)\.dist-info".format(pkg_name))
    for d in os.listdir(directory):
        if infodirname.match(d):
            infodir = d
            break
    else:
        raise ValueError("pip dist-info not found")
    
    distinfo["infodir"] = infodir
    
    p = os.path.join(directory, infodir, "top_level.txt")
    with open(p, "r", encoding="utf-8") as fi:
        distinfo["toplevel"] = fi.read().strip()
    
    return distinfo

#
def _read_private_requirements(localdir):
    if localdir:
        reqs = os.path.join(localdir, "PRIVATE-REQUIREMENTS")
        if os.path.isfile(reqs):
            lines = []
            with open(reqs, "r", encoding="utf-8") as reqsf:
                for line in reqsf:
                    lines.append(line)
            return lines
    return None


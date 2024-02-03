import pytest
import sys
import os
import configparser
from machaon.app import AppRoot
from machaon.core.context import instant_context
from machaon.ui.tk import tkLauncher
from machaon.types.shell import Path
from machaon.types.app import RootObject
from machaon.types.package import AppPackageType

from machaon.package.package import Package, create_package
#from machaon.package.repository import bitbucket_rep
#from machaon.package.auth import basic_auth
#from machaon.package.archive import local_archive
#from machaon.engine import NotYetInstalledCommandSet
#from machaon.process import TempSpirit
#from machaon.commands.package import package_install, command_package

@pytest.fixture
def approot(tmpdir):
    macadir = Path(tmpdir.join("machaon"))
    app = AppRoot()
    app.initialize(ui=None, basic_dir=macadir, ignore_args=True)
    return app

def write_package_defs(root, defname, pkgdef):
    pkgconfig = root.get_basic_dir().makedirs() / "{}.packages".format(defname)
    cfg = configparser.ConfigParser()
    cfg.read_dict(pkgdef)
    with open(pkgconfig, "w", encoding="utf-8") as fo:
        cfg.write(fo)

    
def test_load_singlemodule_fundamental(approot):
    root: AppRoot = approot
    root.get_type_module().use_module_or_package_types("machaon.types.shell")

    tm = root.get_type_module()
    assert tm.get("Path")
    assert tm.get("Path").get_describer_qualname() == "machaon.types.shell.Path"
    
    assert tm.get("PathDialog")
    assert tm.get("PathDialog").get_describer_qualname() == "machaon.types.shell.PathDialog"


def test_load_submodules_types(approot):
    root: AppRoot = approot
    root.get_type_module().use_module_or_package_types("machaon.types")

    tm = root.get_type_module()

    assert tm.get("RootObject") is not None
    assert tm.get("RootObject").get_describer_qualname() == "machaon.types.app.RootObject"

    assert tm.get("Path") is not None
    assert tm.get("Path").get_describer_qualname() == "machaon.types.shell.Path"


def test_update_machaon(approot):
    root: AppRoot = approot
    root.boot_core()

    macadir = root.get_package_dir() / "macacore"
    assert not (macadir / "machaon").isdir()
    spi = root.temp_spirit()
    cxt = instant_context(root=root)
    RootObject(cxt).machaon_update(spi, forceupdate=True, location=macadir)
    spi.printout()

    assert (macadir / "machaon").isdir()


def test_defined_package(approot):
    root: AppRoot = approot
    write_package_defs(root, "test", {
        "hello": {
            "repository": "bitbucket:betasewer/test_module",
            "module": "hello"
        }
    })

    root.boot_core()

    pkgm = root.package_manager()
    pkg: Package = pkgm.get("hello:test")
    assert pkg
    assert pkg.name == "hello:test"
    assert pkg.is_remote_source()
    assert pkg.get_source_signature() == "bitbucket.org:betasewer/test_module:master"
    assert not pkg.is_ready()
    assert not pkgm.is_installed(pkg)
    assert pkgm.query_update_status(pkg) == "notfound"

    assert pkg.get_initial_module().get_name() == "hello"

    spi = root.temp_spirit(doprint=True)
    AppPackageType().display_update(pkg, spi, forceinstall=True)

    assert pkg.is_ready()
    assert pkgm.is_installed(pkg)    
    assert pkgm.query_update_status(pkg) == "latest"


def test_defined_package_update(approot):
    # パッケージを新規導入する
    root: AppRoot = approot
    write_package_defs(root, "test", {
        "hello-ageha": {
            "repository": "github:betasewer/ageha+9dd7f3c2ba9d3d4cf544baa3b4a89a70255c2acc",
            "module": "ageha"
        }
    })

    root.boot_core()

    pkgm = root.package_manager()
    pkg: Package = pkgm.get("hello-ageha:test")
    
    assert pkg.get_source_signature() == "github.com:betasewer/ageha:master"
    assert pkg.get_target_hash() == "9dd7f3c2ba9d3d4cf544baa3b4a89a70255c2acc"

    # 初回の新規インストール
    spi = root.temp_spirit(doprint=True)
    AppPackageType().display_update(pkg, spi, forceinstall=True)

    assert pkg.is_ready()
    assert pkgm.is_installed(pkg)    
    assert pkgm.get_installed_hash(pkg) == "9dd7f3c2ba9d3d4cf544baa3b4a89a70255c2acc"
    assert pkgm.query_update_status(pkg) == "old"

    assert pkgm.database.has_option("hello-ageha:test", "hash")
    assert pkgm.database.get("hello-ageha:test", "hash") == "9dd7f3c2ba9d3d4cf544baa3b4a89a70255c2acc"

    # 更新する
    AppPackageType().display_update(pkg, spi, forceupdate=True)

    assert pkg.is_ready()
    assert pkg.get_target_hash() == "9dd7f3c2ba9d3d4cf544baa3b4a89a70255c2acc"
    assert pkgm.is_installed(pkg)
    nowhash =  pkgm.get_installed_hash(pkg)
    assert nowhash and len(nowhash) > 0
    assert nowhash != "9dd7f3c2ba9d3d4cf544baa3b4a89a70255c2acc"
    assert pkgm.query_update_status(pkg) == "latest"

    assert pkgm.database.has_option("hello-ageha:test", "hash")
    assert pkgm.database.get("hello-ageha:test", "hash") == nowhash
    assert pkgm.database.get("hello-ageha:test", "toplevel") == "ageha"


@pytest.mark.skip
def test_no_dep_package(approot: AppRoot):
    write_package_defs(approot, "test", {
        "docxx": {
            "repository": "github:betasewer/python-docx-xtended",
            "module": "docxx"
        }
    })
    approot.add_package_option("docxx:test", no_dependency=True)
    
    approot.boot_core()

    pkgm = approot.package_manager()
    pkg: Package = pkgm.get("docxx:test")
    assert pkg
    
    spi = approot.temp_spirit(doprint=True)
    AppPackageType().display_update(pkg, spi, forceupdate=True)




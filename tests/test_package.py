import pytest
import sys
import os
from machaon.app import AppRoot
from machaon.ui.tk import tkLauncher

from machaon.package.package import Package, create_package
#from machaon.package.repository import bitbucket_rep
#from machaon.package.auth import basic_auth
#from machaon.package.archive import local_archive
#from machaon.engine import NotYetInstalledCommandSet
#from machaon.process import TempSpirit
#from machaon.commands.package import package_install, command_package

def pkgdir():
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "sample\\pkg"))

def approot():
    app = AppRoot()
    app.initialize(ui=None, package_dir=pkgdir())
    return app
    
def test_load_singlemodule_fundamental():
    root = approot()
    pkg = create_package("fundamentals", "module:machaon.types.shell")

    assert not pkg.once_loaded()
    assert not pkg.is_load_succeeded()
    assert not pkg.is_load_failed()
    assert len(pkg.get_load_errors()) == 0

    root.load_pkg(pkg)

    assert pkg.once_loaded()
    if pkg.is_load_failed(): raise pkg.get_load_errors()[0]
    assert pkg.is_load_succeeded()
    assert len(pkg.get_load_errors()) == 0
    
    tm = root.get_type_module()
    assert tm.get("Path")
    assert tm.get("Path").get_describer_qualname() == "machaon.types.shell.Path"
    
    assert tm.get("PathDialog")
    assert tm.get("PathDialog").get_describer_qualname() == "machaon.types.shell.PathDialog"


def test_load_submodules_types():
    root = approot()
    pkg = create_package("types", "package:machaon.types", scope="ion")

    assert not pkg.once_loaded()
    assert not pkg.is_load_succeeded()
    assert not pkg.is_load_failed()
    assert len(pkg.get_load_errors()) == 0

    root.load_pkg(pkg)

    assert pkg.once_loaded()
    if pkg.is_load_failed(): raise pkg.get_load_errors()[0]
    assert pkg.is_load_succeeded()
    assert len(pkg.get_load_errors()) == 0

    tm = root.get_type_module()

    assert tm.get("RootObject", scope="ion") is not None
    assert tm.get("RootObject", scope="ion").get_describer_qualname() == "machaon.types.app.RootObject"

    assert tm.get("Path", scope="ion") is not None
    assert tm.get("Path", scope="ion").get_describer_qualname() == "machaon.types.shell.Path"


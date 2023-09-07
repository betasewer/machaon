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
    app.initialize(ui=None, package_dir=pkgdir(), ignore_args=True)
    return app
    
def test_load_singlemodule_fundamental():
    root = approot()
    root.get_type_module().use_module_or_package_types("machaon.types.shell")

    tm = root.get_type_module()
    assert tm.get("Path")
    assert tm.get("Path").get_describer_qualname() == "machaon.types.shell.Path"
    
    assert tm.get("PathDialog")
    assert tm.get("PathDialog").get_describer_qualname() == "machaon.types.shell.PathDialog"


def test_load_submodules_types():
    root = approot()
    root.get_type_module().use_module_or_package_types("machaon.types")

    tm = root.get_type_module()

    assert tm.get("RootObject") is not None
    assert tm.get("RootObject").get_describer_qualname() == "machaon.types.app.RootObject"

    assert tm.get("Path") is not None
    assert tm.get("Path").get_describer_qualname() == "machaon.types.shell.Path"


import pytest
import sys
import os
from machaon.app import AppRoot
from machaon.ui.tk import tkLauncher
from machaon.types.shell import Path
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

    pkg = root.package_manager()
    pkg.update_core()

    macadir = root.get_package_dir() / "macacore"
    assert not (macadir / "machaon").isdir()
    spi = root.temp_spirit()
    AppPackageType().display_download_and_install(
        spi, 
        pkg.get_core_package(), 
        lambda *args: pkg.update_core(location=macadir.makedirs())
    )
    spi.printout()
    assert (macadir / "machaon").isdir()

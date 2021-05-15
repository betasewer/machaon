import pytest
import sys
from machaon.app import AppRoot
from machaon.ui.tk import tkLauncher

#from machaon.commands.catalogue import shell_commands
from machaon.package.package import Package, create_package
#from machaon.package.repository import bitbucket_rep
#from machaon.package.auth import basic_auth
#from machaon.package.archive import local_archive
#from machaon.engine import NotYetInstalledCommandSet
#from machaon.process import TempSpirit
#from machaon.commands.package import package_install, command_package

def approot():
    app = AppRoot()
    wnd = tkLauncher("test")
    app.initialize(ui=wnd, package_dir="C:\\codes\\python\\machaon\\tests\\sample\\pkg")
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
    
    import machaon.types.shell as shell

    tm = root.get_type_module()
    assert tm.get("Path")
    assert tm.get("Path").get_describer() is shell.Path
    
    assert tm.get("PathDialog")
    assert tm.get("PathDialog").get_describer() is shell.PathDialog

test_load_singlemodule_fundamental()

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

    #
    tm = root.get_type_module()

    import machaon.types.app
    assert tm.get("AppTestObject", scope="ion")
    assert tm.get("AppTestObject", scope="ion").get_describer() is machaon.types.app.AppTestObject

    import machaon.types.shell
    assert tm.get("Path", scope="ion")
    assert tm.get("Path", scope="ion").get_describer() is machaon.types.shell.Path
    

@pytest.mark.skip()
def test_package_setup(approot):
    pkg = approot.add_package(
        "test",
        "bitbucket:betasewer/test_module",
        module="hello"
    )
    
    approot.update_package(pkg)
    assert approot.cmdengine.commandsets[0].match("test.helloworld")
    spi.printout()

    command_package(spi, "remove", False, 0)
    assert isinstance(approot.cmdengine.commandsets[0], NotYetInstalledCommandSet)
    assert not approot.cmdengine.commandsets[0].match("test.helloworld")
    spi.printout()

    command_package(spi, "update", False, 0)
    assert approot.cmdengine.commandsets[0].match("test.helloworld")
    spi.printout()

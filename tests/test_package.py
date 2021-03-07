import pytest
from machaon.app import AppRoot
from machaon.ui.tk import tkLauncher

#from machaon.commands.catalogue import shell_commands
#from machaon.package.package import package
#from machaon.package.repository import bitbucket_rep
#from machaon.package.auth import basic_auth
#from machaon.package.archive import local_archive
#from machaon.engine import NotYetInstalledCommandSet
#from machaon.process import TempSpirit
#from machaon.commands.package import package_install, command_package

@pytest.fixture
def approot():
    app = AppRoot()
    wnd = tkLauncher("test")
    app.initialize(ui=wnd, directory="C:\\codes\\python\\machaon\\tests\\sample\\pkg")
    return app

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

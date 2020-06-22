import pytest
from machaon.app import AppRoot
from machaon.ui.tk import tkLauncher

from machaon.commands.catalogue import shell_commands
from machaon.package.package import package
from machaon.package.repository import bitbucket_rep
from machaon.package.auth import basic_auth
from machaon.package.archive import local_archive
from machaon.engine import NotYetInstalledCommandSet
from machaon.process import TempSpirit
from machaon.commands.package import package_install, command_package

@pytest.fixture
def approot():
    app = AppRoot()
    wnd = tkLauncher("test")
    app.initialize(ui=wnd, directory="C:\\codes\\python\\machaon\\tests\\sample\\pkg")
    return app

def test_cmdset_setup(approot):
    approot.setup_package(("shell",), shell_commands())
    assert len(approot.cmdengine.commandsets) == 1
    assert approot.cmdengine.commandsets[0].get_prefixes() == ("shell",)
    assert len(approot.cmdengine.commandsets[0].match("shell.ls")) == 1

def test_package_setup(approot):
    approot.setup_package(("test",), 
        package(
            source=local_archive("C:\\codes\\python\\machaon\\tests\\sample\\pkg\\betasewer-test_module.zip", name="test_module"), 
            #source=bitbucket_rep("betasewer/test_module"), 
            entrypoint="hello"
        )
    )
    assert len(approot.cmdengine.commandsets) == 1
    #assert isinstance(approot.cmdengine.commandsets[0], NotYetInstalledCommandSet)
    
    spi = TempSpirit(approot)
    command_package(spi, "update", False, 0)
    assert approot.cmdengine.commandsets[0].match("test.helloworld")
    spi.printout()

    command_package(spi, "remove", False, 0)
    assert isinstance(approot.cmdengine.commandsets[0], NotYetInstalledCommandSet)
    assert not approot.cmdengine.commandsets[0].match("test.helloworld")
    spi.printout()

    command_package(spi, "update", False, 0)
    assert approot.cmdengine.commandsets[0].match("test.helloworld")
    spi.printout()

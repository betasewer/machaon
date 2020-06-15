from machaon.app import AppRoot
from machaon.platforms import current
from machaon.command import CommandPackage
from machaon.package.package import package

#
#
#
class Starter():
    def __init__(self, ui, directory):
        self.root = AppRoot()
        self.root.set_current_dir_desktop()
        self.root.initialize(ui=ui, directory=directory)

    def set_cd(self, path):
        self.root.set_current_dir(path)
    
    def commandset(self, prefixes_or_package, cmdpackage=None, **packagekwargs):
        if isinstance(prefixes_or_package, tuple):
            raise TypeError("prefix must be a space-separated string, not tuple")
        elif isinstance(prefixes_or_package, (CommandPackage,package)):
            pkg = prefixes_or_package
            prefixes = ()
        elif isinstance(cmdpackage, CommandPackage):
            pkg = cmdpackage
            prefixes = prefixes_or_package.split()
        else:
            if "package_name" in packagekwargs:
                packagekwargs["name"] = packagekwargs["package_name"]
            pkg = package(**packagekwargs)
            prefixes = prefixes_or_package.split()
        
        self.root.setup_package(prefixes, pkg)

    def go(self):
        return self.root.run()

#
#
#
class ShellStarter(Starter):
    def __init__(self, directory):
        ui = current.shell_ui()
        super().__init__(ui, directory)
    
    def system_commandset(self):
        from machaon.commands.catalogue import app_commands
        self.commandset(app_commands().exclude("interrupt", "theme"))

#
#
#
class TkStarter(Starter):
    def __init__(self, *, title, geometry, directory):
        from machaon.ui.tk import tkLauncher
        ui = tkLauncher(title, geometry)
        super().__init__(ui, directory)
    
    def system_commandset(self):
        from machaon.commands.catalogue import app_commands
        self.commandset(app_commands().exclude("interrupt"))


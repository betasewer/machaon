from machaon.app import AppRoot
from machaon.platforms import current


class Starter():
    def __init__(self):
        self.root = AppRoot()
        self.root.set_current_dir_desktop()
        self.sources = []

    def set_cd(self, path):
        self.root.set_current_dir(path)
    
    def install_commands(self, prefixes, package, *, pip_install=None, **kwargs):
        source = None
        if pip_install:
            prefix = prefixes[0]
            source = (prefix, "pip", pip_install)
        if source is not None:
            self.sources.append(source)
        self.root.install_commands(prefixes, package, **kwargs)

    def go(self):
        return self.root.run()

#
#
#
class ShellStarter(Starter):
    def __init__(self):
        super().__init__()
        ui = current.shell_ui()
        self.root.initialize(ui=ui)
    
    def install_syscommands(self):
        from machaon.commands.catalogue import app_commands
        self.install_commands("", app_commands().excluded("interrupt"))

#
#
#
class TkStarter(Starter):
    def __init__(self, *, title, geometry):
        super().__init__()
        from machaon.ui.tk import tkLauncher
        ui = tkLauncher(title, geometry)
        self.root.initialize(ui=ui)
    
    def install_syscommands(self):
        from machaon.commands.catalogue import app_commands
        pkg = app_commands().excluded("interrupt")
        self.install_commands("", pkg)


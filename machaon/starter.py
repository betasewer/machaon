from machaon.app import AppRoot
from machaon.platforms import current


class Starter():
    def __init__(self):
        self.app = AppRoot()
        self.app.set_current_dir_desktop()
        self.sources = []

    def set_cd(self, path):
        self.app.change_current_dir(path)
    
    def install_commands(self, prefixes, package, *, pip_install=None, **kwargs):
        source = None
        if pip_install:
            prefix = prefixes[0]
            source = (prefix, "pip", pip_install)
        if source is not None:
            self.sources.append(source)
        self.app.install_commands(prefixes, package, **kwargs)

    def go(self):
        return self.app.run()

#
#
#
class ShellStarter(Starter):
    def __init__(self):
        super().__init__()
        ui = current.shell_ui()
        self.app.init_ui(ui)
    
    def install_syscommands(self):
        from machaon.commands.app import app_commands
        self.install_commands("", app_commands().excluded("interrupt"))

#
#
#
class TkStarter(Starter):
    def __init__(self, *, title, geometry):
        super().__init__()
        from machaon.ui.tk import tkLauncherUI
        ui = tkLauncherUI(title, geometry)
        self.app.init_ui(ui)
    
    def install_syscommands(self):
        from machaon.commands.app import app_commands
        from machaon.ui.tk import ui_commands, ui_sys_commands
        pkg = app_commands().excluded("interrupt","cls","exit").annex(ui_commands(), ui_sys_commands())
        self.install_commands("", pkg)


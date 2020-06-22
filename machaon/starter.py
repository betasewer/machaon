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
    
    # コマンドを提供するパッケージをインストール
    #  commandset(source=..., entrypoint=..., std=...)
    #  commandset("prefixes...", source=..., entrypoint=..., std=...)
    #  commandset(package(source=...))
    #  commandset("prefixes...", package(source=...))
    #  commandset(app.commands.catalogue.shell_commands())
    #  commandset("prefixes...", app.commands.catalogue.shell_commands())
    def commandset(self, prefixes_or_package=None, cmdpackage=None, **packagekwargs):
        if isinstance(prefixes_or_package, tuple):
            raise TypeError("prefix must be a space-separated string, not tuple")
        elif isinstance(prefixes_or_package, (CommandPackage,package)):
            pkg = prefixes_or_package
            prefixes = ()
        elif isinstance(cmdpackage, (CommandPackage,package)):
            pkg = cmdpackage
            prefixes = prefixes_or_package.split()
        else:
            if "package_name" in packagekwargs:
                packagekwargs["name"] = packagekwargs["package_name"]
            pkg = package(**packagekwargs)
            if prefixes_or_package is None:
                prefixes = ()
            else:   
                prefixes = prefixes_or_package.split()
        
        self.root.setup_package(prefixes, pkg)
    
    # インストール済みパッケージのコマンドエントリをこの場で読み込む
    def commandset_entry(self, package_name, entrypoint=None):
        tmppkg = package(source=None, name=package_name, entrypoint=entrypoint)
        if not tmppkg.is_installed_module():
            raise ValueError("指定のモジュールはインストールされていません")
        return tmppkg.load_command_builder()
    
    # コマンドを提供しない、依存のみのパッケージをインストール
    def dependency(self, pkg=None, **packagekwargs):
        if pkg is None:
            pkg = package(**packagekwargs)
        pkg._type = package.DEPENDENCY_MODULE
        self.root.setup_dependency_package(pkg)

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


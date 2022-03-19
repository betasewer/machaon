import importlib.util

def has_tk():
    tk = importlib.util.find_spec("tkinter")
    return tk is not None

def new_launcher(ui=None, **args):
    if isinstance(ui, str):
        if ui == "tk":
            if not has_tk():
                raise ValueError("TkがシステムのPythonにインストールされていません")
            return tk_launcher(args)
        elif ui == "shell":
            return shell_launcher(args)
        else:
            raise ValueError("不明なUIタイプです: "+ui)
        
    elif ui is None:
        # GUIを試し、だめならshell
        if has_tk():
            return tk_launcher(args)
        else:
            return shell_launcher(args)
    

def tk_launcher(args):
    from machaon.ui.tk import tkLauncher
    return tkLauncher(args)

def shell_launcher(args):
    from machaon.platforms import is_windows, is_osx
    if is_windows():
        from machaon.ui.shell import WinCmdShell
        return WinCmdShell(args)
    else:
        from machaon.ui.shell import GenericShell
        return GenericShell(args)



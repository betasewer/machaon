import importlib.util

ui_names = (
    "tk",
    "shell",
    "batch", "headless",
    "async-batch", "async-headless",
)


def new_launcher(ui=None, **args):
    if isinstance(ui, str):
        if ui == "tk":
            if not has_tk():
                raise ValueError("TkがシステムのPythonにインストールされていません")
            return tk_launcher(args)
        elif ui == "shell":
            return shell_launcher(args)
        elif ui == "batch":
            return batch_launcher(args)
        elif ui == "async-batch":
            return async_batch_launcher(args)
        elif ui == "headless":
            return passive_launcher(args)
        else:
            raise ValueError("不明なUIタイプです: "+ui)
        
    elif ui is None:
        # GUIを試し、だめならshell
        if has_tk():
            return tk_launcher(args)
        else:
            return shell_launcher(args)
        
    return ui
    
def has_tk():
    tk = importlib.util.find_spec("tkinter")
    return tk is not None

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

def batch_launcher(args):
    from machaon.ui.headless import BatchLauncher
    args["shell"] = shell_launcher(args)
    return BatchLauncher(args)

def async_batch_launcher(args):
    from machaon.ui.headless import AsyncBatchLauncher
    args["shell"] = shell_launcher(args)
    return AsyncBatchLauncher(args)

def passive_launcher(args):
    from machaon.ui.headless import PassiveLauncher
    args["shell"] = shell_launcher(args)
    return PassiveLauncher(args)


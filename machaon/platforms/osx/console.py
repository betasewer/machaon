
preferred_fontname = "Menlo"
preferred_fontsize = 14    

default_encoding = "shift-jis"

def shell_ui():
    from machaon.ui.shell import ShellUI
    return ShellUI("utf-8")

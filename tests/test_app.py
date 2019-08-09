from machaon.shell import ShellApp, WinShellUI

def test_shellapp_load(tmpdir):
    app = BasicShellApp("APPTITLE", WinShellUI())
    assert app.title == "APPTITLE"
    assert isinstance(app.ui, WinShellUI)
    assert app.launcher is not None
    #
    d = tmpdir.mkdir("basedir")
    app.change_current_dir(str(d))
    assert app.get_current_dir() == str(d)
    assert app.abspath("c:\\moge") == "c:\\moge"
    th = d.join("thunder.wav")
    assert app.abspath("thunder.wav") == str(th)
    
    
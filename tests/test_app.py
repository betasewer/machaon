from machaon.app import AppRoot
from machaon.process import Spirit

def test_spirit_currentdir(tmpdir):
    app = AppRoot()
    assert app.ui is None
    assert app.processhive is None

    # current directory
    assert not app.curdir
    spi = Spirit(app)
    d = tmpdir.mkdir("basedir")
    spi.change_current_dir(str(d))
    assert spi.get_current_dir() == str(d)
    assert spi.abspath("c:\\moge") == "c:\\moge"
    th = d.join("thunder.wav")
    assert spi.abspath("thunder.wav") == str(th)
    
    
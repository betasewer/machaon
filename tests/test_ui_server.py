
from machaon.app import create_app
from machaon.macatest import runmain

def test_batch_launcher(tmpdir):
    from machaon.types.shell import Path
    from machaon.types.file import TextFile

    logdir = tmpdir.mkdir("log")
    app = create_app(
        title="testrun", ui="batch", logdir=logdir, logfileperiod="monthly", ignore_args=True
        ).messages(
            "1 + 2",
            "1 to 30"
        ).end()
    app.run()

    p = Path(app.get_ui().get_logfile_path())
    assert p.isfile()

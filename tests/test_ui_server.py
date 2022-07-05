
from machaon.app import create_app


def test_batch_launcher(tmpdir):
    from machaon.types.shell import Path
    from machaon.types.file import TextFile

    logdir = tmpdir.mkdir("log")
    app = create_app(
        title="testrun", ui="batch", logdir=logdir, logfileperiod="monthly"
        ).packages(
        )["docxx"](
            "github:betasewer/python-docx-xtended:docxx"
        )["xlsxx"](
            "github:betasewer/python-xlsx-xtended:xlsxx"
        ).messages(
            "1 + 2",
            "2 / 0",
            "1 to 30"
        ).end()
    app.run()

    p = Path(app.get_ui().get_logfile_path())
    assert p.isfile()


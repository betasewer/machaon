import pytest

from machaon.app import AppRoot
from machaon.process import ProcessMessage, Spirit, TempSpirit, Process
from machaon.ui.tk import tkLauncher

def gettext(log):
    return log.get(1.0, "end")

lastlineindex = ("end linestart -2 lines", "end linestart -2 lines lineend")
def getlastline(log):
    return log.get(*lastlineindex)
def getlasttag(log):
    return log.tag_names(lastlineindex[0])


@pytest.fixture
def approot():
    app = AppRoot()
    app.initialize(ui="tk", title="test")
    app.boot_ui()
    return app

def test_message_window(approot):
    spi = Spirit(approot)
    wnd = approot.get_ui()

    assert "\n" == gettext(wnd.log)
    wnd.insert_screen_text("message", "test-message")
    assert "test-message\n\n" == gettext(wnd.log)
    assert "test-message" == getlastline(wnd.log)

    wnd.insert_screen_text("error", "test-error-message")
    assert "test-error-message" == getlastline(wnd.log)
    assert ("error",) == getlasttag(wnd.log)

    wnd.insert_screen_text("hyperlink", "test-hyperlink", link="www.hellowork.go.jp", linktag="message-em")
    assert "test-hyperlink" == getlastline(wnd.log)
    assert set(("message-em","clickable","hlink-1")) == set(getlasttag(wnd.log))

    #wnd.log.mark_set("CURRENT", "end")
    l1 = wnd.log.get("end linestart -2 lines", "end linestart -1 lines")
    l2 = wnd.log.get("end linestart -3 lines", "end linestart -2 lines")

    wnd.message_handler(ProcessMessage(tag="delete-message", line=-1, count=1))
    assert "test-error-message" == getlastline(wnd.log)
    
    #wnd.run_mainloop()


def test_textindex(approot):
    from machaon.ui.tk import TextIndex as textindex

    assert textindex("1.2").line == 1 and textindex("1.2").char == 2
    assert str(textindex("2.3")) == "2.3"
    assert str(textindex("10.2").move(char=5)) == "10.5"
    assert str(textindex("10.2").move(line=0, char=0)) == "0.0"
    assert str(textindex(line=3, char="end")) == "3.end"
    i = textindex("9.7")
    assert i.shifted(line=-1, char=1).string() == "8.8"
    assert i.string() == "9.7"
    assert textindex("1.0").compare(textindex("1.3")) == 1
    assert textindex("1.2").compare(textindex("2.3")) == 1
    assert textindex("2.3").compare(textindex("2.3")) == 0
    assert textindex("2.3").compare(textindex("1.2")) == -1

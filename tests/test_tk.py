import pytest

from machaon.app import AppRoot
from machaon.process import ProcessMessage, Spirit, DummySpirit, Process, ProcessTargetFunction
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
    wnd = tkLauncher("test")
    app.initialize(ui=wnd)
    return app

def test_message_window(approot):
    spi = Spirit(approot)
    wnd = approot.get_ui()

    assert "\n" == gettext(wnd.log)
    wnd.insert_screen_message(ProcessMessage("test-message"))
    assert "test-message\n\n" == gettext(wnd.log)
    assert "test-message" == getlastline(wnd.log)

    wnd.insert_screen_message(spi.error.msg("test-error-message"))
    assert "test-error-message" == getlastline(wnd.log)
    assert ("error",) == getlasttag(wnd.log)

    wnd.insert_screen_message(spi.hyperlink.msg("test-hyperlink", link="www.hellowork.go.jp", linktag="message_em"))
    assert "test-hyperlink" == getlastline(wnd.log)
    assert set(("message_em","clickable","hlink-1")) == set(getlasttag(wnd.log))

    #wnd.log.mark_set("CURRENT", "end")
    l1 = wnd.log.get("end linestart -2 lines", "end linestart -1 lines")
    l2 = wnd.log.get("end linestart -3 lines", "end linestart -2 lines")

    wnd.insert_screen_message(spi.delete_message.msg())
    assert "test-error-message" == getlastline(wnd.log)
    
    #wnd.run_mainloop()

def test_progress_display(approot):
    spi = DummySpirit(approot)
    wnd = approot.get_ui()

    import time
    from machaon.cui import MiniProgressDisplay
    dis = MiniProgressDisplay(spi)

    def display():
        for x in range(20):
            dis.update(50)
            #time.sleep(0.5)
    display()

    def dd():
        spi.printout()


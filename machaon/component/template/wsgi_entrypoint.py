
from machaon.app import AppRoot
from machaon.ui.server.server import InternalServer
from {entrymodule} import wsgi

root = AppRoot()
root.initialize(
    title={title!r}, ui="headless", 
    ignore_hotkeys=True, ignore_packages=True,
    basic_dir={dir!r}, 
    logfileperiod="monthly"
)
root.boot_core()

spi = root.temp_spirit(doprint=True)
svrapp = wsgi()
app = InternalServer(svrapp, spi)

#!/usr/bin/env python3
# coding: utf-8

def launch():
    from machaon.app import AppRoot
    from machaon.ui.tk import tkLauncher
    ui = tkLauncher("test app")
    root = AppRoot()
    root.initialize(ui=ui)
    
    from machaon.package.repository import BitbucketRepArchive
    from machaon.package.auth import BasicAuth
    root.add_package(
        "machaon.shell",
        "module:machaon.types.shell",
    )
    root.add_package(
        "hello",
        "bitbucket:betasewer/test_module"
    )

    root.run()

launch()

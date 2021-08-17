#!/usr/bin/env python3
# coding: utf-8

def launch():
    from machaon.app import AppRoot
    from machaon.ui.tk import tkLauncher
    ui = tkLauncher("test app")
    root = AppRoot()
    root.initialize(ui=ui)
    
    root.add_package(
        "hello",
        "bitbucket:betasewer/test_module:hello"
    )
    root.run()

launch()

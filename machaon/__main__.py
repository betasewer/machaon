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
    root.add_package(
        "xuthus",
        "package:xuthus",
    )
    root.add_package(
        "protenor",
        "package:protenor",
    )
    root.add_package(
        "docxx",
        "github:betasewer/python-docx-xtended:docxx",
        modules = [
            "docxx.ma"
        ]
    )

    #root.add_startup_message("DocProcessor new default-setup process (desktop Path / 会社 / ドストエフスキー論集 ls # 貝 DocxFile)")
    root.run()

launch()

#!/usr/bin/env python3
# coding: utf-8

def launch():
    from machaon.app import AppRoot
    root = AppRoot()
    root.initialize(ui="shell", title="test app")
    root.add_package(
        "hello",
        "bitbucket:betasewer/test_module:hello"
    )
    root.run()

launch()

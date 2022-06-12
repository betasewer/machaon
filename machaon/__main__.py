#!/usr/bin/env python3
# coding: utf-8

#
#
#
import argparse

def main():
    pser = argparse.ArgumentParser(
        prog = "machaon",
        description = "Machaon is a message-oriented Python application environment",
    )
    pser.add_argument("-e", "--entrypoint", help="Pythonの関数を[モジュール名.変数名]の形式で指定して実行")
    pser.add_argument("-m", "--message", help="任意のメッセージを実行")
    args = pser.parse_args()

    if args.entrypoint:
        from machaon.core.importer import attribute_loader
        loader = attribute_loader(args.entrypoint)
        entrypoint = loader()
        if callable(entrypoint):
            r = entrypoint()
            if r is not None:
                print(r)
        else:
            print(entrypoint)
    else:
        launch_ui()


def launch_ui():
    from machaon import AppRoot
    root = AppRoot()
    root.initialize(ui="shell", title="test app")
    root.add_package(
        "hello",
        "bitbucket:betasewer/test_module:hello"
    )
    root.run()

if __name__ == "__main__":
    main()

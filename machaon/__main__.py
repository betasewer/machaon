#!/usr/bin/env python3
# coding: utf-8

if __name__ == "__main__":
    from machaon.ui.main import create_main_app
    root = create_main_app()
    root.add_startup_message("@@test-progress")
    root.run()


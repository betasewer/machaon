#!/usr/bin/env python3
# coding: utf-8

#
#
#
def launch_sample_app(default_choice=None):
    import sys
    import argparse
    import machaon.starter
    from machaon.command import describe_command

    desc = 'machaon sample application'
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--cui", action="store_const", const="cui", dest="apptype")
    p.add_argument("--tk", action="store_const", const="tk", dest="apptype")
    args = p.parse_args()
    
    apptype = args.apptype or default_choice
    if apptype is None or apptype == "cui":
        boo = machaon.starter.ShellStarter()
    elif apptype == "tk":
        boo = machaon.starter.TkStarter(title="machaon sample app", geometry=(900,500))
    else:
        p.print_help()
        sys.exit()

    import machaon.commands.app
    import machaon.commands.character
    boo.install_commands("", machaon.commands.app.sample_commands().annex(machaon.commands.character.unicode_commands()))

    import machaon.commands.shell
    boo.install_commands("", machaon.commands.shell.shell_commands())

    boo.install_syscommands()

    boo.go()

#
launch_sample_app("tk")

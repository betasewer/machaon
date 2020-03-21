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

    import machaon.commands.catalogue as catalogue
    boo.install_commands("", catalogue.app_sample_commands().annexed(catalogue.unicode_commands()))
    boo.install_commands("", catalogue.shell_commands().annexed(catalogue.dataset_commands()))
    boo.install_syscommands()

    boo.go()

#
launch_sample_app("tk")

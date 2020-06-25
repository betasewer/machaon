#!/usr/bin/env python3
# coding: utf-8

#
#
#
def launch_sample_app(default_choice=None, directory=None):
    import sys
    import argparse
    import machaon.starter
    from machaon.command import describe_command

    desc = 'machaon sample application'
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--cui", action="store_const", const="cui", dest="apptype")
    p.add_argument("--tk", action="store_const", const="tk", dest="apptype")
    args = p.parse_args()

    if directory is None:
        directory = "C:\\codes\\machaon\\"

    apptype = args.apptype or default_choice
    if apptype is None or apptype == "cui":
        boo = machaon.starter.ShellStarter(directory=directory)
    elif apptype == "tk":
        boo = machaon.starter.TkStarter(title="machaon sample app", geometry=(900,500), directory=directory)
    else:
        p.print_help()
        sys.exit()

    import machaon.commands.catalogue as catalogue
    
    from machaon.package.repository import bitbucket_rep
    from machaon.package.auth import basic_auth
    boo.commandset("test", 
        source=bitbucket_rep("betasewer/test_module"), 
        entrypoint="hello"
    )
    boo.shell_commandset()
    boo.go()

#
launch_sample_app("tk")

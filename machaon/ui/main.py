import sys
import argparse
from machaon.app import AppRoot

def create_main_app():
    pser = argparse.ArgumentParser(
        prog = "machaon",
        description = "Machaon is a message-oriented Python application environment",
    )
    pser.add_argument("-e", "--entrypoint", help="Pythonの関数を[モジュール名.変数名]の形式で指定して実行")
    pser.add_argument("-m", "--message", help="任意のメッセージを実行")
    pser.add_argument("-d", "--deploy", help="machaonディレクトリを配備する")
    pser.add_argument("-u", "--ui", help="UIを指定する")
    pser.add_argument("-b", "--batch", help="バッチモードで起動する", action="store_const", dest="ui", const="batch")
    pser.add_argument("-l", "--location", help="開始ディレクトリを指定する")
    pser.add_argument("-o", "--option", help="オプションを指定する: [NAME]=[VALUE]", action="append", default=[])
    pser.add_argument("--update", help="machaonをアップデートして終了する", action="store_const", const=True)
    args = pser.parse_args()
    
    options = {}
    for opt in args.option:
        key, sep, value = opt.partition("=")
        if not sep:
            raise ValueError("=で区切ってください;" + opt)
        options[key] = value

    #
    #
    #
    root = AppRoot()
    root.initialize(
        ui = (args.ui or "shell"), 
        basic_dir = args.location,
        title = "machaon",
        **options
    )

    if args.entrypoint:
        from machaon.core.importer import attribute_loader
        loader = attribute_loader(args.entrypoint)
        entrypoint = loader()
        if callable(entrypoint):
            r = entrypoint()
        else:
            r = entrypoint
        
        root.add_startup_variable("result", r)
        root.add_startup_message("@result =")
    
    elif args.message:
        root.add_startup_message(args.message)

    elif args.deploy:
        root.add_startup_variable("path", args.deploy, "Path")
        root.add_startup_message("@@deploy @path")
        
    elif args.update:
        root.add_startup_message("@@machaon-update")
        root.add_startup_message("exit")
    
    return root



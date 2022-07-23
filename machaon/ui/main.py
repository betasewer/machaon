
import argparse
from machaon.app import AppRoot

def create_main_app():
    root = AppRoot()
    root.initialize(
        ui = "shell", 
        basic_dir = None,
        title = "machaon",
    )
    return root

def initialize_app_args(root, argv=None, **defaults):
    pser = argparse.ArgumentParser(
        prog = "machaon",
        description = "Machaon is a message-oriented Python application environment",
    )
    pser.add_argument("-e", "--entrypoint", help="Pythonの関数を[モジュール名.変数名]の形式で指定して実行", action="append", default=[])
    pser.add_argument("-m", "--message", help="任意のメッセージを実行", action="append", default=[])
    pser.add_argument("-d", "--deploy", help="machaonディレクトリを配備する")
    pser.add_argument("-u", "--ui", help="UIを指定する")
    pser.add_argument("-b", "--batch", help="バッチモードで起動する", action="store_const", dest="ui", const="batch")
    pser.add_argument("-l", "--location", help="開始ディレクトリを指定する")
    pser.add_argument("-o", "--option", help="オプションを指定する: [NAME]=[VALUE]", action="append", default=[])
    pser.add_argument("--update", help="machaonをアップデートして終了する", action="store_const", const=True)
    pser.add_argument("--title", help="アプリの名前")
    args = pser.parse_args(argv)
    
    autoexit = False

    if args.update or args.deploy:
        args.ui = defaults.get("ui", "batch")

    if args.entrypoint:
        for i, ent in enumerate(args.entrypoint, start=1):
            root.add_startup_message("_ ('{}' py)".format(ent))
    
    if args.message:
        for msg in args.message:
            root.add_startup_message(msg)

    if args.deploy:
        root.add_startup_variable("path", args.deploy, "Path")
        root.add_startup_message("@@deploy @path")
        autoexit = True
        
    if args.update:
        root.add_startup_message("@@machaon-update")
        autoexit = True

    if autoexit:
        root.add_startup_message("exit")
    
    options = {}
    for opt in args.option:
        key, sep, value = opt.partition("=")
        if not sep:
            raise ValueError("=で区切ってください;" + opt)
        options[key] = value

    # AppRoot.initializeの引数辞書を作成する
    initargs = {}
    initargs.update(defaults)
    if args.ui:
        initargs["ui"] = args.ui
    if args.location:
        initargs["basic_dir"] = args.location
    if args.title:
        initargs["title"] = args.title
    initargs.update(options)

    return initargs



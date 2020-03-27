from machaon.command import describe_command, describe_command_package

#
#
#
#
#
def app_commands():
    import machaon.commands.app as appcmd
    return describe_command_package(
        "machaon.app",
        description="ターミナルを操作するコマンドです。",
    )["syntax"](
        describe_command(
            appcmd.command_syntax,
            description="コマンド文字列を解析し、可能な解釈をすべて示します。"
        )["target command_string"](
            help="コマンド文字列",
            take_remainder=True
        )
    )["interrupt it"](
        describe_command(
            appcmd.command_interrupt,
            description="現在実行中のプロセスを中断します。"
        )
    )["help h"](
        describe_command(
            appcmd.command_help,      
            description="ヘルプを表示します。",
        )["target command_name"](
            nargs="?",
            help="ヘルプを見るコマンド"
        ),
    )["process_list"](
        describe_command(
            appcmd.command_processlist,
            description="プロセスの一覧を表示します。"
        )
    )["theme"](
        describe_command(
            appcmd.command_ui_theme,
            description="アプリのテーマを変更します。"
        )["target themename"](
            help="テーマ名",
            nargs="?"
        )["target --alt"](
            help="設定項目を上書きする [config-name]=[config-value]",
            take_remainder=True,
            default=()
        )["target --show"](
            help="設定項目を表示する",
            const_option=True
        )
    )["dataview %"](
        describe_command(
            target="list_operation",
            from_module="machaon.dataset",
            description="データを表示・選択する"
        )["target expression"](
            help="表示カラムの指定とフィルタ・ソート記述式",
        )["target --dataset -d"](
            help="対象データセットを指定",
            dest="dataset_index",
        )
    )["calc"](
        describe_command(
            "calculator",
            from_module="machaon.commands.shell",
            description="任意の式を実行します。"
        )["target -l --library"](
            help="ライブラリをロード",
            action="append",
        )["target expression"](
            help="Pythonの式",
            take_remainder=True
        )
    )["exit"](
        describe_command(
            lambda: None, # 実際に呼び出されることはない
            description="終了します。",
        ),
    )
    
#   
#
#
def app_sample_commands():
    return describe_command_package(
        "machaon.sample",
        description="テスト用コマンドです。"
    )["spam"](
        target="TestProcess",
        from_module="machaon.commands.app",        
        description="任意の文字を増やしてみるテスト"
    )["texts"](
        target="ColorProcess",
        from_module="machaon.commands.app",        
        description="テキスト表示のテスト"
    )["link"](
        target="LinkProcess",        
        from_module="machaon.commands.app",
        description="リンク文字列のテスト"
    )["progress"](
        describe_command(
            target="progress_display",
            from_module="machaon.commands.app",
            description="プログレスバーのテスト"
        )
    )

#
#
#
#
#
def unicode_commands():
    return describe_command_package(
        "machaon.text",
        description="文字に関するコマンドです。"
    )["unicode"](
        describe_command(
            target="encode_unicodes",
            from_module="machaon.commands.character",
            description="文字を入力 -> コードにする"
        )["target characters"](
            help="コードにしたい文字列"
        )
    )["unidec"](
        describe_command(
            target="decode_unicodes",
            from_module="machaon.commands.character",
            description="コードを入力 -> 文字にする"
        )["target characters"](
            help="文字列にしたいコード"
        )
    )

#
#
#
#
#
def shell_commands():
    return describe_command_package(
        "machaon.shell",
        description="PC内のファイルを操作するコマンドです。"
    )["$"](
        describe_command(
            "execprocess",
            from_module="machaon.commands.shell",
            description="シェルからコマンドを実行します。", 
        )["target commandhead"](
            help="実行するコマンド",
        )["target commandstr"](
            help="コマンド引数",
            take_remainder=True
        )
    )["cd"](
        describe_command(
            "currentdir",
            from_module="machaon.commands.shell",
            description="作業ディレクトリを変更します。", 
        )["target path"](
            nargs="?",
            help="移動先のパス"
        )["target -s --silent"](
            const_option=True,
            help="変更後lsを実行しない"
        ),
    )["ls"](
        describe_command(
            "filelist",
            from_module="machaon.commands.shell",
            description="作業ディレクトリにあるフォルダとファイルの一覧を表示します。", 
        )["target pattern"](
            help="表示するフォルダ・ファイルを絞り込む正規表現パターン（部分一致）",
            nargs="?",
            const=None
        )["target -l --long"](
            const_option=True,
            help="詳しい情報を表示する"
        )["target -t --time"](
            const_option="t",
            help="更新日時で降順に並び替える",
            dest="howsort"
        )["target -o --opc"](
            const_option=r"\.(docx|doc|xlsx|xls|pptx|ppt)$",
            help="OPCパッケージのみ表示する",
            dest="presetpattern"
        )["target -r --recurse"](
            help="配下のフォルダの中身も表示する[深度を指定：デフォルトは3]",
            type=int,
            nargs="?",
            const=3,
            default=1,
        )["target --view"](
            help="データの表示方法",
            take_remainder=True
        )
    )["text xt"](
        describe_command(
            "get_text_content",
            from_module="machaon.commands.shell",
            description="ファイルの内容をテキストとして表示します。", 
        )["target target"](
            help="表示するファイル",
            files=True,
        )["target -e --encoding"](
            help="テキストエンコーディング [utf-8|utf-16|ascii|shift-jis]",
            default=None
        )["target -d --head"](
            help="先頭からの表示行",
            type=int,
            nargs="?",
            const=1,
            default=10
        )["target -t --tail"](
            help="末尾からの表示行",
            type=int,
            nargs="?",
            const=1,
            default=0
        )["target -a --all"](
            help="全て表示",
            const_option=True
        )
    )["hex"](
        describe_command(
            "get_binary_content",
            from_module="machaon.commands.shell",
            description="ファイルの内容をバイナリとして表示します。", 
        )["target target"](
            help="表示するファイル",
            files=True,
        )["target --size"](
            help="読み込むバイト数",
            type=int,
            default=128
        )["target --width"](
            help="表示の幅",
            type=int,
            default=16
        )
    )

    

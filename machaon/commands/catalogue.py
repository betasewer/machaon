from machaon.command import describe_command, describe_command_package

#
#
#
#
#
def app_commands():
    import machaon.commands.app
    import machaon.commands.package
    return describe_command_package(
        "machaon.app",
        description="ターミナルを操作するコマンドです。",
    )["program-list prog"](
        describe_command(
            machaon.commands.app.command_commandlist,
            description="コマンドの一覧を表示します。",
        )
    )["process-list proc"](
        describe_command(
            machaon.commands.app.command_processlist,
            description="起動されたプロセスの一覧を表示します。"
        )
    )["package"](
        describe_command(
            machaon.commands.package.command_package,
            description="コマンドパッケージを管理します。",
        )["target -u --update"](
            help="ローカルのパッケージを更新する",
            dest="action",
            const="update",
        )["target -r --remove"](
            help="ローカルからパッケージを取り除く",
            dest="action",
            const="remove",
        )["target --forceupdate"](
            help="変更が無くてもアップデートを行う",
            flag=True
        )["target --index"](
            help="序数で対象コマンドパッケージを指定する",
            valuetype="int"
        )
    )["theme"](
        describe_command(
            machaon.commands.app.command_ui_theme,
            description="アプリのテーマを変更します。"
        )["target themename"](
            help="テーマ名",
            arg="?",
        )["target --alt"](
            help="設定項目を上書きする [config-name]=[config-value]",
            remainder=True,
        )["target --show"](
            help="設定項目を表示する",
            flag=True
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
    )["graphics"](
        describe_command(
            target="draw_graphic",
            from_module="machaon.commands.app",
            description="図形描画のテスト"
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
        )["target command"](
            help="実行するコマンド",
            remainder=True
        )["target --split"](
            help="引数を空白で区切って渡す",
            flag=True
        )
    )["cd"](
        describe_command(
            "currentdir",
            from_module="machaon.commands.shell",
            description="作業ディレクトリを変更します。", 
        )["target path"](
            help="移動先のパス",
            arg="?",
            valuetype="input-dirpath",
        )["target -s --silent"](
            help="変更後lsを実行しない",
            flag=True
        ),
    )["ls"](
        describe_command(
            "filelist",
            from_module="machaon.commands.shell",
            description="作業ディレクトリにあるフォルダとファイルの一覧を表示します。", 
        )["target pattern"](
            help="表示するフォルダ・ファイルを絞り込む正規表現パターン（部分一致）",
            arg="?",
        )["target -l --long"](
            help="詳しい情報を表示する",
            flag=True
        )["target -t --time"](
            help="更新日時で降順に並び替える",
            const="t",
            dest="howsort"
        )["target -d --dir"](
            help="ディレクトリのみ表示する",
            const=r"|d",
            dest="pattern"
        )["target -f --file"](
            help="ファイルのみ表示する",
            const=r"|f",
            dest="pattern"
        )["target -o --opc"](
            help="OPCパッケージのみ表示する",
            const=r"\.(docx|doc|xlsx|xls|pptx|ppt)$",
            dest="pattern"
        )["target -r --recurse"](
            help="配下のフォルダの中身も表示する[深度を指定：デフォルトは3]",
            valuetype=int,
            const=3,
            default=1,
        )["target -s --silent"](
            help="データのみを表示する",
            flag=True
        )
    )["text xt"](
        describe_command(
            "get_text_content",
            from_module="machaon.commands.shell",
            description="ファイルの内容をテキストとして表示します。", 
        )["target target"](
            help="表示するファイル",
            valuetype="input-filepath",
        )["target -e --encoding"](
            help="テキストエンコーディング [utf-8|utf-16|ascii|shift-jis]",
            default=None
        )["target -d --head"](
            help="先頭からの表示行",
            valuetype=int,
            const=1,
            default=10
        )["target -t --tail"](
            help="末尾からの表示行",
            valuetype=int,
            const=1,
            default=0
        )["target -a --all"](
            help="全て表示",
            flag=True,
        )
    )["hex xe"](
        describe_command(
            "get_binary_content",
            from_module="machaon.commands.shell",
            description="ファイルの内容をバイナリとして表示します。", 
        )["target target"](
            help="表示するファイル",
            valuetype="input-filepath",
        )["target --size"](
            help="読み込むバイト数",
            valuetype=int,
            default=128
        )["target --width"](
            help="表示の幅",
            valuetype=int,
            default=16
        )
    )["reencfname"](
        describe_command(
            "reencode_filename",
            from_module="machaon.commands.shell",
            description="文字化けしたファイル名をエンコードしなおします。",
        )["target dirpath"](
            help="対象とするディレクトリ",
            valuetype="input-dirpath"
        )["target --current"](
            help="現在の誤ったエンコーディング",
            default="cp932"
        )["target --original"](
            help="本来のエンコーディング",
            default="utf-8"
        )
    )["unzip"](
        describe_command(
            "unzip",
            from_module="machaon.commands.shell",
            description="zipを解凍します。",
        )["target path"](
            help="ZIPのパス",
            valuetype="input-dirpath"
        )["target --out"](
            help="解凍ディレクトリ",
            valuetype="dirpath"
        )["target --win -w"](
            help="UTF-8でエンコードされたファイル名をcp932に変換（Windows）",
        )
    )

    

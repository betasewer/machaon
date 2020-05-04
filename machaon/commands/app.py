#!/usr/bin/env python3
# coding: utf-8

from machaon.cui import test_yesno, composit_text


#
# アプリ基本コマンド
#
#
def command_syntax(spi, command_string):
    results = spi.get_app().parse_possible_commands(command_string)
    if not results:
        spi.message("[有効なコマンドではありません]")
    else:
        for entry in results:
            spi.message(entry.command_string())

# 
def command_interrupt(spi):  
    pass
"""  
    if not app.is_process_running():
        app.message("実行中のプロセスはありません")
        return
    app.message("プロセスを中断します")
    app.interrupt_process()
"""

#
class HelpItem():
    def __init__(self, cmdset, command_entry):
        self.cmdset = cmdset
        self.cmdentry = command_entry
        
    def get_link(self):
        return self.qual_keyword_list()[0]
    
    def keyword_list(self):
        return self.cmdentry.keywords
        
    def keyword(self):
        return ", ".join(self.cmdentry.keywords)
    
    def qual_keyword_list(self):
        pfx = self.cmdset.get_prefixes()
        heads = []
        for i, kwd in enumerate(self.cmdentry.keywords):
            if i == 0 and pfx:
                qualkwd = "{}.{}".format(pfx[0], kwd)
            elif pfx:
                qualkwd = "{}{}".format(pfx[1 if len(pfx)>=1 else 0], kwd)
            else:
                qualkwd = kwd
            heads.append(qualkwd)
        return heads

    def qual_keyword(self):
        return ", ".join(self.qual_keyword_list())
    
    def description(self):
        return self.cmdentry.get_description()
    
    def setname(self):
        return self.cmdset.get_name()

    def setdescription(self):
        return self.cmdset.get_description()
    
    @classmethod
    def describe(cls, builder):
        builder.default_columns(
            table=("qual_keyword", "description", "setname"),
        )["keyword kwd"](
            disp="キーワード"
        )["qual_keyword qkwd"](
            disp="コマンド"
        )["description desc"](
            disp="説明"
        )["setname"](
            disp="コマンドセット"
        )["setdescription setdesc"](
            disp="コマンドセットの説明"
        )

#
def command_help(spi):
    spi.message("<< コマンド一覧 >>")
    spi.message("各コマンドの詳細は <command> --help で")
    spi.message("")
    
    items = []
    for cmdset in spi.get_app().get_command_sets():
        for entry in cmdset.display_entries():
            items.append(HelpItem(cmdset, entry))

    spi.create_data(items, ":table")
    spi.dataview()


#
class ProcessListItem():
    def __init__(self, chamber):
        self.chamber = chamber

    def get_link(self):
        return self.chamber.get_index()
    
    def id(self):
        return self.chamber.get_index()

    def command(self):
        return self.chamber.get_command()
    
    def full_command(self):
        return self.chamber.get_process().build_command_string()
        
    def handler(self):
        parsedcommand = self.chamber.get_process().get_command_args()
        return " / ".join(parsedcommand.preview_handlers())

    def status(self):
        if self.chamber.is_waiting_input():
            return "稼働中：入力待ち"
        elif self.chamber.is_running():
            return "稼働中"
        elif self.chamber.is_failed():
            return "終了：失敗"
        else:
            return "終了：成功"

    def spirit_type(self):
        return type(self.chamber.get_bound_spirit()).__name__
    
    @classmethod
    def describe(cls, builder):
        builder.default_columns(
            table=("id", "full_command", "status"),
        )["id"](
            disp="ID"
        )["full_command fcmd"](
            disp="コマンド全体"
        )["command"](
            disp="コマンド"
        )["status"](
            disp="状態"
        )["spirit_type"](
            disp="スピリット"
        )["handler"](
            disp="ハンドラ呼び出し"
        )


#
def command_processlist(spi):
    spi.message("<< プロセス一覧 >>")
    items = [ProcessListItem(x) for x in spi.get_app().get_chambers()]
    spi.create_data(items, ":table")
    spi.dataview()

# テーマの選択
def command_ui_theme(spi, themename=None, alt="", show=False):
    from machaon.ui.theme import theme_dict, ShellThemeItem
    if themename is None and not alt:
        theme_items = [ShellThemeItem(k,fn()) for (k,fn) in theme_dict.items()]
        spi.create_data(theme_items, ":table")
        spi.dataview()
    else:
        root = spi.get_app()
        if themename:
            themenew = theme_dict.get(themename, None)
            if themenew is None:
                spi.error("'{}'という名のテーマはありません".format(themename))
                return
            theme = themenew()        
        else:
            theme = root.get_ui().get_theme()
        
        for altrow in alt.split():
            cfgname, cfgval = altrow.split("=")
            theme.setval(cfgname, cfgval)
        
        root.get_ui().apply_theme(theme)


# 立ち上げスクリプトのひな形を吐き出す
def command_bootstrap(app, tk=True):
    pass
    
#
# クラスサンプル用コマンド
#
class TestProcess():
    def __init__(self, app):
        self.app = app
    
    def init_process(self):
        self.app.message("文字列を倍増するプロセスを開始.")
    
    def process_target(self):
        target = self.app.get_input("文字列を入力してください...")
        templ = self.app.get_input("倍数を入力してください...")
        if not templ.isdigit():
            self.app.error("数値が必要です")
        else:
            self.app.message_em("\n".join([target for _ in range(int(templ))]))   

    def exit_process(self):
        self.app.message("文字列を倍増するプロセスを終了.")
    
    @classmethod
    def describe(cls, cmd):
        cmd.describe(
            description = "文字列を倍増します。"
        )

#
class LinkProcess():
    def __init__(self, app):
        self.app = app
    
    def init_process(self):
        self.app.message("リンク作成を開始.")
    
    def process_target(self, url):
        spl = url.split(maxsplit=1)
        if len(spl)==1:
            url = spl[0]
            target = url
        elif len(spl)==2:
            url = spl[0]
            target = spl[1]
        else:
            raise ValueError("")

        self.app.hyperlink(target, link=url)

    def exit_process(self):
        self.app.message("リンク作成を終了.")
        
    @classmethod
    def describe(cls, cmd):
        cmd.describe(
            description = "リンクを貼ります。"
        )["target url_and_text"](
            help = "リンクのURLと文字列",
            dest = "url"
        )
    
#
class ColorProcess():
    def __init__(self, app):
        self.app = app
    
    def process_target(self, text):
        self.app.message(text)
        self.app.message_em("【強調】" + text)
        self.app.custom_message("input", "【入力】" + text)
        self.app.custom_message("hyperlink", "【リンク】" + text)
        self.app.warn("【注意】" + text)
        self.app.error("【エラー発生】" + text)
    
    @classmethod
    def describe(cls, cmd):
        cmd.describe(
            description = "文字色のサンプルを表示します。"
        )["target --text"](
            default="文字色のサンプルです。"
        )

#
def progress_display(app):
    app.message("プログレスバーのテスト")
    app.start_progress_display(total=50)
    for _ in range(50):
        app.interruption_point(progress=1)
    app.finish_progress_display(total=50)

    
    

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
        for process, _spirit, result in results:
            spi.message(process.get_prog()+" "+result.get_expanded_command())

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
        
    def keyword(self):
        return ", ".join(self.cmdentry.keywords)

    def qual_keyword(self):
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
        return ", ".join(heads)
    
    def description(self):
        return self.cmdentry.get_description()
    
    def setname(self):
        return self.cmdset.get_name()

    def setdescription(self):
        return self.cmdset.get_description()
    
    @classmethod
    def describe(cls, builder):
        builder.default_columns(
            table=("keyword", "description", "setname"),
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
def command_help(spi, command_name=None):
    spi.message("<< コマンド一覧 >>")
    spi.message("各コマンドの詳細は command --help で")
    spi.message("")
    
    items = []
    for cmdset in spi.get_app().get_command_sets():
        for entry in cmdset.display_entries():
            items.append(HelpItem(cmdset, entry))

    spi.create_data(items, ":table")
    spi.dataview()

"""   
    for cmdset in spi.get_app().get_command_sets():
        pfx = cmdset.get_prefixes()
        msgs = []

        for entry in cmdset.display_entries():
            heads = []
            for i, k in enumerate(entry.keywords):
                if i == 0 and pfx:
                    fk = "{}.{}".format(pfx[0], k)
                elif pfx:
                    fk = "{}{}".format(pfx[1 if len(pfx)>=1 else 0], k)
                else:
                    fk = k
                heads.append((k, fk))

            if command_name and not any(command_name in head for (_, head) in heads):
                continue

            for k, fk in heads:
                msgs.append(spi.hyperlink.msg(k, nobreak=True, link=fk))
                msgs.append(spi.message.msg(", ", nobreak=True))
            msgs.pop()
            
            for l in composit_text(entry.get_description(), 100, indent=4, first_indent=6).splitlines():
                msgs.append(spi.message.msg(l))
        
        if not msgs:
            continue

        if pfx:
            msg = spi.warn.msg(pfx[0])
            spi.message_em("[%1%] ", embed=[msg], nobreak=True)
        spi.message_em(cmdset.get_description())
        spi.message("---------------------------")
        for m in msgs:
            spi.post_message(m)
        spi.message("")
    
    spi.message("")
"""

# 終了処理はAppRoot内にある
def command_exit(spi):
    raise NotImplementedError()
    
# テーマの選択
def command_ui_theme(app, themename=None, alt=(), show=False):
    from machaon.ui.theme import themebook
    if themename is None and not alt and not show:
        for name in themebook.keys():
            app.hyperlink(name)
        return

    root = app.get_app()
    if themename is not None:
        themenew = themebook.get(themename, None)
        if themenew is None:
            app.error("'{}'という名のテーマはありません".format(themename))
            return
        theme = themenew()
    else:
        theme = root.get_ui().get_theme()
    
    for altline in alt:
        cfgname, cfgval = altline.split("=")
        theme.setval(cfgname, cfgval)
    
    if show:
        for k, v in theme.config.items():
            app.message("{}={}".format(k,v))
    else:
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
    
    def process_target(self, target, url):
        self.app.hyperlink(target, link=url)

    def exit_process(self):
        self.app.message("リンク作成を終了.")
        
    @classmethod
    def describe(cls, cmd):
        cmd.describe(
            description = "リンクを貼ります。"
        )["target target"](
            help = "リンクの文字列"
        )["target url"](
            help = "リンク先URL"
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

    
    

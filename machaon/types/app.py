#!/usr/bin/env python3
# coding: utf-8

from machaon.cui import test_yesno, composit_text

class RootObject:
    """ @type
    アプリケーションを表すグローバルなオブジェクト。
    """

    def __init__(self, context):
        self.context = context

    #
    # メソッド
    #
    def types(self, spirit):
        '''@method spirit
        使用可能な型を列挙する。
        Params:
        Returns:
            Set[Type]: (name,doc) 型のリスト
        '''
        types = []
        for t in self.context.type_module.enum():
            types.append(t)
        return types
    
    def var(self, name):
        '''@method
        変数を参照する。
        Params:
            name(str): 引数名
        Returns:
            Object: 変数
        '''
        item = self.context.input_objects.get_by_name(name)
        if item is None:
            raise ValueError(name)
        return item.object

    def packages(self):
        ''' @method
        パッケージを取得する。
        Returns:
            Set[Package]: (name, source, scope) パッケージリスト
        '''
        return list(self.context.root.enum_packages())
    
    def chamber(self):
        ''' @method
        現在のチャンバーを取得する。
        Params:
        Returns:
            AppChamber: プロセス
        '''
        chm = self.context.root.get_active_chamber()
        return chm

#
#
#
class AppChamber:
    """ @type
    プロセスとその結果を保持するチャンバーオブジェクト
    ValueType:
        machaon.process.ProcessChamber
    """
    def dump_message(self, chm, app):
        """ @method spirit
        処理済みのメッセージを詳細な形式で表示する。
        """
        for msg in chm.get_process_messages():
            app.post("message", msg.text)
            app.post("message", "tag={}".format(msg.tag))
            for k, v in msg.args.items():
                app.post("message", "{}={}".format(k, v))



"""

class HelpItem():
    def __init__(self, cmdset, command_entry):
        self.cmdset = cmdset
        self.cmdentry = command_entry
        
    def first_qual_keyword(self):
        return self.qual_keyword_list()[0]
    
    def keyword_list(self):
        return self.cmdentry.keywords
        
    def keyword(self):
        return ", ".join(self.cmdentry.keywords)
    
    def qual_keyword_list(self):
        pfx = self.cmdset.get_prefixes()
        heads = []
        for i, kwd in enumerate(self.keyword_list()):
            if i == 0 and pfx:
                qualkwd = "{}::{}".format(kwd, pfx[0])
            elif pfx:
                qualkwd = "{}::{}".format(kwd, pfx[1 if len(pfx)>=1 else 0])
            else:
                qualkwd = kwd
            heads.append(qualkwd)
        return heads

    def qual_keyword(self):
        return ", ".join(self.qual_keyword_list())
    
    def description(self):
        return self.cmdentry.get_description()
    
    def setprefix(self):
        return ", ".join(self.cmdset.prefixes)
    
    def setname(self):
        return self.cmdset.get_name()

    def setdescription(self):
        return self.cmdset.get_description()
    
    @classmethod
    def describe(cls, builder):
        builder.default_columns(
            table=("keyword", "setprefix", "description", "setname"),
            link="first_qual_keyword"
        )["keyword kwd"](
            disp="キーワード"
        )["qual_keyword qkwd"](
            disp="コマンド"
        )["first_qual_keyword"](
            disp="最初のコマンド"
        )["description desc"](
            disp="説明"
        )["setname"](
            disp="コマンドセット"
        )["setprefix"](
            disp="コマンドセット指定子"
        )["setdescription setdesc"](
            disp="コマンドセットの説明"
        )

# 
class NotAvailableItem(HelpItem):
    def __init__(self, cmdset, description):
        super().__init__(cmdset, None)
        self._desc = description
    
    def keyword_list(self):
        return ["***"]
        
    def description(self):
        return "<{}>".format(self._desc)
    
    def setname(self):
        return "<パッケージ {}>".format(self.cmdset.get_name())

    def setdescription(self):
        return ""

#
def command_commandlist(spi):
    spi.post("message", "<< コマンド一覧 >>")
    spi.post("message", "各コマンドの詳細は <command> --help で")
    spi.post("message")
    
    items = []
    for cmdset in spi.get_app().get_command_sets():
        if isinstance(cmdset, NotYetInstalledCommandSet):
            items.append(NotAvailableItem(cmdset, "インストールされていません"))
        elif isinstance(cmdset, LoadFailedCommandSet):
            items.append(NotAvailableItem(cmdset, "ロードに失敗：" + cmdset.error))
        else:
            for entry in cmdset.display_commands():
                items.append(HelpItem(cmdset, entry))

    spi.create_data(items)
    spi.dataview()


#
class ProcessListItem():
    def __init__(self, chamber):
        self.chamber = chamber

    def id(self):
        return self.chamber.get_index()

    def command(self):
        return self.chamber.get_command()
    
    def full_command(self):
        p = self.chamber.get_process()
        if p.is_executed():
            return p.build_command_string()
        else:
            return p.get_command_string()

    def status(self):
        if self.chamber.is_waiting_input():
            return "稼働中：入力待ち"
        elif not self.chamber.is_finished():
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
        )

#
def command_processlist(spi):
    spi.message("<< プロセス一覧 >>")
    items = [] 
    for chm in spi.get_app().get_chambers():
        if chm.get_process() is spi.get_process():
            continue
        items.append(ProcessListItem(chm))
    spi.create_data(items)
    spi.dataview()

# テーマの選択
def command_ui_theme(spi, themename=None, alt="", show=False):
    from machaon.ui.theme import theme_dict, ShellThemeItem
    if themename is None and not alt:
        theme_items = [ShellThemeItem(k,fn()) for (k,fn) in theme_dict.items()]
        spi.create_data(theme_items)
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
            self.app.message-em("\n".join([target for _ in range(int(templ))]))   

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
        self.app.message-em("【強調】" + text)
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

    
#
def draw_graphic(app):
    app.message-em("図形描画のテスト")

    with app.canvas("cv", width=200, height=400) as cv:
        cv.rectangle_frame(coord=(2,2,100,200), color="#00FF00")
        cv.rectangle_frame(coord=(50,50,200,250), color="#FF0000", dash=",")
        cv.rectangle_frame(coord=(10,100,90,300), color="#0000FF")
    
    with app.canvas("cv2", width=200, height=400) as cv:
        cv.oval(coord=(10,10,200,400), color="#004444")
        cv.rectangle(coord=(2,2,100,200), color="#00FF00")
        cv.rectangle(coord=(50,50,200,250), color="#FF0000", stipple="grey50")
        cv.rectangle(coord=(10,100,90,300), color="#0000FF")

"""

#!/usr/bin/env python3
# coding: utf-8

from machaon.types.package import AppPackageType
from machaon.app import AppRoot, deploy_directory, transfer_deployed_directory

class RootObject:
    """
    アプリケーションを表すグローバルなオブジェクト。
    """

    def __init__(self, context):
        self.context = context
    
    @property
    def root(self) -> AppRoot:
        return self.context.root

    #
    # メソッド
    #
    def startup(self, spirit):
        ''' @task
        起動画面を表示し、パッケージをロードする。
        '''
        spirit.post('message', "Welcome to")
        spirit.post('message-em', '''
8b    d8    db     dP""b8 88  88    db     dP"Yb  88b 88 
88b  d88   dPYb   dP   `" 88  88   dPYb   dP   Yb 88Yb88 
88YbdP88  dP__Yb  Yb      888888  dP__Yb  Yb   dP 88 Y88 
88 YY 88 dP""""Yb  YboodP 88  88 dP""""Yb  YbodP  88  Y8
          [AN OBJECT-BASED PYTHON APP LAUNCHER]                                  
        '''[1:])

        self.context.root._initialize()

        spirit.post("message", "パッケージをロードします")
        for pkg in self.context.root.enum_packages():
            spirit.post("message", "{}".format(pkg.name), nobreak=True)
            self.context.root.load_pkg(pkg)
            spirit.post("message", " -> {}".format(AppPackageType.status(AppPackageType(), pkg, spirit)))
        
        spirit.post("message", "")
        spirit.post("message", "ヘルプ")
        spirit.post("message", "")


    def types(self, spirit):
        '''@task
        使用可能な型を列挙する。
        Params:
        Returns:
            Sheet[Type](name, scope, doc): 型のリスト
        '''
        types = []
        for t in self.context.type_module.enum():
            types.append(t)
        return types
    
    def vars(self):
        '''@method
        全ての変数を取得する。
        Returns:
            ObjectCollection: 辞書
        '''
        return self.context.input_objects
    
    def store_objects(self):
        ''' @method alias-name [store]
        machaonフォルダのファイル名を列挙する。
        Returns:
            Sheet[Str]: 名前のリスト
        '''
        from machaon.core.persistence import enum_persistent_names
        return enum_persistent_names(self.context.root)

    def packages(self):
        ''' @method
        パッケージを取得する。
        Returns:
            Sheet[Package](name, source, scope, status): パッケージリスト
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
    
    def context_(self):
        ''' @method alias-name [context]
        現在の呼び出しコンテキストを取得する。
        Returns:
            Context: 
        '''
        return self.context
    
    def spirit_(self):
        ''' @method alias-name [spirit]
        現在の呼び出しコンテキストのSpiritを取得する。
        Returns:
            Any:
        '''
        return self.context.spirit

    def _clear_processes(self, app, pred):
        ''' プロセスの実行結果とプロセス自体を削除する。 '''
        chm = self.context.root.get_active_chamber()
        pids = chm.drop_processes(pred=pred)
        app.get_ui().drop_screen_text(pids)
        
    def clear(self, app):
        ''' @method spirit [cla]
        現在のチャンバーの全ての実行結果を削除する。
        '''
        self._clear_processes(app, None)
    
    def clear_except_last(self, app):
        ''' @method spirit [cl]
        直前のプロセスを除いてすべてを削除する。
        '''
        chm = self.context.root.get_active_chamber()
        index = chm.last_process.get_index()
        def is_lastpr(pr):
            return pr.get_index() != index
        self._clear_processes(app, is_lastpr)

    def clear_failed(self, app):
        ''' @method spirit [claf]
        エラーを返した実行結果をすべて削除する。
        '''
        def is_failed(pr):
            return pr.is_failed()
        self._clear_processes(app, is_failed)
    
    def keymap(self):
        ''' @method
        ショートカットキーの一覧を表示する。 
        Returns:
            Sheet[ObjectCollection](key, command):
        '''
        keymap = self.root.get_ui().get_keymap()
        rets = []
        for cmd in keymap.all_commands():
            keys = [("+".join(x.key), x.when) for x in cmd.keybinds]
            if keys:
                key = ", ".join(["{} [{}]".format(*x) for x in keys])
            else:
                key = "割り当てなし"

            rets.append({
                "command" : cmd.command,
                "key" : key
            })
        return rets
    
    def deploy(self, app, path):
        ''' @task
        machaonディレクトリを配置する。
        Params:
            path(Path):
        '''
        deploy_directory(path)
    
    def trans_deploy(self, app, path):
        ''' @task
        machaonディレクトリを移譲する。
        Params:
            path(Path): 新たにmachaonが配備されるディレクトリ
        '''
        from machaon.types.shell import Path
        transfer_deployed_directory(app, Path(self.context.root.get_basic_dir()), path)

    def stringify(self):
        """ @meta """
        return "<root>"
    
    def testobj(self):
        """ @method 
        様々なテストを実装するオブジェクトを返す。
        Returns:
            Any
        """
        return AppTestObject()

#
#
#
class AppChamber:
    """
    プロセスとその結果を保持するチャンバーオブジェクト。
    ValueType:
        machaon.process.ProcessChamber
    """
    def dump_message(self, chm, app):
        """ @method spirit
        処理済みのメッセージを詳細な形式で表示する。
        """
        for msg in chm.get_process_messages():
            lines = []
            lines.append('"{}"'.format(msg.text))
            lines.append("tag={}".format(msg.tag))
            for k, v in msg.args.items():
                lines.append("{}={}".format(k, v))
            app.post("message", "\n".join(lines) + "\n")

#
#
#
class AppTestObject:
    """ @type
    さまざまなテストを提供する。
    """
    def colors(self, app, text="サンプルテキスト"):
        """ @method spirit
        テキストの色。
        Params:
            text(str): 
        """
        app.post("message", text)
        app.post("message-em", "【強調】" + text)
        app.post("input", "【入力】" + text)
        app.post("hyperlink", "【リンク】" + text)
        app.post("warn", "【注意】" + text)
        app.post("error", "【エラー発生】" + text)
    
    def progress(self, app):
        """ @task
        プログレスバーを表示。
        """
        app.start_progress_display(total=50)
        for _ in range(50):
            app.interruption_point(progress=1)
        app.finish_progress_display(total=50)

    def graphic(self, app):
        """ @method spirit
        図形を描画する。
        """
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

"""

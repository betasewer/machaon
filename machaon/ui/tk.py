#!/usr/bin/env python3
# coding: utf-8

import os
from typing import Tuple, Sequence, List

import tkinter as tk
import tkinter.filedialog
import tkinter.scrolledtext
import tkinter.ttk as ttk

from machaon.ui.basic_launcher import Launcher
from machaon.command import describe_command, describe_command_package
from machaon.cui import collapse_text
import machaon.platforms

#
#
#
class tkLauncher(Launcher):
    def __init__(self, title="", geometry=(900,400)):
        super().__init__(title, geometry)
        # GUI
        self.root = tkinter.Tk() #
        self.rootframe = None    #
        self.frames = []         #
        self.commandline = None  #
        self.chambermenu = None  #
        self.buttons = []        #
        self.log = None          #
        #
        self.hyperlinks = HyperlinkDatabase()
        self.chambermenu_active = None

    def openfilename_dialog(self, *, filters=None, initialdir=None):
        return tkinter.filedialog.askopenfilename(filetypes = filters, initialdir = initialdir)

    def opendirname_dialog(self, *, filters=None, initialdir=None):
        return tkinter.filedialog.askdirectory(initialdir = initialdir)

    #
    # UIの配置と初期化
    #
    def init_screen(self):
        self.root.title(self.screen_title)
        self.root.geometry("{}x{}".format(*self.screen_geo))
        self.root.protocol("WM_DELETE_WINDOW", self.app.exit)
        
        def commandline_break(e):
            return None
        self.root.bind('<Return>', self.on_commandline_return)
        self.root.bind('<Shift-Return>', commandline_break)
        self.root.bind('<Shift-Up>', self.on_commandline_up)
        self.root.bind('<Shift-Down>', self.on_commandline_down)

        padx, pady = 3, 3
        self.rootframe = ttk.Frame(self.root)
        self.rootframe.pack(fill=tk.BOTH, expand=1)

        self.frame = ttk.Frame(self.rootframe)
        self.frame.pack(fill=tk.BOTH, expand=1, padx=padx, pady=pady)
    
        # コマンド入力欄
        self.commandline = tk.Text(self.frame, relief="solid", height=4, width=40)
        self.commandline.grid(column=0, row=0, sticky="ns", padx=padx, pady=pady)
        self.commandline.focus_set()
        self.commandline.bind('<Return>', self.on_commandline_return)
        self.commandline.bind('<Shift-Return>', commandline_break)
        self.commandline.bind('<Shift-Up>', self.on_commandline_up)
        self.commandline.bind('<Shift-Down>', self.on_commandline_down)
        
        # ボタンパネル
        def addbutton(parent, **kwargs):
            b = ttk.Button(parent, **kwargs)
            self.buttons.append(b)
            return b
        
        def addframe(parent, **kwargs):
            f = ttk.Frame(parent, **kwargs)
            self.frames.append(f)
            return f
        
        histlist = tk.Text(self.frame, relief="solid", height=10, width=40)
        histlist.grid(column=0, row=1, sticky="ew", padx=padx, pady=pady)
        histlist.tag_configure("link")
        histlist.tag_bind("link", "<Enter>", lambda e: histlist.config(cursor="hand2"))
        histlist.tag_bind("link", "<Leave>", lambda e: histlist.config(cursor=""))
        histlist.tag_bind("link", "<Button-1>", self.chamber_menu_click)
        histlist.tag_configure("chamber", foreground="#000000")
        histlist.tag_configure("running", foreground="#00A000")
        histlist.mark_unset("insert")
        self.chambermenu = histlist
        
        # ログウィンドウ
        #self.log = tk.scrolledtext.ScrolledText(self.frame, wrap="word", font="TkFixedFont")
        self.log = tk.Text(self.frame, wrap="word", font="TkFixedFont", relief="solid")
        self.log.grid(column=1, row=0, rowspan=2, sticky="news", padx=padx, pady=pady) #  columnspan=2, 
        #self.log['font'] = ('consolas', '12')
        self.log.configure(state='disabled')
        self.log.tag_configure("hyperlink", underline=1)
        self.log.tag_bind("clickable", "<Enter>", self.hyper_enter)
        self.log.tag_bind("clickable", "<Leave>", self.hyper_leave)
        self.log.tag_bind("clickable", "<Control-Button-1>", self.hyper_click)
        self.log.tag_bind("clickable", "<Double-Button-1>", self.hyper_as_input_text)
        
        tk.Grid.columnconfigure(self.frame, 1, weight=1)
        tk.Grid.rowconfigure(self.frame, 0, weight=1)

        # ボタン等
        btnpanel = addframe(self.frame)
        btnpanel.grid(column=0, row=2, columnspan=2, sticky="new", padx=padx)
        
        #btnunredo = addframe(btnpanel)
        #btnunredo.pack(side=tk.TOP, fill=tk.X, pady=pady)
        b = addbutton(btnpanel, text=u"終了", command=self.app.exit, width=6)
        b.pack(side=tk.RIGHT, pady=padx)
        b = addbutton(btnpanel, text=u"▲", command=lambda:self.on_commandline_up(None), width=4)
        b.pack(side=tk.RIGHT, padx=padx)
        b = addbutton(btnpanel, text=u"▼", command=lambda:self.on_commandline_down(None), width=4)
        b.pack(side=tk.RIGHT, padx=padx)
        b = addbutton(btnpanel, text=u"作業ディレクトリ", command=self.change_cd_dialog)
        b.pack(side=tk.RIGHT, padx=padx)
        b = addbutton(btnpanel, text=u"ファイルパス", command=self.input_filepath)
        b.pack(side=tk.RIGHT, padx=padx)
        #b = tk.Button(btnpanel, text=u"テーマ", command=app.reset_screen, relief="groove")
        #b.pack(side=tk.TOP, fill=tk.X, pady=2)
    
        # フレームを除去       
        #self.root.overrideredirect(True)
        from machaon.ui.theme import dark_classic_theme
        self.apply_theme(dark_classic_theme())
    
    #
    # ログの操作
    #
    def insert_screen_message(self, msg):
        """ メッセージをログ欄に追加する """
        if msg.tag == "hyperlink":
            dbtag = self.hyperlinks.add(msg.get_hyperlink_link())
            tags = (msg.argument("linktag") or "hyperlink", "clickable", "hlink-{}".format(dbtag))
        else:
            tags = (msg.tag or "message",)
        
        self.log.configure(state='normal')
        
        # メッセージの挿入
        self.log.insert("end", msg.text, tags)
        if not msg.argument("nobreak", False):
            self.log.insert("end", "\n")

        self.log.configure(state='disabled')
        #self.log.yview_moveto(0)
    
    def delete_screen_message(self, lineno=None, count=None):
        """ ログ欄からメッセージ行を削除する"""
        if lineno is None:
            lineno = -1
        if count is None:
            count = 1
              
        if lineno < 0:
            indices = ("end linestart {} lines".format(lineno-count), "end linestart {} lines".format(lineno))
        elif 0 < lineno:
            indices = ("{} linestart".format(lineno), "{} linestart".format(lineno+count))
        else:
            return

        self.log.configure(state='normal')  
        self.log.delete(*indices)
        self.log.configure(state='disabled')

    def replace_screen_message(self, msgs):
        """ ログ欄をクリアし別のメッセージで置き換える """
        self.log.configure(state='normal')        
        self.log.delete(1.0, tk.END)
        for msg in msgs:
            self.message_handler(msg)
        self.log.configure(state='disabled')
        self.log.yview_moveto(0) # ログ上端へスクロール
        
    def watch_process(self, procchamber):
        """ アクティブなプロセスの状態を監視する。
            定期的に自動実行する """
        # プロセスの発したメッセージを読みに行く
        print("[{}] watching message...".format(procchamber.get_command()))
        running = procchamber.is_running()
        if not self.handle_chamber_message(procchamber):
            return
        if running:
            self.log.after(300, self.watch_process, procchamber) # 100ms
        else:
            self.update_chamber_menu(ceased=procchamber)
            print("[{}] watch finished.".format(procchamber.get_command()))
    
    #
    # key handler
    #
    def on_commandline_return(self, e):
        if self.execute_command_input():
            self.commandline.mark_set("INSERT", 0.0)
        return "break"

    def on_commandline_up(self, e):
        if not self.rollback_command_input():
            self.shift_active_chamber(1)
        self.commandline.mark_set("INSERT", 0.0)
        return "break"

    def on_commandline_down(self, e):
        self.shift_active_chamber(-1)
        self.commandline.mark_set("INSERT", 0.0)
        return "break"

    #
    # ハイパーリンク
    #
    def hyper_enter(self, _event):
        self.log.config(cursor="hand2")

    def hyper_leave(self, _event):
        self.log.config(cursor="")
    
    def hyper_clicked_link(self):
        tags = self.log.tag_names(tk.CURRENT)
        for tag in tags:
            if tag.startswith("hlink-"):
                break
        else:
            return
        key = int(tag[len("hlink-"):])
        link = self.hyperlinks.resolve(key)
        return link

    def hyper_click(self, _event):
        link = self.hyper_clicked_link()
        if link is not None:
            if os.path.isfile(link) or os.path.isdir(link):
                machaon.platforms.current.openfile(link)
            else:
                import webbrowser
                webbrowser.open_new_tab(link)

    #
    # チャンバーメニューの操作
    #
    def add_chamber_menu(self, chamber):
        line = collapse_text("  " + " ".join(chamber.get_command().splitlines()), 35)
        self.chambermenu.configure(state='normal')
        self.chambermenu.insert(tk.END, line + "\n", ("running", "link", "chamber",))
        self.chambermenu.yview_moveto(1.0)
        self.chambermenu.configure(state='disable')
        if chamber.is_running():
            self.update_chamber_menu(active=chamber)
        else:
            self.update_chamber_menu(active=chamber, ceased=chamber)
    
    def update_chamber_menu(self, *, active=None, ceased=None):
        def update_prefix(index, b, prefix):
            begin = "{}.{}".format(index+1, b)
            end = "{}.{}".format(index+1, b+len(prefix))
            if self.chambermenu.get(begin, end):
                self.chambermenu.replace(begin, end, prefix, ("chamber",))

        def remove_tag(index, tag):
            begin = "{}.0".format(index+1)
            end = "{}.end".format(index+1)
            if self.chambermenu.get(begin, end):
                self.chambermenu.tag_remove(tag, begin, end)

        self.chambermenu.configure(state='normal')

        if active:
            # 以前のアクティブチャンバー
            if self.chambermenu_active is not None:
                update_prefix(self.chambermenu_active, 0, "  ")
            # 新たなアクティブチャンバー
            idx = active.get_index()
            update_prefix(idx, 0, "> ")
            self.chambermenu_active = idx

        if ceased:
            idx = ceased.get_index()
            remove_tag(idx, "running")

        self.chambermenu.configure(state='disable')

    def chamber_menu_click(self, e):
        coord = self.chambermenu.index(tk.CURRENT)
        line, _ = coord.split(".")
        index = int(line)-1
        if index != self.app.get_active_chamber_index():
            self.app.set_active_chamber_index(index)
            self.update_active_chamber(self.app.get_active_chamber())

    #
    # 入力欄
    #
    def replace_input_text(self, text): 
        """ 入力文字列を代入する """
        self.commandline.delete(1.0, "end")
        self.commandline.insert(1.0, text)
        
    def insert_input_text(self, text):
        """ 入力文字列をカーソル位置に挿入する """
        self.commandline.insert("insert", text)
    
    def pop_input_text(self, nopop=False):
        """ 入力文字列を取り出しクリアする """
        text = self.commandline.get(1.0, tk.END)
        if not nopop:
            self.commandline.delete(1.0, tk.END)
        return text.rstrip() # 改行文字が最後に付属する?

    def hyper_as_input_text(self, _event):
        """ クリックされたハイパーリンクを入力欄に追加する """
        link = self.hyper_clicked_link()
        if os.path.exists(link):
            link = os.path.relpath(link, self.app.get_current_dir()) # 存在するパスであれば相対パスに直す
        self.insert_input_text(link)

    # 
    def run_mainloop(self):
        self.root.mainloop()
    
    def destroy(self):
        self.root.destroy()
    
    #
    # テーマ
    #
    def apply_theme(self, theme):
        ttktheme = theme.getval("ttktheme", "clam")
        style = ttk.Style()
        style.theme_use(ttktheme)

        bg = theme.getval("color.background")
        msg = theme.getval("color.message")
        msg_em = theme.getval("color.message_em", msg)
        msg_wan = theme.getval("color.warning", msg_em)
        msg_err = theme.getval("color.error", msg)
        msg_inp = theme.getval("color.userinput", msg_em)
        msg_hyp = theme.getval("color.hyperlink", msg)
        insmark = theme.getval("color.insertmarker", msg)
        label = theme.getval("color.label", msg_em)
        highlight = theme.getval("color.highlight", msg_em)
        secbg = theme.getval("color.sectionbackground", bg)

        style.configure("TButton", relief="flat", background=bg, foreground=msg)
        style.map("TButton", 
            lightcolor=[("pressed", bg)],
            background=[("disabled", bg), ("pressed", bg), ("active", highlight)],
            darkcolor=[("pressed", bg)],
            bordercolor=[("alternate", label)]
        )
        style.configure("TFrame", background=bg)

        self.rootframe.configure(style="TFrame")
        for button in self.buttons:
            button.configure(style="TButton")
        for frame in self.frames + [self.frame]:
            frame.configure(style="TFrame")
        
        commandfont = theme.getfont("commandfont")
        logfont = theme.getfont("logfont")

        self.commandline.configure(background=bg, foreground=msg, insertbackground=insmark, font=commandfont, borderwidth=1)
        
        self.log.configure(background=secbg, selectbackground=highlight, font=logfont, borderwidth=1)
        self.log.tag_configure("message", foreground=msg)
        self.log.tag_configure("message_em", foreground=msg_em)
        self.log.tag_configure("warn", foreground=msg_wan)
        self.log.tag_configure("error", foreground=msg_err)
        self.log.tag_configure("input", foreground=msg_inp)
        self.log.tag_configure("hyperlink", foreground=msg_hyp)

        self.chambermenu.configure(background=bg, selectbackground=highlight, font=logfont, borderwidth=1)
        self.chambermenu.tag_configure("chamber", foreground=msg)
        self.chambermenu.tag_configure("running", foreground=msg_em)

        self.set_theme(theme)

#
#
#
class HyperlinkDatabase:
    def __init__(self):
        self.keys = {}
        self.links = {}
    
    def add(self, link):
        if link in self.keys:
            key = self.keys[link]
        else:
            key = len(self.links)+1
            self.keys[link] = key
            self.links[key] = link
        return key
    
    def resolve(self, key):
        if key in self.links:
            return self.links[key]
        else:
            return None
    
    def loglines(self):
        ds = []
        ds.extend(["{:03}|{}".format(key, link) for (key, link) in self.links.items()])
        return ds


#
# デバッグ用コマンド
#
def show_history(app):
    app.message("<< コマンド履歴 >>")
    for i, his in enumerate(app.get_app().get_ui().get_command_history()):
        row = "{} | {}".format(i, his["command"])
        app.message(row)

def show_hyperlink_database(app):
    for l in app.ui.screen.hyperlinks.loglines():
        app.message(l)

def ui_sys_commands():
    return describe_command_package(
        description="ターミナルを操作するコマンドです。",
    )["history"](
        describe_command(
            target=show_history,
            description="入力履歴を表示します。"
        )
    )["hyperdb"](
        describe_command(
            target=show_hyperlink_database,
            description="内部のハイパーリンクデータベースを表示します。"
        )
    )


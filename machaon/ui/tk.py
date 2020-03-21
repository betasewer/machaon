#!/usr/bin/env python3
# coding: utf-8

import os
from datetime import datetime
from typing import Tuple, Sequence, List

import tkinter as tk
import tkinter.filedialog
import tkinter.scrolledtext
import tkinter.ttk as ttk

from machaon.ui.basic_launcher import Launcher
from machaon.command import describe_command, describe_command_package
from machaon.cui import collapse_text, get_text_width, ljust
import machaon.platforms

#
class textindex():
    def __init__(self, tkindex=None, *, line=None, char=None):
        if tkindex:
            parts = str(tkindex).split(".")
            if len(parts) < 2:
                return None
            if line is None:
                line = int(parts[0])
            if char is None:
                char = int(parts[1])
        if line is None:
            line = 1
        if char is None:
            char = 0        
        self.line = line
        self.char = char
    
    def __call__(self, *, line=None, char=None):
        if line is not None:
            self.line = line
        if char is not None:
            self.char = char
        return self
    
    def __str__(self):
        return "{}.{}".format(self.line, self.char)
    
    def compare(self, right):
        left = self
        if left.line < right.line:
            return 1
        elif left.line == right.line:
            if left.char == right.char:
                return 0
            elif left.char < right.char:
                return 1
            else:
                return -1
        else:
            return -1
        
    @staticmethod
    def rangetest(beg, end, point):
        return beg.compare(point) >= 0 and point.compare(end) > 0

#
class HYPERLABEL_DATAITEM:
    pass

#
#
#
class tkLauncher(Launcher):
    def __init__(self, title="", geometry=(900,400)):
        super().__init__(title, geometry)
        # GUI
        self.root = tkinter.Tk() #
        self.rootframe = None    #
        self.tkwidgets = []      # [(typename, widget)...]
        self.commandline = None  #
        self.chambermenu = None  #
        self.log = None          #
        #
        self.hyperlinks = HyperlinkDatabase()
        self.hyperlabels = []
        self.chambermenu_active = None
        self.focusbg = (None, None)
        self.is_stick_bottom = tk.BooleanVar(value=True)

    def openfilename_dialog(self, *, 
        filters=None, 
        initialdir=None, 
        multiple=False,
        title=None
    ):
        return tkinter.filedialog.askopenfilename(
            filetypes = filters or (), 
            initialdir = initialdir, 
            multiple = multiple, 
            title = title
        )

    def opendirname_dialog(self, *, 
        filters=None, 
        initialdir=None,     
        title=None,
        mustexist=False,
    ):
        return tkinter.filedialog.askdirectory(
            initialdir = initialdir, 
            title = title,
            mustexist = mustexist  
        )
    
    #
    # UIの配置と初期化
    #
    def init_screen(self):
        self.root.title(self.screen_title)
        self.root.geometry("{}x{}".format(*self.screen_geo))
        self.root.protocol("WM_DELETE_WINDOW", self.app.exit)        
        
        padx, pady = 3, 3
        self.rootframe = ttk.Frame(self.root)
        self.rootframe.pack(fill=tk.BOTH, expand=1)

        self.frame = ttk.Frame(self.rootframe)
        self.frame.pack(fill=tk.BOTH, expand=1, padx=padx, pady=pady)

        # コマンド入力欄
        self.commandline = tk.Text(self.frame, relief="solid", height=4)
        self.commandline.focus_set()
        #self.commandline.bind('<Return>', self.on_commandline_return)
        #self.commandline.bind('<Shift-Return>', commandline_break)
        #self.commandline.bind('<Shift-Up>', self.on_commandline_up)
        #self.commandline.bind('<Shift-Down>', self.on_commandline_down)
        
        # ボタンパネル
        def addbutton(parent, **kwargs):
            b = ttk.Button(parent, **kwargs)
            self.tkwidgets.append(("button", b))
            return b
        
        def addcheckbox(parent, **kwargs):
            ch = ttk.Checkbutton(parent, **kwargs)
            self.tkwidgets.append(("checkbox", ch))
            return ch
        
        def addframe(parent, **kwargs):
            f = ttk.Frame(parent, **kwargs)
            self.tkwidgets.append(("frame", f))
            return f
        
        histlist = tk.Text(self.frame, relief="solid", height=4, width=45)
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
        #self.log['font'] = ('consolas', '12')
        self.log.configure(state='disabled')
        self.log.tag_configure("hyperlink", underline=1)
        self.log.tag_bind("clickable", "<Enter>", self.hyper_enter)
        self.log.tag_bind("clickable", "<Leave>", self.hyper_leave)
        self.log.tag_bind("clickable", "<Button-1>", self.hyper_select)
        self.log.tag_bind("clickable", "<Control-Button-1>", self.hyper_open)
        self.log.tag_bind("clickable", "<Double-Button-1>", self.hyper_copy_input_text)

        # エラーログウィンドウ
        #self.errlog = tk.Text(self.frame, width=30, wrap="word", font="TkFixedFont", relief="solid")
        #self.errlog.configure(state='disabled')
        
        # ボタン等
        btnpanel = addframe(self.frame)
        #btnunredo = addframe(btnpanel)
        #btnunredo.pack(side=tk.TOP, fill=tk.X, pady=pady)
        # ----------------------
        b = addcheckbox(btnpanel, text=u"末尾に追従", variable=self.is_stick_bottom, onvalue=True, offvalue=False)
        b.pack(side=tk.RIGHT, padx=padx)
        b = addbutton(btnpanel, text=u"▼", command=lambda:self.scroll_page(1), width=4)
        b.pack(side=tk.RIGHT, padx=padx)
        b = addbutton(btnpanel, text=u"▲", command=lambda:self.scroll_page(-1), width=4)
        b.pack(side=tk.RIGHT, padx=padx)        
        b = addbutton(btnpanel, text=u"停止", command=lambda:self.app.interrupt_process(), width=4)
        b.pack(side=tk.RIGHT, padx=padx)
        # ----------------------
        b = addbutton(btnpanel, text=u"ファイルパス入力", command=self.input_filepath)
        b.pack(side=tk.LEFT, padx=padx)
        b = addbutton(btnpanel, text=u"作業ディレクトリ", command=self.change_cd_dialog)
        b.pack(side=tk.LEFT, padx=padx)
        #b = tk.Button(btnpanel, text=u"テーマ", command=app.reset_screen, relief="groove")
        #b.pack(side=tk.TOP, fill=tk.X, pady=2)
    
        # メインウィジェットの配置
        self.commandline.grid(column=0, row=0, sticky="news", padx=padx, pady=pady)
        self.chambermenu.grid(column=1, row=0, sticky="news", padx=0, pady=pady)
        self.log.grid(column=0, row=1, columnspan=2, sticky="news", padx=padx, pady=pady) #  columnspan=2, 
        btnpanel.grid(column=0, row=2, columnspan=2, sticky="new", padx=padx)
    
        tk.Grid.columnconfigure(self.frame, 0, weight=1)
        tk.Grid.rowconfigure(self.frame, 1, weight=1)
        tk.Grid.rowconfigure(self.frame, 2, weight=0)

        # フレームを除去       
        #self.root.overrideredirect(True)
        from machaon.ui.theme import dark_classic_theme
        self.apply_theme(dark_classic_theme())
        
        # イベント
        def bind_event(*widgets):
            def _deco(fn):
                fnname: str = fn.__name__
                onpos = fnname.find("on_")
                if onpos == -1:
                    raise ValueError("")
                sequence = "<{}>".format("-".join(fnname[onpos+3:].split("_")))
                for w in widgets:
                    w.bind(sequence, fn)
            return _deco

        # コマンド入力
        @bind_event(self.commandline)
        def cmdline_on_Return(e):
            self.on_commandline_return()        
            return "break"
        
        @bind_event(self.commandline)
        def cmdline_on_Control_Return(e): # 改行を入力
            return None
        
        @bind_event(self.commandline)
        def cmdline_on_Escape(e):
            self.log.focus_set() # 選択モードへ
            return "break"
        
        @bind_event(self.commandline)
        def cmdline_on_Alt_Right(e):
            self.rollback_command_input()
            return "break"
        
        @bind_event(self.commandline)
        def cmdline_on_Alt_Left(e):
            self.replace_input_text("")
            return "break"
        
        # ログウィンドウ
        @bind_event(self.log)
        def log_on_Return(e):
            self.log_input_selection()
            self.commandline.focus_set()
            return "break"
    
        @bind_event(self.log)
        def log_on_Escape(e):
            self.log_set_selection() # 項目選択を外す
            self.commandline.focus_set() # コマンド入力モードへ
            return None
            
        @bind_event(self.log)
        def log_on_Down(e):
            self.hyper_select_next()
            return "break"

        @bind_event(self.log)
        def log_on_Up(e):
            self.hyper_select_prev()
            return "break"

        # 全体
        @bind_event(self.root)
        def on_Shift_Up(e):
            self.on_commandline_up()
            return "break"

        @bind_event(self.root)
        def on_Shift_Down(e):
            self.on_commandline_down()
            return "break"

        @bind_event(self.root)
        def on_Control_Up(e):
            self.scroll_page(-1)

        @bind_event(self.root)
        def on_Control_Down(e):
            self.scroll_page(1)

        @bind_event(self.root, self.commandline, self.log)
        def on_Control_C(e):
            self.app.interrupt_process()
            return "break"

        @bind_event(self.commandline, self.log)
        def on_FocusIn(e):
            e.widget.configure(background=self.focusbg[0])
            
        @bind_event(self.commandline, self.log)
        def on_FocusOut(e):
            e.widget.configure(background=self.focusbg[1])
            
    #
    # ログの操作
    #
    def insert_screen_message(self, msg):
        """ メッセージをログ欄に追加する """
        if msg.tag == "hyperlink":
            tags = self.new_hyper_tags(msg.get_hyperlink_link(), msg.get_hyperlink_label(), msg.argument("linktag"))
        else:
            tags = (msg.tag or "message",)
        
        self.log.configure(state='normal')
        
        # メッセージの挿入
        self.log.insert("end", msg.get_text(), tags)
        if not msg.argument("nobreak", False):
            self.log.insert("end", "\n")

        self.log.configure(state='disabled')

        if self.is_stick_bottom.get():
            self.log.yview_moveto(1.0)
    
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
        
        if self.is_stick_bottom.get():
            self.log.yview_moveto(1.0)

    def replace_screen_message(self, msgs):
        """ ログ欄をクリアし別のメッセージで置き換える """
        self.log.configure(state='normal')        
        self.log.delete(1.0, tk.END)
        for msg in msgs:
            self.message_handler(msg)
        self.log.configure(state='disabled')

        if self.is_stick_bottom.get():
            self.log.yview_moveto(1.0) # ログ下端へスクロール
        else:
            self.log.yview_moveto(0) # ログ上端へスクロール
        
    def watch_active_process(self):
        """ アクティブなプロセスの発するメッセージを読みに行く """
        procchamber = self.app.get_active_chamber()
        print("[{}] watching message...".format(procchamber.get_command()))
        running = procchamber.is_running()
        if not self.handle_chamber_message(procchamber):
            return
        if running:
            self.log.after(300, self.watch_active_process) # 300ms
        else:
            print("stopped watching.")

    def watch_running_process(self, states):
        curstates = self.app.get_chambers_state()
        print("checking running... = {}".format(curstates["running"]))

        # 停止したプロセスを調べる
        for wasrunning in states["running"]:
            if wasrunning not in curstates["running"]:
                self.update_chamber_menu(ceased=wasrunning)
                procchamber = self.app.get_chamber(wasrunning)
                print("[{}] finished.".format(procchamber.get_command()))
        
        if curstates["running"]:
            self.log.after(100, self.watch_running_process, curstates) 
        else:
            print("stopped checking.")
    
    #
    def scroll_page(self, delta):
        self.log.yview_scroll(delta, "pages")
    
    #
    # key handler
    #
    def on_commandline_return(self):
        if self.execute_command_input():
            self.commandline.mark_set("INSERT", 0.0)

    def on_commandline_up(self):
        self.shift_active_chamber(1)
        self.commandline.mark_set("INSERT", 0.0)

    def on_commandline_down(self):
        self.shift_active_chamber(-1)
        self.commandline.mark_set("INSERT", 0.0)

    #
    # ハイパーリンク
    #
    def new_hyper_tags(self, link, label=None, linktag=None):
        dbkey = self.hyperlinks.add(link)
        tags = (linktag or "hyperlink", "clickable", "hlink-{}".format(dbkey))
        if label is not None:
            self.hyperlabels.append(label)
            labelkey = len(self.hyperlabels)-1
            tags = tags + ("label-{}".format(labelkey),)
        return tags

    def hyper_enter(self, _event):
        self.log.config(cursor="hand2")

    def hyper_leave(self, _event):
        self.log.config(cursor="")
    
    def hyper_resolve_link(self, index):
        linkkey = None
        labelkey = None
        tags = self.log.tag_names(index)
        for tag in tags:
            if tag.startswith("hlink-"):
                linkkey = int(tag[len("hlink-"):])
            elif tag.startswith("label-"):
                labelkey = int(tag[len("label-"):])

        if linkkey is None:
            return None, None
        link = self.hyperlinks.resolve(linkkey)
        label = None
        if labelkey is not None:
            label = self.hyperlabels[labelkey]
        return link, label

    def hyper_open(self, _event):
        link, _label = self.hyper_resolve_link(tk.CURRENT)
        if link is not None:
            if os.path.isfile(link) or os.path.isdir(link):
                machaon.platforms.current.openfile(link)
            else:
                import webbrowser
                webbrowser.open_new_tab(link)

    def hyper_select(self, _event):
        cur = textindex(self.log.index(tk.CURRENT))

        ppoints = self.log.tag_prevrange("hyperlink", tk.CURRENT)
        if ppoints and cur.compare(textindex(ppoints[1])) >= 0:
            beg, end = ppoints[0], ppoints[1]
        else: 
            # rend -> compare の順になっている
            npoints = self.log.tag_nextrange("hyperlink", tk.CURRENT)
            if not npoints:
                return
            beg, end = npoints[0], npoints[1]
            
        self.log_set_selection(beg, end)
        self.hyper_select_dataview_item(beg)

    def hyper_select_next(self):
        _beg, end = self.log_get_selection()
        if end is None:
            end = 1.0
        points = self.log.tag_nextrange("hyperlink", end)
        if not points:
            # 先頭に戻る
            points = self.log.tag_nextrange("hyperlink", "1.0")
            if not points:
                return
        self.log_set_selection(points[0], points[1])
        self.hyper_select_dataview_item(points[0])
        self.log.see(points[1])
    
    def hyper_select_prev(self):
        beg, _end = self.log_get_selection()
        if beg is None:
            beg = tk.END
        points = self.log.tag_prevrange("hyperlink", beg)
        if not points:
            # 末尾に戻る
            points = self.log.tag_prevrange("hyperlink", tk.END)
            if not points:
                return
        self.log_set_selection(points[0], points[1])
        self.hyper_select_dataview_item(points[0])
        self.log.see(points[1])

    #
    # 選択
    #
    def log_get_selection(self):
        selpoints = self.log.tag_ranges("log-selection")
        if not selpoints:
            return None, None
        return selpoints[0], selpoints[1]
    
    def log_set_selection(self, beg=None, end=None):
        # 現在の選択を取り除く
        oldbeg, oldend = self.log_get_selection()
        if oldbeg is not None:
            self.log.tag_remove("log-selection", oldbeg, oldend)

        # 新しい選択を設定
        if beg is not None:
            self.log.tag_add("log-selection", beg, end)
    
    def log_input_selection(self):
        # 選択位置を取得
        beg, _end = self.log_get_selection()
        if beg is None:
            return None

        # リンクからオブジェクトを取り出す
        resolved_as_item = False
        link, label = self.hyper_resolve_link(beg)
        if label is HYPERLABEL_DATAITEM:
            # データ取り出し
            resolved_as_item = True

        if not resolved_as_item:
            self.insert_input_text(link)
    
    #
    #
    #
    def dataviewer(self, viewtype):
        return {
            "table" : DataTableView,
            "wide" : DataWideView,
        }[viewtype]
    
    def insert_screen_dataview(self, msg, viewer, data):
        self.log.configure(state='normal')
        viewer.render(self, self.log, data)
        self.log.configure(state='disabled')
    
    def select_screen_dataview_item(self, index, charindex):
        # 現在のデータセットのアイテムを選択する
        datas = self.app.get_active_chamber().get_bound_data(running=True)
        if datas is None:
            return False
        datas.select(index)
        self.log.configure(state='normal')
        self.dataviewer(datas.get_viewtype()).change_select(self, self.log, charindex)
        self.log.configure(state='disabled')
        return True
    
    def hyper_select_dataview_item(self, index):
        # リンクからオブジェクトを取り出す        
        link, label = self.hyper_resolve_link(index)
        if label is HYPERLABEL_DATAITEM:
            itemindex = int(link)
            if self.select_screen_dataview_item(itemindex, charindex=index):
                return True
        return False

    def select_dataview_item(self, index):
        # リンクの場所を探す
        points = self.log.tag_ranges("hyperlink")
        for i in range(0, len(points), 2):
            link, label = self.hyper_resolve_link(points[i])
            if label is HYPERLABEL_DATAITEM:
                itemindex = int(link)
                if itemindex == index:
                    linkbeg = points[i]
                    linkend = points[i+1]
                    break
        else:
            raise ValueError("invalid dataview index")
        
        self.log_set_selection(linkbeg, linkend)
        self.select_screen_dataview_item(index, charindex=linkbeg)

    #
    # チャンバーメニューの操作
    #
    def add_chamber_menu(self, chamber):
        #sign = datetime.now().strftime("%Y-%m-%d %H:%M.%S")
        line = collapse_text(" ".join(chamber.get_command().splitlines()), 30)
        line = "[{}]".format(chamber.get_index()+1).ljust(6) + " " + line
        self.chambermenu.configure(state='normal')
        self.chambermenu.insert(tk.END, "  ", ("chamber,"))
        self.chambermenu.insert(tk.END, line + "\n", ("running", "link", "chamber",))
        self.chambermenu.yview_moveto(1.0)
        self.chambermenu.configure(state='disable')
        if chamber.is_running():
            self.update_chamber_menu(active=chamber.get_index())
        else:
            self.update_chamber_menu(active=chamber.get_index(), ceased=chamber.get_index())
    
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

        if active is not None:
            # 以前のアクティブチャンバー
            if self.chambermenu_active is not None:
                update_prefix(self.chambermenu_active, 0, "  ")
            # 新たなアクティブチャン
            update_prefix(active, 0, "> ")
            self.chambermenu_active = active
            # 必要ならスクロールする
            self.chambermenu.see("{}.0".format(self.chambermenu_active))

        if ceased is not None:
            remove_tag(ceased, "running")

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

    def hyper_copy_input_text(self, _event):
        """ クリックされたハイパーリンクを入力欄に追加する """
        link, _label = self.hyper_resolve_link(tk.CURRENT)
        if os.path.exists(link):
            link = os.path.relpath(link, self.app.get_current_dir()) # 存在するパスであれば相対パスに直す
        self.insert_input_text(link)

    # 
    #
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

        self.focusbg = (secbg, bg)

        style.configure("TButton", relief="flat", background=bg, foreground=msg)
        style.map("TButton", 
            lightcolor=[("pressed", bg)],
            background=[("disabled", bg), ("pressed", bg), ("active", highlight)],
            darkcolor=[("pressed", bg)],
            bordercolor=[("alternate", label)]
        )
        style.configure("TCheckbutton", background=bg, foreground=msg)
        style.map("TCheckbutton", 
            background=[("disabled", bg), ("pressed", bg), ("active", highlight)],
        )
        style.configure("TFrame", background=bg)

        self.rootframe.configure(style="TFrame")
        for typename, wid in self.tkwidgets:
            if typename == "button":
                wid.configure(style="TButton")
            elif typename == "frame":
                wid.configure(style="TFrame")
            elif typename == "checkbox":
                wid.configure(style="TCheckbutton")
        self.frame.configure(style="TFrame")
 
        commandfont = theme.getfont("commandfont")
        logfont = theme.getfont("logfont")

        self.commandline.configure(background=secbg, foreground=msg, insertbackground=insmark, font=commandfont, borderwidth=1)
        
        self.log.configure(background=bg, selectbackground=highlight, font=logfont, borderwidth=1)
        self.log.tag_configure("message", foreground=msg)
        self.log.tag_configure("message_em", foreground=msg_em)
        self.log.tag_configure("warn", foreground=msg_wan)
        self.log.tag_configure("error", foreground=msg_err)
        self.log.tag_configure("input", foreground=msg_inp)
        self.log.tag_configure("hyperlink", foreground=msg_hyp)
        self.log.tag_configure("log-selection", background=highlight, foreground=msg)
        self.log.tag_configure("log-item-selection", foreground=msg_em)

        self.chambermenu.configure(background=bg, selectbackground=highlight, font=logfont, borderwidth=1)
        self.chambermenu.tag_configure("chamber", foreground=msg)
        self.chambermenu.tag_configure("running", foreground=msg_inp)
        self.chambermenu.tag_configure("header", foreground=msg_em)

        self.set_theme(theme)

#
#
#
class DataTableView():    
    @classmethod
    def render(cls, ui, wnd, data):
        rows, colwidth = data.to_string_table()
        
        columns = [x.get_description() for x in data.get_predicates()]
        colwidths = [max(get_text_width(c),w)+3 for (c,w) in zip(columns, colwidth)]

        # ヘッダー
        head = "      | "
        wnd.insert("end", head, ("message",))
        line = ""
        for col, width in zip(columns, colwidths):
            line += ljust(col, width)
        wnd.insert("end", line+"\n", ("message_em",))

        # 値
        for i, row in enumerate(rows):
            line = " | "
            for s, width in zip(row, colwidths):
                line += ljust(s, width)

            index = str(i)
            if i == data.selection():
                head = ">> " + " "*(2-len(index))
                tags = ("message", "log-item-selection")
                linktags = ui.new_hyper_tags(index, HYPERLABEL_DATAITEM) + ("log-selection",)
            else:   
                head = " "*(5-len(index))
                tags = ("message",)
                linktags = ui.new_hyper_tags(index, HYPERLABEL_DATAITEM)

            wnd.insert("end", head, tags) # ヘッダー
            wnd.insert("end", index, linktags) # No. リンク
            wnd.insert("end", line+"\n", tags) # 行本体
    
    #
    @classmethod
    def change_select(cls, ui, wnd, charindex):
        wnd.configure(state='normal')
        
        selpoints = wnd.tag_ranges("log-item-selection")
        if selpoints:
            for i in range(0, len(selpoints), 2):
                wnd.tag_remove("log-item-selection", selpoints[i], selpoints[i+1])
            oline = textindex(selpoints[0])
            wnd.delete(str(oline(char=0)), str(oline(char=2)))
            wnd.insert(str(oline(char=0)), "  ")
        
        line = textindex(charindex)
        wnd.tag_add("log-item-selection", str(line(char=0)), str(line(char="end")))
        wnd.delete(str(line(char=0)), str(line(char=2)))
        wnd.insert(str(line(char=0)), ">>", "log-item-selection")
        
        wnd.configure(state='disabled')


#
class DataWideView(DataTableView):
    pass

#
#
#
class HyperlinkDatabase:
    def __init__(self):
        self.keys = {}
        self.links = {}
        self.labels = {}
    
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
        "machaon.ui.system",
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


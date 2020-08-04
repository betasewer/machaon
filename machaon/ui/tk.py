#!/usr/bin/env python3
# coding: utf-8

import os
from datetime import datetime
from typing import Tuple, Sequence, List, Optional, Any, Generator

import tkinter as tk
import tkinter.filedialog
import tkinter.scrolledtext
import tkinter.ttk as ttk

from machaon.ui.basic import Launcher
from machaon.command import describe_command, describe_command_package
from machaon.process import ProcessMessage, ProcessChamber
from machaon.cui import get_text_width, ljust, composit_text, collapse_text
import machaon.platforms

#
class TextIndex():
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
    
    def move(self, *, line=None, char=None):
        if line is not None:
            self.line = line
        if char is not None:
            self.char = char
        return self
    
    def moved(self, **kwargs):
        i = TextIndex(line=self.line, char=self.char)
        return i.move(**kwargs)
    
    def __str__(self):
        return "{}.{}".format(self.line, self.char)
    
    def string(self):
        return str(self)

    def shift(self, *, line=None, char=None):
        if line is not None:
            self.line += line
        if char is not None:
            self.char += char
        return self
        
    def shifted(self, **kwargs):
        i = TextIndex(line=self.line, char=self.char)
        return i.shift(**kwargs)
    
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
# tk.Text helper function
#
#
def text_get_first_tag_range(wid, tag) -> Tuple[Optional[str], Optional[str]]:
    selpoints = wid.tag_ranges(tag)
    if not selpoints:
        return None, None
    return selpoints[0], selpoints[1]

#
def text_iter_coord_pair(coords) -> Generator[Tuple[Optional[str], Optional[str]], None, None]:
    if len(coords)%2 == 1:
        raise ValueError("Number of the tag ranges is odd")
    for i in range(0, len(coords), 2):
        yield coords[i], coords[i+1]

#
class DataItemTag:
    @staticmethod
    def parse(s):
        spl = s.split("/")
        if len(spl) != 3 and spl[0] != "item":
            return None, None
        dataname, key = spl[1], spl[2]
        return dataname, int(key)
    
    @staticmethod
    def make(dataname, key):
        return "item/{}/{}".format(dataname, key)
    
    class HYPERLABEL:
        pass

#
class ObjectTag:
    @staticmethod
    def parse(s):
        spl = s.split("/")
        if len(spl) != 3 and spl[0] != "obj":
            return None, None
        deskindex, name = spl[1], spl[2]
        return int(deskindex), name

    @staticmethod
    def make(dataname, key):
        return "obj/{}/{}".format(dataname, key)

    class HYPERLABEL:
        pass

#
def menukeytag(index):
    return "chm{}".format(index)

#
#
#
class tkLauncher(Launcher):
    wrap_width = 144

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
        self.does_stick_bottom = tk.BooleanVar(value=False)
        self.does_overflow_wrap = tk.BooleanVar(value=False)

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
        self.commandline = tk.Text(self.frame, relief="solid", height=1)
        self.commandline.focus_set()
        
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
        
        histlist = tk.Text(self.frame, relief="solid", height=1)
        histlist.tag_configure("chamberlink")
        histlist.tag_bind("chamberlink", "<Enter>", lambda e: histlist.config(cursor="hand2"))
        histlist.tag_bind("chamberlink", "<Leave>", lambda e: histlist.config(cursor=""))
        histlist.tag_bind("chamberlink", "<Button-1>", self.chamber_menu_click)
        histlist.mark_unset("insert")
        self.chambermenu = histlist
        
        # ログウィンドウ
        #self.log = tk.scrolledtext.ScrolledText(self.frame, wrap="word", font="TkFixedFont")
        if self.does_overflow_wrap.get():
            wrap_option = "word"
        else:
            wrap_option = "none"
        self.log = tk.Text(self.frame, wrap=wrap_option, font="TkFixedFont", relief="solid")
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
        lefties = [
            addbutton(btnpanel, text=u"作業ディレクトリ", command=self.change_cd_dialog),
            addbutton(btnpanel, text=u"ファイルパス入力", command=self.input_filepath)
        ]
        for b in reversed(lefties):
            b.pack(side=tk.LEFT, padx=padx)

        righties = [
            addbutton(btnpanel, text=u"停止", command=lambda:self.break_chamber_process(), width=4),
            addbutton(btnpanel, text=u"▲", command=lambda:self.scroll_page(-1), width=4),
            addbutton(btnpanel, text=u"▼", command=lambda:self.scroll_page(1), width=4),
            addcheckbox(btnpanel, text=u"末尾に追従", variable=self.does_stick_bottom, onvalue=True, offvalue=False),
            addcheckbox(btnpanel, text=u"折り返し", variable=self.does_overflow_wrap, onvalue=True, offvalue=False)
        ]
        for b in reversed(righties):
            b.pack(side=tk.RIGHT, padx=padx)
    
        # メインウィジェットの配置
        self.commandline.grid(column=0, row=0, sticky="news", padx=padx, pady=pady)
        self.chambermenu.grid(column=0, row=1, sticky="news", padx=padx, pady=pady)
        self.log.grid(column=0, row=2, columnspan=2, sticky="news", padx=padx, pady=pady) #  columnspan=2, 
        btnpanel.grid(column=0, row=3, columnspan=2, sticky="new", padx=padx)
    
        tk.Grid.columnconfigure(self.frame, 0, weight=1)
        tk.Grid.rowconfigure(self.frame, 2, weight=1)
        tk.Grid.rowconfigure(self.frame, 3, weight=0)

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
    
        @bind_event(self.log, self.chambermenu)
        def log_on_Escape(e):
            self.log_set_selection() # 項目選択を外す
            self.commandline.focus_set() # コマンド入力モードへ
            return None

        # ログスクロール
        # コマンドモード
        @bind_event(self.commandline)
        def on_Control_Up(e):
            self.scroll_page(-1)
            return "break"

        @bind_event(self.commandline)
        def on_Control_Down(e):
            self.scroll_page(1)
            return "break"

        @bind_event(self.commandline)
        def on_Control_Shift_Left(e):
            self.scroll_horizon(-1)
            return "break"

        @bind_event(self.commandline)
        def on_Control_Shift_Right(e):
            self.scroll_horizon(1)
            return "break"
            
        @bind_event(self.commandline, self.log, self.root)
        def on_Control_Left(e):
            self.on_commandline_down()
            return "break"

        @bind_event(self.commandline, self.log, self.root)
        def on_Control_Right(e):
            self.on_commandline_up()
            return "break"
            
        # ログ閲覧モード
        @bind_event(self.log)
        def on_Key_w(e):
            self.scroll_vertical(-1)

        @bind_event(self.log)
        def on_Key_s(e):
            self.scroll_vertical(1)
            
        @bind_event(self.log)
        def on_Key_a(e):
            self.scroll_horizon(-1)

        @bind_event(self.log)
        def on_Key_d(e):
            self.scroll_horizon(1)
            
        @bind_event(self.log)
        def on_Key_q(e):
            self.scroll_page(-1)

        @bind_event(self.log)
        def on_Key_e(e):
            self.scroll_page(1)

        @bind_event(self.root, self.commandline, self.log)
        def on_Control_c(e):
            self.app.interrupt_process()
            return "break"

        @bind_event(self.log)
        def log_on_Down(e):
            self.hyper_select_next()
            return "break"

        @bind_event(self.log)
        def log_on_Up(e):
            self.hyper_select_prev()
            return "break"
            
        @bind_event(self.commandline, self.log)
        def on_Alt_c(e):
            self.close_active_chamber()
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

        if self.does_stick_bottom.get():
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
        
        if self.does_stick_bottom.get():
            self.log.yview_moveto(1.0)

    def replace_screen_message(self, msgs):
        """ ログ欄をクリアし別のメッセージで置き換える """
        self.log.configure(state='normal')        
        self.log.delete(1.0, tk.END)
        for msg in msgs:
            self.message_handler(msg)
        self.log.configure(state='disabled')

        if self.does_stick_bottom.get():
            self.log.yview_moveto(1.0) # ログ下端へスクロール
        else:
            self.log.yview_moveto(0) # ログ上端へスクロール
        
    def insert_screen_object_summary(self, msg):
        obj = msg.argument("object")
        deskname = msg.argument("deskname")
        sel = msg.argument("sel") 
        self.log.configure(state='normal')
        screen_insert_object(self, self.log, deskname, obj, sel)
        self.log.configure(state='disabled')
        
    def insert_screen_canvas(self, msg):
        """ ログ欄に図形を描画する """
        self.log.configure(state='normal')
        canvas_id = screen_insert_canvas(self.log, msg.argument("canvas"), self.theme)
        self.log.window_create(tk.END, window=canvas_id)
        self.log.insert(tk.END, "\n") # 
        self.log.configure(state='disabled')
    
    def get_screen_texts(self):
        """ プレーンテキストに変換 """
        return self.log.get(1.0, tk.END)
        
    def watch_chamber_message(self):
        """ アクティブなプロセスの発するメッセージを読みに行く """
        running = super().watch_chamber_message()
        if running:
            self.log.after(300, self.watch_chamber_message) # 300ms
        return running

    def watch_chamber_state(self, states):
        curstates = super().watch_chamber_state(states)
        if curstates["running"]:
            self.log.after(100, self.watch_chamber_state, curstates) 
        return curstates
    
    #
    def scroll_vertical(self, sign):
        self.log.yview_scroll(sign*2, "units")
    
    def scroll_page(self, sign):
        self.log.yview_scroll(sign*1, "pages")
    
    def scroll_horizon(self, sign):
        self.log.xview_scroll(sign*2, "units")
    
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
        return "break"

    def hyper_select(self, _event):
        cur = TextIndex(self.log.index(tk.CURRENT))

        ppoints = self.log.tag_prevrange("hyperlink", tk.CURRENT)
        if ppoints and cur.compare(TextIndex(ppoints[1])) >= 0:
            beg, end = ppoints[0], ppoints[1]
        else: 
            # rend -> compare の順になっている
            npoints = self.log.tag_nextrange("hyperlink", tk.CURRENT)
            if not npoints:
                return
            beg, end = npoints[0], npoints[1]
            
        self.log_set_selection(beg, end)
        self.hyper_select_object(beg)
        return "break"
        
    def hyper_select_object(self, index):
        # リンクからオブジェクトを取り出す        
        link, label = self.hyper_resolve_link(index)

        if label is DataItemTag.HYPERLABEL:
            # データビューのアイテム
            dataname, itemindex = DataItemTag.parse(link)
            if self.select_screen_dataview_item(dataname, itemindex, charindex=index):
                return True

        elif label is ObjectTag.HYPERLABEL:
            # オブジェクト
            deskname, objname = ObjectTag.parse(link)
            if self.select_screen_object_on_desktop(deskname, objname, charindex=index):
                return True

        return False

    def hyper_select_next(self):
        _beg, end = text_get_first_tag_range(self.log, "log-selection")
        if end is None:
            end = 1.0
        points = self.log.tag_nextrange("hyperlink", end)
        if not points:
            # 先頭に戻る
            points = self.log.tag_nextrange("hyperlink", "1.0")
            if not points:
                return

        self.log_set_selection(points[0], points[1])
        self.hyper_select_object(points[0])
        self.log.see(points[1])
    
    def hyper_select_prev(self):
        beg, _end = text_get_first_tag_range(self.log, "log-selection")
        if beg is None:
            beg = tk.END
        points = self.log.tag_prevrange("hyperlink", beg)
        if not points:
            # 末尾に戻る
            points = self.log.tag_prevrange("hyperlink", tk.END)
            if not points:
                return

        self.log_set_selection(points[0], points[1])
        self.hyper_select_object(points[0])
        self.log.see(points[1])

    def hyper_copy_input_text(self, _event):
        """ クリックされたハイパーリンクを入力欄に追加する """
        link, label = self.hyper_resolve_link(tk.CURRENT)
        if label is ObjectTag.HYPERLABEL:
            return
        if os.path.exists(link):
            link = os.path.relpath(link, self.app.get_current_dir()) # 存在するパスであれば相対パスに直す
        self.insert_input_text(link)
        return "break"

    #
    # 選択
    #
    def log_set_selection(self, beg=None, end=None):
        # 現在の選択を取り除く
        oldbeg, oldend = text_get_first_tag_range(self.log, "log-selection")
        if oldbeg is not None:
            self.log.tag_remove("log-selection", oldbeg, oldend)

        # 新しい選択を設定
        if beg is not None:
            self.log.tag_add("log-selection", beg, end)
    
    def log_input_selection(self):
        # 選択位置を取得
        beg, _end = text_get_first_tag_range(self.log, "log-selection")
        if beg is None:
            return None

        # リンクからオブジェクトを取り出す
        resolved_as_item = False
        link, label = self.hyper_resolve_link(beg)
        if label is DataItemTag.HYPERLABEL:
            # データ取り出し
            resolved_as_item = True

        if not resolved_as_item:
            self.insert_input_text(link)
    
    #
    #
    #
    def insert_screen_dataview(self, data, viewtype, dataname):
        insert = screen_get_dataview_method(viewtype, "insert")
        if insert is None:
            raise ValueError("表示形式'{}'には未対応です".format(viewtype))
        
        self.log.configure(state='normal')
        insert(self, self.log, data, dataname)
        self.log.insert("end", "\n")
        self.log.configure(state='disabled')
    
    def select_screen_dataview_item(self, dataname, index, charindex):
        # 現在のデータセットのアイテムを選択する
        dataobj = self.app.select_desktop().pick(dataname)
        if dataobj is None:
            return False
        datas = dataobj.value
        datas.select(index)

        viewtype = datas.get_viewtype()
        select_item = screen_get_dataview_method(viewtype, "select_item")
        if select_item is None:
            raise ValueError("表示形式'{}'には未対応です".format(viewtype))

        self.log.configure(state='normal')
        select_item(self, self.log, charindex, dataname)
        self.log.configure(state='disabled')
        return True
    
    def select_screen_object_on_desktop(self, deskname, objname, charindex):
        # オブジェクトを選択する
        objdesk = self.app.select_desktop(deskname)
        if objdesk is None:
            return False
        obj = objdesk.pick(objname)
        if obj is None:
            return False
        
        # 選択状態を切り替える
        sel = not objdesk.is_selected(objname)
        objdesk.select(objname, sel)

        # 描画を更新する
        self.log.configure(state='normal')
        screen_select_object(self, self.log, charindex, ObjectTag.make(deskname,objname), sel)
        self.log.configure(state='disabled')
        return True

    def select_dataview_item(self, index):
        # リンクの場所を探す
        ranges = self.log.tag_ranges("hyperlink")
        for linkbeg, linkend in text_iter_coord_pair(ranges):
            link, label = self.hyper_resolve_link(linkbeg)
            if label is DataItemTag.HYPERLABEL:
                dataname, itemindex = DataItemTag.parse(link)
                if itemindex == index:
                    break
        else:
            raise IndexError("invalid dataview index")

        self.log_set_selection(linkbeg, linkend)
        self.select_screen_dataview_item(dataname, index, charindex=linkbeg)
    
    #
    #
    #
    def insert_screen_appendix(self, valuelines, title=""):
        if title:
            self.insert_screen_message(ProcessMessage(">>> {}".format(title)))

        if isinstance(valuelines, str):
            self.insert_screen_message(ProcessMessage(valuelines))
        else:
            # シーケンスが渡されたなら、簡単な表形式にする
            maxspacing = max(*[len(x[0]) for x in valuelines], 0, 0)
            for value, desc in valuelines:
                spacing = " " * (maxspacing - len(value) + 2)
                for msg in ProcessMessage("%1%" + spacing + desc).embed(value, "message_em").expand():
                    self.insert_screen_message(msg)

        self.insert_screen_message(ProcessMessage(""))
        self.log.yview_moveto(1.0)

    #
    # チャンバーメニューの操作
    #
    def add_chamber_menu(self, chamber: ProcessChamber):
        # メニュータイトルの作成
        title = chamber.get_title()

        # 表示の末尾に追加
        keytag = menukeytag(chamber.get_index())
        self.chambermenu.configure(state='normal')
        if self.app.count_chamber() > 1:
            self.chambermenu.insert(tk.END, " | ", ("chamber",))
        self.chambermenu.insert(tk.END, " "+title+" ", ("running", "chamberlink", "chamber", keytag))
        self.chambermenu.configure(state='disable')

        # プロセスの状態を反映する
        if chamber.is_running():
            self.update_chamber_menu(active=chamber)
        else:
            self.update_chamber_menu(active=chamber, ceased=chamber)
    
    def update_chamber_menu(self, *, active: ProcessChamber = None, ceased: ProcessChamber = None):
        def update_prefix(index, prefixes):
            keytag = menukeytag(index)
            menubeg, menuend = text_get_first_tag_range(self.chambermenu, keytag)
            if menubeg is not None:
                leftinside = TextIndex(menubeg).shift(char=1).string()
                self.chambermenu.replace(menubeg, leftinside, prefixes[0], ("chamber", keytag))
                rightinside = TextIndex(menuend).shift(char=-1).string()
                self.chambermenu.replace(rightinside, menuend, prefixes[1], ("chamber", keytag))

        def update_tag(index, tag, on):
            keytag = menukeytag(index)
            menubeg, menuend = text_get_first_tag_range(self.chambermenu, keytag)
            if menubeg is not None:
                if on:
                    self.chambermenu.tag_add(tag, menubeg, menuend)
                else:
                    self.chambermenu.tag_remove(tag, menubeg, menuend)
            if tag=="active" and on:
                self.chambermenu.tag_lower(tag, "running")

        self.chambermenu.configure(state='normal')

        if active is not None:
            iactive = active.get_index()
            # 以前のアクティブチャンバー
            if self.chambermenu_active is not None:
                update_prefix(self.chambermenu_active, "  ")
                update_tag(self.chambermenu_active, "active", False)
            # 新たなアクティブチャンバー
            update_prefix(iactive, "<>")
            update_tag(iactive, "active", True)
            self.chambermenu_active = iactive
            # 必要ならスクロールする
            # self.chambermenu.see("{}.0".format(self.chambermenu_active))

        if ceased is not None:
            iceased = ceased.get_index()
            update_tag(iceased, "running", False)
            if ceased.is_failed():
                update_tag(iceased, "failed", True)

        self.chambermenu.configure(state='disable')
    
    def remove_chamber_menu(self, chm: ProcessChamber):
        index = chm.get_index()
        keytag = menukeytag(index)
        menubeg, menuend = text_get_first_tag_range(self.chambermenu, keytag)
        if menubeg is not None:
            self.chambermenu.configure(state='normal')
            self.chambermenu.delete(menubeg, menuend)
            # セパレータの削除
            if TextIndex(menubeg).char == 0:
                self.chambermenu.delete(1.0, 1.3) 
            else:
                self.chambermenu.delete(TextIndex(menubeg).shift(char=-3).string(), menubeg) 
            self.chambermenu.configure(state='disable')

    def chamber_menu_click(self, e):
        chmindex = None

        coord = self.chambermenu.index(tk.CURRENT)
        taghead = menukeytag("")
        for tag in self.chambermenu.tag_names(coord):
            if tag.startswith(taghead):
                idx = tag[len(taghead):]
                if not idx:
                    continue
                chmindex = int(idx)

        if chmindex is not None and chmindex != self.app.get_active_chamber_index():
            chm = self.app.select_chamber(chmindex, activate=True)
            self.update_active_chamber(chm)

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

        insecbg = theme.getval("color.inactivesectionbackground", bg)
        self.focusbg = (secbg, insecbg)

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
        self.log.tag_configure("object-frame", foreground="#888888")
        self.log.tag_configure("object-metadata", foreground=msg_inp)
        self.log.tag_configure("object-selection", foreground=msg_wan)

        self.chambermenu.configure(background=bg, selectbackground=highlight, font=logfont, borderwidth=0)
        self.chambermenu.tag_configure("chamber", foreground=msg)
        self.chambermenu.tag_configure("running", foreground=msg_inp)
        self.chambermenu.tag_configure("active", foreground=msg_em)
        self.chambermenu.tag_configure("failed", foreground=msg_err)

        self.set_theme(theme)

#
#
# 描画関数
#
#

#
# Dataview Table
#
def screen_dataview_table_insert(ui, wnd, dataview, dataname):
    rows, colmaxwidths = dataview.rows_to_string_table()
    
    columns = [x.get_help() for x in dataview.get_current_columns()]
    colwidths = [max(get_text_width(c),w)+3 for (c,w) in zip(columns, colmaxwidths)]

    # ヘッダー
    head = "      | "
    wnd.insert("end", head, ("message",))
    line = ""
    for col, width in zip(columns, colwidths):
        line += ljust(col, width)
    wnd.insert("end", line+"\n", ("message_em",))

    # 値
    for i, (itemindex, row) in enumerate(rows):
        line = " | "
        for s, width in zip(row, colwidths):
            line += ljust(s, width)

        index = str(i)
        itemkey = DataItemTag.make(dataname, itemindex)
        if i == dataview.selection():
            head = ">> " + " "*(2-len(index))
            tags = ("message", "log-item-selection")
            linktags = ui.new_hyper_tags(itemkey, DataItemTag.HYPERLABEL) + ("log-selection",)
        else:   
            head = " "*(5-len(index))
            tags = ("message",)
            linktags = ui.new_hyper_tags(itemkey, DataItemTag.HYPERLABEL)

        wnd.insert("end", head, tags) # ヘッダー
        wnd.insert("end", index, linktags) # No. リンク
        wnd.insert("end", line+"\n", tags) # 行本体
    
def screen_dataview_table_select_item(ui, wnd, charindex, dataname):
    wnd.configure(state='normal')
    
    selpoints = wnd.tag_ranges("log-item-selection")
    if selpoints:
        for i in range(0, len(selpoints), 2):
            wnd.tag_remove("log-item-selection", selpoints[i], selpoints[i+1])
        olinehead = TextIndex(selpoints[0]).move(char=0)
        wnd.delete(str(olinehead), str(olinehead.moved(char=2)))
        wnd.insert(str(olinehead), "  ")
    
    linehead = TextIndex(charindex).move(char=0)
    wnd.tag_add("log-item-selection", str(linehead), str(linehead.moved(char="end")))
    wnd.delete(str(linehead), str(linehead.moved(char=2)))
    wnd.insert(str(linehead), ">>", "log-item-selection")
    
    wnd.configure(state='disabled')

#
# Dataview Wide
#
def screen_dataview_wide_insert(ui, wnd):
    raise NotImplementedError()

def screen_dataview_wide_select_item(ui, wnd):
    raise NotImplementedError()

#
# Dataview List
#

# 実装関数を取得する
def screen_get_dataview_method(viewtype, name):
    viewtype = {
    }.get(viewtype, viewtype).lower()
    return globals().get("screen_dataview_{}_{}".format(viewtype, name), None)

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
# 埋め込みキャンバス
#
def screen_insert_canvas(parent, canvas, theme):
    """ キャンバスを作成する """
    bg = canvas.bg
    if bg is None:
        bg = theme.getval("color.background")

    cv = tk.Canvas(
        parent,
        width=canvas.width,
        height=canvas.height,
        bg=bg,
        highlightbackground=bg,
        highlightcolor=bg
    )

    for typ, args in canvas.get_graphs():
        if args.get("coord") is None:
            args["coord"] = (1, 1, canvas.width, canvas.height)

        if args.get("color") is None:
            args["color"] = theme.getval("color.message")

        if args.get("width") is None:
            args["width"] = 1
            
        if typ == "rectangle":
            cv.create_rectangle(*args["coord"], fill=args["color"], outline="", dash=args["dash"])
        elif typ == "rectangle-frame":
            coord = args["coord"]
            coordlist = [
                coord[0], coord[1],
                coord[2], coord[1],
                coord[2], coord[3],
                coord[0], coord[3],
                coord[0], coord[1]
            ]
            cv.create_line(*coordlist, fill=args["color"], width=args["width"], dash=args["dash"])
        elif typ == "oval":
            cv.create_oval(*args["coord"], fill=args["color"], outline="", dash=args["dash"])
        elif typ == "text":
            cv.create_text(*args["coord"], fill=args["color"], text=args["text"])
        else:
            raise NotImplementedError()

    return cv

#
#
#
def screen_insert_object(ui, wnd, deskname, obj, sel):
    width = 30
    objtag = ObjectTag.make(deskname, obj.name)
    tags = ("message", objtag)
    frametags = ("message", "object-frame", objtag)
    metatags = ("message", "object-metadata", objtag)
    buttontags = ("hyperlink", "clickable", objtag) + ui.new_hyper_tags(objtag, ObjectTag.HYPERLABEL)
    
    # 選択状態を反映する：枠のタグを切り替え
    if sel:
        frametags = frametags + ("object-selection",)
        btnchar = "X"
    else:
        btnchar = "O"

    # 上の罫
    title = "{}".format("object")
    tops = composit_text(" "+title+" ", width-3, fill=("─", " ")) # ボタンが4文字分入る
    wnd.insert("end", "┌" + tops + "[", frametags) # ヘッダー
    wnd.insert("end", btnchar, buttontags)
    wnd.insert("end", "]┐" + '\n', frametags) # ヘッダー

    # 上段：オブジェクトの情報
    props = [
        "name: {}".format(obj.name),
        "type: {}".format(obj.get_typename())
    ]
    for line, _ in composit_text.filled_lines("\n".join(props), width, fill=" "):
        wnd.insert("end", "｜", frametags)
        wnd.insert("end", line, metatags) 
        wnd.insert("end", "｜\n", frametags)

    # 仕切りの罫
    mid = composit_text("", width, fill=("─", " "))
    midline = "├" + mid + "┤" + '\n'
    wnd.insert("end", midline, frametags) # 

    # 下段：オブジェクトの値
    summary = obj.get_summary()
    for line, _ in composit_text.filled_lines(summary, width, fill=" "):
        wnd.insert("end", "｜", frametags)
        wnd.insert("end", line, tags) 
        wnd.insert("end", "｜\n", frametags)

    # 下の罫
    bottoms = composit_text("", width, fill=("─", " "))
    bottomline = "└" + bottoms + "┘" + '\n'
    wnd.insert("end", bottomline, frametags) # 

#
#
#
def screen_select_object(ui, wnd, charindex, objtag, sel):
    btnchar = TextIndex(charindex)
    btntags = wnd.tag_names(btnchar)

    # オブジェクトの枠の座標範囲を推定する
    framecoords = []
    objbeg, objend = text_get_first_tag_range(wnd, objtag)
    beg = TextIndex(objbeg)
    end = TextIndex(objend)
    while beg.line < end.line:
        if "object-frame" in wnd.tag_names(beg.shifted(char=2)):
            framecoords.extend([
                beg.string(), 
                beg.moved(char="end").string()
            ])
        else:
            framecoords.extend([
                beg.string(), 
                beg.moved(char=1).string(), 
                beg.moved(char="end").string() + " -1 indices", 
                beg.moved(char="end").string()
            ])
        beg = beg.shift(line=1)

    # 表示を切り替える：タグの付け替え、ボタンの切り替え
    if sel:
        wnd.tag_add("object-selection", *framecoords)
        wnd.delete(str(btnchar), str(btnchar.shifted(char=1)))
        wnd.insert(str(btnchar), "X", btntags)
    else:
        for beg, end in text_iter_coord_pair(framecoords):
            wnd.tag_remove("object-selection", beg, end) # なぜか一括削除に対応していない
        wnd.delete(str(btnchar), str(btnchar.shifted(char=1)))
        wnd.insert(str(btnchar), "O", btntags)


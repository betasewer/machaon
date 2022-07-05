#!/usr/bin/env python3
# coding: utf-8

import os
from typing import Tuple, Sequence, List, Optional, Any, Generator

import tkinter as tk
import tkinter.filedialog
import tkinter.scrolledtext
import tkinter.ttk as ttk

from machaon.ui.basic import KeybindMap, Launcher
from machaon.process import ProcessMessage, ProcessChamber
from machaon.cui import get_text_width, ljust, composit_text, collapse_text
import machaon.platforms

#
class tkCallWrapper:
    """ 例外を投げるように変更 """
    def __init__(self, func, subst, _widget):
        self.func = func
        self.subst = subst
    
    def __call__(self, *args):
        try:
            if self.subst:
                args = self.subst(*args)
            return self.func(*args)
        except:
            raise 

tk.CallWrapper = tkCallWrapper # type: ignore

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
class TkTextDump:
    def __init__(self, dump):
        self.dump = dump
        
    def items(self):
        return self.dump

#
HANDLE_MESSAGE_MAX = 10
APP_UPDATE_RATE = 100
TK_UPDATE_RATE = 10

#
#
#
class tkLauncher(Launcher):
    wrap_width = 144

    def __init__(self, args):
        super().__init__()
        # args
        self.screen_title = args.get("title", "Machaon Terminal")
        self.screen_geo = args.get("geometry", (850, 550))

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
        self.does_stick_bottom = tk.BooleanVar(value=True)
        self.does_overflow_wrap = tk.BooleanVar(value=False)
        self.dnd = machaon.platforms.draganddrop().tkDND()
        #
        self._destroyed = False

    def open_pathdialog(self, dialogtype, 
        initialdir=None, 
        initialfile=None, 
        filters=None, 
        multiple=False,
        title=None,
        defaultextension=None,
        mustexist=False
    ):
        if "f" in dialogtype:
            return tkinter.filedialog.askopenfilename(
                initialdir=initialdir,
                filetypes=filters or (),
                initialfile=initialfile,
                multiple=multiple,
                title=title or "ファイルを選択"
            )
        elif "d" in dialogtype:
            if multiple:
                raise ValueError("複数選択はサポートされていません")
            return tkinter.filedialog.askdirectory(
                initialdir=initialdir,
                mustexist=mustexist,
                title=title or "ディレクトリを選択"
            )
        elif "s" in dialogtype:
            return tkinter.filedialog.asksaveasfilename(
                initialdir=initialdir,
                defaultextension=defaultextension,
                title=title or "保存場所を選択"
            )
        else:
            raise ValueError("Bad dialogtype code")
    
    #
    # UIの配置と初期化
    #
    def addbutton(self, parent, **kwargs):
        b = ttk.Button(parent, **kwargs)
        self.tkwidgets.append(("button", b))
        return b
    
    def addcheckbox(self, parent, **kwargs):
        ch = ttk.Checkbutton(parent, **kwargs)
        self.tkwidgets.append(("checkbox", ch))
        return ch
    
    def addframe(self, parent, **kwargs):
        f = ttk.Frame(parent, **kwargs)
        self.tkwidgets.append(("frame", f))
        return f

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

        # オブジェクトウィンドウ
        #self.objdesk = tk.Text(self.frame, wrap=wrap_option, font="TkFixedFont", relief="solid", width=50)
        #self.objdesk.configure(state='disabled')

        #self.errlog = tk.Text(self.frame, width=30, wrap="word", font="TkFixedFont", relief="solid")
        #self.errlog.configure(state='disabled')
        
        # ボタン等
        self.btnpanel = self.addframe(self.frame)
        
        lefties = [
            #addbutton(btnpanel, text=u"作業ディレクトリ", command=self.change_cd_dialog),
            #addbutton(btnpanel, text=u"ファイルパス入力", command=self.input_filepath)
        ]
        for b in reversed(lefties):
            b.pack(side=tk.LEFT, padx=padx)

        righties = [
            self.addbutton(self.btnpanel, text=u"停止", command=lambda:self.break_chamber_process(), width=4),
            self.addbutton(self.btnpanel, text=u"▲", command=lambda:self.on_commandline_up(), width=4),
            self.addbutton(self.btnpanel, text=u"▼", command=lambda:self.on_commandline_down(), width=4),
            self.addcheckbox(self.btnpanel, text=u"末尾に追従", variable=self.does_stick_bottom, onvalue=True, offvalue=False),
            self.addcheckbox(self.btnpanel, text=u"折り返し", variable=self.does_overflow_wrap, onvalue=True, offvalue=False)
        ]
        for b in reversed(righties):
            b.pack(side=tk.RIGHT, padx=padx)
    
        # メインウィジェットの配置
        self.commandline.grid(column=0, row=0, columnspan=2, sticky="news", padx=padx, pady=pady)
        self.chambermenu.grid(column=0, row=1, columnspan=2, sticky="news", padx=padx, pady=pady)
        self.log.grid(column=0, row=2, sticky="news", padx=padx, pady=pady) #  columnspan=2, 
        #self.objdesk.grid(column=1, row=2, sticky="news", padx=padx, pady=pady) #  columnspan=2, 
        self.btnpanel.grid(column=0, row=3, columnspan=2, sticky="new", padx=padx)
    
        tk.Grid.columnconfigure(self.frame, 0, weight=1)
        tk.Grid.rowconfigure(self.frame, 2, weight=1)
        tk.Grid.rowconfigure(self.frame, 3, weight=0)

        # テーマの適用
        #self.root.overrideredirect(True)
        import machaon.ui.theme
        self.apply_theme(machaon.ui.theme.light_terminal_theme())

        # 入力イベントの定義
        self.keymap.define_ui_handlers(self)

        for command in self.keymap.all_commands():
            self.bind_command(command)
        self.bind_event("<FocusIn>", "fields", self.keymap.wrap_ui_handler(self.keymap.FocusIn, self))
        self.bind_event("<FocusOut>", "fields", self.keymap.wrap_ui_handler(self.keymap.FocusOut, self))

        # ドラッグアンドドロップの初期化
        self.dnd.enter(self)

    #
    #
    #
    

    #
    # ログの操作
    #
    def insert_screen_text(self, tag, text, **args):
        """ メッセージをログ欄に追加する """
        if tag == "hyperlink":
            link = args.get("link", text)
            label = args.get("label")
            linktag = args.get("linktag")
            tags = self.new_hyper_tags(link, label, linktag)
        else:
            tags = (tag or "message",)

        self.log.configure(state='normal')
        
        # プロセス区切りの挿入
        if "beg_of_process" in args:
            markname = "process{}beg".format(args["beg_of_process"])
            # 末尾に追加するとgravityを無視して追尾してしまう？ので一行上におく
            pos = TextIndex(self.log.index("end")).shift(line=-1)
            self.log.mark_set(markname, pos.string())
            self.log.mark_gravity(markname, "left")
        
        # メッセージの挿入
        self.log.insert("end", text, tags)
        if not args.get("nobreak", False):
            self.log.insert("end", "\n")
        
        # プロセス区切りの挿入
        if "end_of_process" in args:
            markname = "process{}end".format(args["end_of_process"])
            # 末尾に追加するとgravityを無視して追尾してしまう？ので一行上の最後の文字におく
            pos = TextIndex(self.log.index("end")).shift(line=-1).move(char="end")
            self.log.mark_set(markname, pos.string())
            self.log.mark_gravity(markname, "left")

        self.log.configure(state='disabled')
        
        # 下に自動でスクロール
        if self.does_stick_bottom.get():
            self.log.yview_moveto(1.0)
    
    def delete_screen_text(self, lineno, count, stick=False):
        """ ログ欄からメッセージ行を削除する"""              
        if lineno < 0:
            indices = ("end linestart {} lines".format(lineno-count), "end linestart {} lines".format(lineno))
        elif 0 < lineno:
            indices = ("{} linestart".format(lineno), "{} linestart".format(lineno+count))
        else:
            return

        self.log.configure(state='normal')  
        self.log.delete(*indices)
        self.log.configure(state='disabled')
        
        if stick and self.does_stick_bottom.get():
            self.log.yview_moveto(1.0)

    def replace_screen_text(self, textdump):
        """ ログ欄をクリアし別のメッセージで置き換える 
        Params:
            text (TkTextDump):
        """
        self.log.configure(state='normal')
        self.log.delete(1.0, tk.END)

        if textdump:
            tags = set()
            for key, value, index in textdump.items():
                if key == "tagon":
                    tags.add(value)
                elif key == "tagoff":
                    tags.remove(value)
                elif key == "text":
                    self.log.insert("end", value, tuple(tags))
                elif key == "window":
                    self.log.window_create(tk.END, window=value)
                elif key == "mark":
                    self.log.mark_set(value, index)
                else:
                    print("unsupported text element '{}': {}".format(key, value))

        self.log.configure(state='disabled')

        if self.does_stick_bottom.get():
            self.log.yview_moveto(1.0) # ログ下端へスクロール
        else:
            self.log.yview_moveto(0) # ログ上端へスクロール
    
    def dump_screen_text(self):
        """ エディタの内容物をダンプする """
        dumps = self.log.dump(1.0, tk.END)
        return TkTextDump(dumps)

    def drop_screen_text(self, process_ids):
        """ 指定のプロセスに関連するテキストの区画を削除する """
        allmarks = set(self.log.mark_names())
        usedmarks = []
        
        self.log.configure(state='normal')
        
        for pid in process_ids:
            head = "process{}beg".format(pid)
            if head not in allmarks:
                continue
            usedmarks.append(head)

            last = "process{}end".format(pid)
            if last not in allmarks:
                continue
            usedmarks.append(last)
            
            self.log.delete(head, last)
        
        self.log.configure(state='disabled')
        self.log.mark_unset(*usedmarks)

    def insert_screen_object_summary(self, msg):
        obj = msg.argument("object")
        deskname = msg.argument("deskname")
        sel = msg.argument("sel") 
        self.log.configure(state='normal')
        screen_insert_object(self, self.log, deskname, obj, sel)
        self.log.configure(state='disabled')
        
    def insert_screen_canvas(self, canvas):
        """ ログ欄に図形を描画する """
        self.log.configure(state='normal')
        canvas_id = screen_insert_canvas(self.log, canvas, self.theme)
        self.log.window_create(tk.END, window=canvas_id)
        self.log.insert(tk.END, "\n") # 
        self.log.configure(state='disabled')
    
    def get_screen_texts(self):
        """ プレーンテキストに変換 """
        return self.log.get(1.0, tk.END)
    
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
        self.execute_input_text()
        if self._destroyed:
            return
        self.commandline.mark_set("INSERT", 0.0)

    def on_commandline_up(self):
        self.shift_history(-1)
        self.commandline.mark_set("INSERT", 0.0)

    def on_commandline_down(self):
        self.shift_history(1)
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
                machaon.platforms.shellpath().start_file(link)
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
            if self.select_screen_setview_item(dataname, itemindex, charindex=index):
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
    def add_toggle_for_DND_pad(self, handler):
        """ ドラッグドロップパネルを開くボタンを設置する """
        # ボタンを追加
        button = self.addbutton(self.btnpanel, text="", command=handler)
        button.pack(side=tk.LEFT, padx=3)
        # キーバインドを追加
        command = self.keymap.get("DragAndDropPanelToggle")
        @command.handler
        def DragAndDropPanelToggle(e):
            handler()
            return "break"
        self.bind_command(command)
        return button
    
    def update_dnd(self):
        """ DND """
        values = self.dnd.update()
        if values is None:
            return
        self.insert_input_text(" ".join(values))
        self.commandline.focus() # 入力欄にフォーカスする

    #
    #
    #
    def insert_screen_setview(self, rows, columns, dataid, context):
        self.log.configure(state='normal')
        screen_sheetview_generate(self, self.log, rows, columns, dataid)
        self.log.insert("end", "\n")
        self.log.configure(state='disabled')
    
    def select_screen_setview_item(self, dataname, index, charindex):
        viewtype, dataid = dataname.split("@")
        self.log.configure(state='normal')
        screen_sheetview_select_item(self, self.log, charindex, dataid)
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

    #
    #
    #
    def insert_screen_progress_display(self, command, view):
        width = 30
        if command == "progress":
            if view.is_marquee():
                if not view.update_change_bit(30):
                    return
                l, m = (
                    (0, 0.3), (0.33, 0.34), (0.7, 0.3)
                )[view.lastbit % 3]
                lb = round(l * width)
                mb = round(m * width)
                rb = width - lb - mb
                bar = "[{}{}{}] ({})".format(lb*"-", mb*"o", rb*"-", view.progress)
            else:
                bar_width = round(width * view.get_progress_rate())
                rest_width = width - bar_width
                hund = round(view.get_progress_rate() * 100)
                bar = "[{}{}] {}% ({}/{})".format(bar_width*"o", rest_width*"-", hund, view.progress, view.total)
                     
        elif command == "start":
            bar = "[{}{}] {}% ({}/{})".format("", width*"-", 0, 0, view.total)
        elif command == "end":
            if view.is_marquee():
                bar = "[{}{}] ({})".format(width*"o", "", view.progress+1)
            else:
                bar = "[{}{}] {}% ({}/{})".format(width*"o", "", 100, view.total, view.total)
        else:
            return

        if view.title:
            header = "{}: ".format(view.title)
        else:
            header = ""

        if command != "start":
            self.delete_screen_text(-1, 1)
        self.insert_screen_text("message", header + bar)

    #
    # チャンバーメニューの操作
    #
    def add_chamber_menu(self, chamber: ProcessChamber):
        # メニュータイトルの作成
        title = chamber.get_title()

        # 表示の末尾に追加
        keytag = menukeytag(chamber.get_index())
        self.chambermenu.configure(state='normal')
        if self.chambers.count() > 1:
            self.chambermenu.insert(tk.END, " | ", ("chamber",))
        self.chambermenu.insert(tk.END, " "+title+" ", ("running", "chamberlink", "chamber", keytag))
        self.chambermenu.configure(state='disable')

        # プロセスの状態を反映する
        if not chamber.is_finished():
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

        if chmindex is not None and not self.chambers.is_active(chmindex):
            lastchm = self.chambers.get_active()
            chm = self.chambers.select(chmindex, activate=True)
            self.flip_chamber(chm, lastchm)

    #
    # 表示ハンドラ
    #
    def post_on_exec_process(self, process, exectime):
        """ プロセス実行開始時 """
        id = process.get_index()
        process.post("message-em", "[{:04}] ".format(id), nobreak=True, beg_of_process=id)
        timestamp = exectime.strftime("%Y-%m-%d|%H:%M.%S")
        process.post("message", "[{}] ".format(timestamp), nobreak=True)
        process.post("input", process.message.source)
    
    def post_on_success_process(self, process, ret, spirit):
        """ プロセスの正常終了時 """
        if ret.is_pretty():
            # 詳細表示を行う
            ret.pprint(spirit)
        else:
            process.post("message", " -> {} [{}]".format(ret.summarize(), ret.get_typename()))

    def post_on_interrupt_process(self, process):
        """ プロセス中断時 """
        process.post("message-em", "中断しました")
    
    def post_on_error_process(self, process, excep):
        """ プロセスの異常終了時 """
        process.post("error", " -> {}".format(excep.summarize()))

    def post_on_end_process(self, process):
        """ 正常であれ異常であれ、プロセスが終了した後に呼ばれる """
        procid = process.get_index()
        process.post("message", "", end_of_process=procid) # プロセス識別用のタグをつけた改行を1つ入れる
        process.post("message-em", self.get_input_prompt(), nobreak=True) # 次回入力へのプロンプト
    

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
    
    def get_input_text(self, pop=False):
        """ 入力文字列を取り出しクリアする """
        text = self.commandline.get(1.0, tk.END)
        if pop:
            self.commandline.delete(1.0, tk.END)
        return text.rstrip() # 改行文字が最後に付属する?

    # 
    #
    #
    def run_mainloop(self):
        def messagestep(interval):
            # メッセージを処理
            self.update_chamber_messages(HANDLE_MESSAGE_MAX)
            # チャンバーメニューの表示を更新
            self.update_chamber_states()
            # DNDを処理
            self.update_dnd()
            # 次回の呼び出し
            self.root.after(interval, messagestep, interval)
        
        self.root.after(0, messagestep, 100)
        self.root.mainloop()

    def destroy(self):
        self._destroyed = True
        self.root.destroy()

    #
    # input 
    #
    def new_keymap(self):
        return TkKeymap()

    def bind_event(self, sequence, wid, fn):
        if wid == "root":
            wids = (self.root, self.commandline, self.log, self.chambermenu)
        elif wid == "input":
            wids = (self.commandline,)
        elif wid == "log":
            wids = (self.log, self.chambermenu)
        elif wid == "fields":
            wids = (self.commandline, self.log)
        else:
            raise ValueError("不明なターゲットウィジェットです: {}".format(wid))
        
        for w in wids:
            w.bind(sequence, fn)

    def bind_command(self, command):
        for keybind in command.keybinds:
            # tkのシークエンスに変換する
            modifiers = []
            details = []
            for k in keybind.key:
                if k == "Ctrl":
                    k = "Control"
                elif k == "Cmd":
                    k = "Command"
                if k in tk_event_modifiers:
                    modifiers.append(k)
                else:
                    if len(k) == 1 and k.upper():
                        k = k.lower() # 大文字表記はShiftが必要になる
                    details.append(k)

            if not details:
                raise ValueError("tkのシークエンスに変換できませんでした: {} ({})".format(keybind.key, command))
            
            sequence = "<{}>".format("-".join(modifiers+details))

            # 登録
            self.bind_event(sequence, keybind.when, command.fn)

    #
    # テーマ
    #
    def apply_theme(self, theme):
        ttktheme = theme.getval("ttktheme", "clam")
        style = ttk.Style()
        style.theme_use(ttktheme)

        bg = theme.getval("color.background")
        msg = theme.getval("color.message")
        msg_em = theme.getval("color.message-em", msg)
        msg_wan = theme.getval("color.warning", msg_em)
        msg_err = theme.getval("color.error", msg)
        msg_inp = theme.getval("color.userinput", msg_em)
        msg_hyp = theme.getval("color.hyperlink", msg)
        insmark = theme.getval("color.insertmarker", msg)
        label = theme.getval("color.label", msg_em)
        highlight = theme.getval("color.highlight", msg_em)
        secbg = theme.getval("color.sectionbackground", bg)
        col_red = theme.getval("color.red")
        col_gre = theme.getval("color.green")
        col_blu = theme.getval("color.blue")
        col_yel = theme.getval("color.yellow")
        col_cya = theme.getval("color.cyan")
        col_mag = theme.getval("color.magenta")
        col_bla = theme.getval("color.black")
        col_gry = theme.getval("color.gray", theme.getval("color.grey"))

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
        self.log.tag_configure("message-em", foreground=msg_em)
        self.log.tag_configure("warn", foreground=msg_wan)
        self.log.tag_configure("error", foreground=msg_err)
        self.log.tag_configure("input", foreground=msg_inp)
        self.log.tag_configure("hyperlink", foreground=msg_hyp)
        self.log.tag_configure("log-selection", background=highlight, foreground=msg)
        self.log.tag_configure("log-item-selection", foreground=msg_em)
        self.log.tag_configure("black", foreground=col_bla)
        self.log.tag_configure("grey", foreground=col_gry)
        self.log.tag_configure("red", foreground=col_red)
        self.log.tag_configure("blue", foreground=col_blu)
        self.log.tag_configure("green", foreground=col_gre)
        self.log.tag_configure("cyan", foreground=col_cya)
        self.log.tag_configure("yellow", foreground=col_yel)
        self.log.tag_configure("magenta", foreground=col_mag)

        #self.objdesk.configure(background=bg, selectbackground=highlight, font=logfont, borderwidth=1)
        #self.objdesk.tag_configure("message", foreground=msg)
        #self.objdesk.tag_configure("object-frame", foreground="#888888")
        #self.objdesk.tag_configure("object-metadata", foreground=msg_inp)
        #self.objdesk.tag_configure("object-selection", foreground=msg_wan)

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
# ui, wnd, rows, columns, colmaxwidths, dataname
def screen_sheetview_generate(ui, wnd, rows, columns, dataname):
    sheettag = "sheet-{}".format(dataname)
    widths = []

    # 列幅計算の準備
    if not wnd.tag_configure(sheettag, "tabs")[-1]:
        cfgs = wnd.configure("font")
        import tkinter.font as tkfont
        wndfont = tkfont.Font(font=cfgs[-1]) #　デフォルトフォント 
        widths = [0 for _ in columns]

    # ヘッダー
    head = "\t \t| "
    wnd.insert("end", head, ("message", sheettag))
    line =  "\t".join(columns)
    wnd.insert("end", line+"\n", ("message-em", sheettag))
    if widths:
        widths = [max(w, wndfont.measure(s)) for w,s in zip(widths,columns)]

    # 値
    tags = ("message", sheettag)
    for i, (_itemindex, row) in enumerate(rows):
        line = "\t{}\t| ".format(i) + "\t".join(row)
        wnd.insert("end", line+"\n", tags)
        if widths:
            widths = [max(w, wndfont.measure(s)) for w,s in zip(widths,row)]
    
    # 列幅を計算する
    if widths:
        one = wndfont.measure("_")
        widths = [one*2, one*3] + widths
        widths[2] += one*2 # セパレータぶんの幅を先頭の値に加える
        widths = widths[0:2] + [x + one*2 for x in widths[2:]] # アキを加える

        start = 0
        tabs = []
        for w in widths:
            start += w
            tabs.append(start)
        wnd.tag_configure(sheettag, tabs=tabs)



def screen_sheetview_select_item(ui, wnd, charindex, _dataid):
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
    wnd.insert(str(linehead), "->", "log-item-selection")
    
    wnd.configure(state='disabled')

#
# Tuple 
#
def screen_setview_tuple_generate(ui, wnd, objects, dataname, context):
    # 値
    for i, obj in enumerate(objects):
        line = "{} [{}]".format(obj.summarize(), obj.get_typename())
        index = str(i)
        head = " "*(5-len(index))
        tags = ("message",)
        wnd.insert("end", head + index + " | " + line + "\n", tags)

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

    for args in canvas.graphs:
        if args.get("coord") is None:
            args["coord"] = (1, 1, canvas.width, canvas.height)

        if args.get("color") is None:
            args["color"] = theme.getval("color.message")

        if args.get("width") is None:
            args["width"] = 1
            
        typ = args["type"]
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
    summary = obj.summarize()
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



#
#
#
class TkKeymap(KeybindMap):
    """ 
    入力ハンドラを定義する 
    """
    def wrap_ui_handler(self, fn, ui):
        def _handler(e):
            return fn(ui, e)
        return _handler

    def Run(self, ui, e):
        """ 入力の実行 """
        ui.on_commandline_return()        
        return "break"
    
    def Interrupt(self, ui, e):
        """ 入力中止 """
        ui.app.interrupt()
        return "break"

    def CloseChamber(self, ui, e): 
        """ チャンバーを閉じる """
        ui.close_active_chamber()
        return "break"

    def InputInsertBreak(self, ui, e): 
        """ 改行を入力 """
        return None
    
    def InputClear(self, ui, e):
        """ """
        ui.replace_input_text("")
        return "break"

    def InputRollback(self, ui, e):
        """ """
        ui.rollback_input_text()
        return "break"
        
    def InputHistoryNext(self, ui, e):
        """ """
        ui.on_commandline_down()
        return "break"

    def InputHistoryPrev(self, ui, e):
        """ """
        ui.on_commandline_up()
        return "break"
    
    def InputPaneExit(self, ui, e):
        """ 選択モードへ """
        ui.log.focus_set()
        return "break"
    
    def LogPaneExit(self, ui, e):
        """  """
        ui.log_set_selection() # 項目選択を外す
        ui.commandline.focus_set() # コマンド入力モードへ
        return None
    
    def LogScrollPageUp(self, ui, e):
        ui.scroll_page(-1)
        return "break"

    def LogScrollPageDown(self, ui, e):
        ui.scroll_page(1)
        return "break"

    def LogScrollUp(self, ui, e):
        ui.scroll_vertical(-1)
        return "break"

    def LogScrollDown(self, ui, e):
        ui.scroll_vertical(1)
        return "break"
    
    def LogScrollLeft(self, ui, e):
        ui.scroll_horizon(-1)
        return "break"

    def LogScrollRight(self, ui, e):
        ui.scroll_horizon(1)
        return "break"
    
    def LogScrollNextProcess(self, ui, e):
        ui.hyper_select_next()
        return "break"

    def LogScrollPrevProcess(self, ui, e):
        ui.hyper_select_prev()
        return "break"
        
    def LogInputSelection(self, ui, e):
        ui.log_input_selection()
        ui.commandline.focus_set()
        return "break"

    def FocusIn(self, ui, e):
        e.widget.configure(background=ui.focusbg[0])

    def FocusOut(self, ui, e):
        e.widget.configure(background=ui.focusbg[1])


tk_event_modifiers = {
    "Control", 
    "Alt", "Option",
    "Shift",
    "Lock",
    "Extended",
    "Button1",
    "Button2",
    "Button3",
    "Button4",
    "Button5",
    "Mod1", 
    "Mod2", 
    "Mod3", 
    "Mod4", 
    "Mod5", 
    "Meta", "Command",
    "Double",
    "Triple",
    "Quadruple",
}


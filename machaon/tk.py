#!/usr/bin/env python3
# coding: utf-8

import os
import datetime
from threading import Event
from typing import Tuple, Sequence, List

import tkinter as tk
import tkinter.filedialog
import tkinter.scrolledtext
import tkinter.ttk as ttk

from machaon.app import AppMessage, BasicCUI
from machaon.command_launcher import CommandLauncher

#
#
#
class tkLauncherUI(BasicCUI):
    def __init__(self):
        self.app = None
        self.launcher = None
        self.screen = None
        
        self._cmdhistory = []
        self._curhistory = 0
        
    def init_with_app(self, app):
        self.app = app
        self.launcher = CommandLauncher(app)
        self.screen = tkLauncherScreen()
        self.screen.init_screen(app, self)
    
    def get_launcher(self):
        return self.launcher

    # メッセージはすべてキュー
    def post_message(self, msg):
        self.queue_message(msg)
    
    # ログウィンドウにメッセージを出力
    def message_handler(self, msg):
        self.screen.insert_log(msg)
    
    # スクリーンを初期化
    def reset_screen(self):
        self.screen.reset_log(self)
        self.screen.update_log(self)
    
    # 入力を取得
    def get_input(self, instr):
        instr += " >>> "
        self.app.message(instr, nobreak=True)
        inputtext = self.screen.wait_input()
        self.app.print_message(AppMessage(inputtext, "input"))
        return inputtext
    
    # コマンドを実行する
    def invoke_command(self, command):
        index = self.add_command_history(command)
        # スクリーンに表示
        self.reset_screen()
        tim = datetime.datetime.now().strftime("%Y-%m-%d|%H:%M.%S")
        self.app.message_em("{:02}[{}] >>> ".format(index+1, tim), nobreak=True)
        self.post_message(AppMessage(command, "input"))
        # 実行
        self.app.command_process(command, threading=True)

    # コマンド欄を実行する
    def execute_command_input(self):
        command = self.screen.pop_input_text()
        if self.screen.inputwaiting:
            self.screen.finish_input(command)
        else:
            self.invoke_command(command)
    
    # コマンド履歴への追加
    def add_command_history(self, command):
        self._cmdhistory.append({"command": command, "logs": None})
        self._curhistory = len(self._cmdhistory)-1
        return self._curhistory
        
    def add_command_log_history(self, logs):
        if len(self._cmdhistory)==0:
            return
        self._cmdhistory[-1]["logs"] = logs
        
    def rollback_command_history(self, d):
        if len(self._cmdhistory)==0:
            return
        if self.app.is_process_running():
            return
        index = self._curhistory - d
        if index<0 or len(self._cmdhistory)<=index:
            return
        history = self._cmdhistory[index]
        self._curhistory = index
        self.screen.replace_input_text(history["command"])
        logs = history["logs"]
        if logs is not None:
            self.screen.rollback_log(logs)
    
    def show_command_history(self):
        self.app.message("<< 履歴 >>")
        for i, his in enumerate(self._cmdhistory):
            row = "{} | {}".format(i, his["command"])
            self.app.message(row)
        
    # ダイアログからファイルパスを入力
    def input_filepath(self, *filters:Tuple[str, str]):
        filepath = tkinter.filedialog.askopenfilename(filetypes = filters, initialdir = self.app.get_current_dir())
        self.screen.insert_input_text("{}".format(filepath))
    
    # カレントディレクトリの変更
    def change_cd_dialog(self):
        path = tkinter.filedialog.askdirectory(initialdir = self.app.get_current_dir())
        self.invoke_command("cd {}".format(path))
        
    # ハイパーリンクのURLを列挙する
    def show_hyperlink_database(self):
        for l in self.screen.hyperlinks.loglines():
            self.app.message(l)

    # ハンドラ
    def run_mainloop(self):
        self.screen.run()

    def on_exit_command(self, procclass):
        self.app.message_em("実行終了\n")
        self.screen.take_logdump(self)
    
    def on_exit(self):
        self.screen.finish_input("") # 入力待ち状態を解消する
        self.screen.destroy()

#
# 色の設定
#
class GreenShellTheme():
    def __init__(self):
        self.colors =  {
            "background" : "#000000",
            "insertmarker" : "#FFFFFF",
            "message" : "#FFFFFF",
            "message_em" : "#00FF00",
            "warning" : "#FF8800",
            "error" : "#FF4444",
            "hyperlink" : "#0088FF",
            "userinput" : "#FFFF00",
            "label" : "#FFFFFF",
            "highlight" : "#005416",
        }

    def getcol(self, key, fallback=None):
        c = self.colors.get(key)
        if c is None and fallback is not None:
            c = fallback
        if c is None:
            c = default_theme.colors[key]
        return c

    # 色を設定する
    def apply(self, ui):
        style = ttk.Style()
        style.theme_use("clam")

        bg = self.getcol("background")
        msg = self.getcol("message")
        msg_em = self.getcol("message_em", msg)
        msg_wan = self.getcol("warning", msg_em)
        msg_err = self.getcol("error", msg)
        msg_inp = self.getcol("userinput", msg_em)
        msg_hyp = self.getcol("hyperlink", msg)
        insmark = self.getcol("insertmarker", msg)
        label = self.getcol("label", msg_em)
        highlight = self.getcol("highlight", msg_em)

        style.configure("TButton", relief="flat", background=bg, foreground=msg)
        style.map("TButton", 
            lightcolor=[("pressed", bg)],
            background=[("disabled", bg), ("pressed", bg), ("active", highlight)],
            darkcolor=[("pressed", bg)],
            bordercolor=[("alternate", label)]
        )
        style.configure("TFrame", background=bg)

        ui.commandline.configure(background=bg, foreground=msg, insertbackground=insmark)
        ui.log.configure(background=bg)
        ui.log.tag_configure("message", foreground=msg)
        ui.log.tag_configure("message_em", foreground=msg_em)
        ui.log.tag_configure("warn", foreground=msg_wan)
        ui.log.tag_configure("error", foreground=msg_err)
        ui.log.tag_configure("input", foreground=msg_inp)
        ui.log.tag_configure("hyper", foreground=msg_hyp)
        for button in ui.buttons:
            button.configure(style="TButton")
        for frame in ui.frames + [ui.frame]:
            frame.configure(style="TFrame")

#
class BlueShellTheme(GreenShellTheme):
    def __init__(self):
        super().__init__()
        customcols = {
            "message_em" : "#00FFFF",
            "warning" : "#D9FF00",
            "error" : "#FF4400",
            "userinput" : "#0060FF",
            "highlight" : "#0038A1",            
        }
        self.colors.update(customcols)

        
default_theme = GreenShellTheme()

#
#
#
class tkLauncherScreen():
    def __init__(self):
        super().__init__()
        # ルートウィジェット
        self.root = tkinter.Tk()
        self.commandline = None
        self.log = None
        self.logmsgdump = []

        # 入力終了イベント＆終了時のテキスト
        self.inputwaiting = False
        self.event_inputend = Event()
        self.lastinput = None
        
        self.hyperlinks = HyperlinkDatabase()
    
    # UIの配置と初期化
    def init_screen(self, app, launcher):
        self.root.title(app.title)
        self.root.geometry("900x400")
        self.root.protocol("WM_DELETE_WINDOW", app.exit)

        self.frame = ttk.Frame(self.root)
        self.frame.pack(fill=tk.BOTH, expand=1)
    
        # コマンド入力欄
        commandfont = ('Verdana', 10)
        self.commandline = tk.Text(self.frame, relief="solid", font=commandfont, height=4)
        self.commandline.grid(column=0, row=0, sticky="ew", padx=5)
        self.commandline.focus_set()
        
        def on_commandline_return(e):
            launcher.execute_command_input()
            self.commandline.mark_set("INSERT", 0.0)
            return "break"
        def on_commandline_up(e):
            launcher.rollback_command_history(1)
            self.commandline.mark_set("INSERT", 0.0)
            return "break"
        def on_commandline_down(e):
            launcher.rollback_command_history(-1)
            self.commandline.mark_set("INSERT", 0.0)
            return "break"
        self.commandline.bind('<Return>', on_commandline_return)  
        self.commandline.bind('<Up>', on_commandline_up)
        self.commandline.bind('<Down>', on_commandline_down)
        
        # ボタンパネル
        self.buttons = []
        def addbutton(parent, **kwargs):
            b = ttk.Button(parent, **kwargs)
            self.buttons.append(b)
            return b
        
        self.frames = []
        def addframe(parent, **kwargs):
            f = ttk.Frame(parent, **kwargs)
            self.frames.append(f)
            return f

        btnpanel = addframe(self.frame)
        btnpanel.grid(column=1, row=0, rowspan=2, sticky="new", padx=5)
        btnunredo = addframe(btnpanel)
        btnunredo.pack(side=tk.TOP, fill=tk.X, pady=2)
        b = addbutton(btnunredo, text=u"◀", command=lambda:launcher.rollback_command_history(1), width=4)
        b.pack(side=tk.LEFT, fill=tk.X, padx=1)
        b = addbutton(btnunredo, text=u"▶", command=lambda:launcher.rollback_command_history(-1), width=4)
        b.pack(side=tk.RIGHT, fill=tk.Y, padx=1)
        b = addbutton(btnpanel, text=u"ファイル入力...", command=launcher.input_filepath)
        b.pack(side=tk.TOP, fill=tk.X, pady=2)
        b = addbutton(btnpanel, text=u"作業ディレクトリ...", command=launcher.change_cd_dialog)
        b.pack(side=tk.TOP, fill=tk.X, pady=2)
        #b = tk.Button(btnpanel, text=u"テーマ", command=app.reset_screen, relief="groove")
        #b.pack(side=tk.TOP, fill=tk.X, pady=2)
        b = addbutton(btnpanel, text=u"終了", command=app.exit)
        b.pack(side=tk.TOP, fill=tk.X, pady=2)
        
        # ログウィンドウ
        #self.log = tk.scrolledtext.ScrolledText(self.frame, wrap="word", font="TkFixedFont")
        self.log = tk.Text(self.frame, wrap="word", font="TkFixedFont", relief="solid")
        self.log.grid(column=0, row=1, sticky="news", padx=5) #  columnspan=2, 
        #self.log['font'] = ('consolas', '12')
        self.log.configure(state='disabled')
        self.log.tag_configure("hyper", underline=1)
        self.log.tag_bind("hyper", "<Enter>", lambda e: self.hyper_enter(e))
        self.log.tag_bind("hyper", "<Leave>", lambda e: self.hyper_leave(e))
        self.log.tag_bind("hyper", "<Double-Button-1>", lambda e: self.hyper_click(e, app))
        
        tk.Grid.columnconfigure(self.frame, 0, weight=1)
        tk.Grid.rowconfigure(self.frame, 1, weight=1)
    
        # フレームを除去       
        #self.root.overrideredirect(True)
        theme = GreenShellTheme()
        theme.apply(self)
    
    # ログの操作
    def insert_log(self, msg):        
        if msg.tag == "hyper":
            dbtag = self.hyperlinks.add(msg.argument("link"))
            tags = (msg.argument("linktag") or "hyper", "hyperlink{}".format(dbtag))
        else:
            tags = (msg.tag or "message",)
        
        self.log.configure(state='normal')
        
        self.log.insert("end", msg.text, tags)
        if not msg.argument("nobreak", False):
            self.log.insert("end", "\n")
            
        self.log.configure(state='disabled')
        self.log.yview_moveto(1)
        
        # 復元用に記録する
        if not msg.argument("norecord", False):
            self.logmsgdump.append(msg)
        
    def update_log(self, ui):
        ui.handle_queued_message()
        self.log.after(100, self.update_log, ui)

    def reset_log(self, ui):
        ui.discard_queued_message()
        self.log.configure(state='normal')
        self.log.delete(1.0, tk.END)
        self.log.configure(state='disabled')
    
    def take_logdump(self, ui):
        def handler():
            dump = self.logmsgdump
            self.logmsgdump = []
            ui.add_command_log_history(dump)
        self.log.after(102, handler)
    
    def rollback_log(self, msgdump):
        self.log.configure(state='normal')        
        self.log.delete(1.0, tk.END)
        for msg in msgdump:
            msg.set_argument("norecord", True)
            self.insert_log(msg)
        self.log.configure(state='disabled')
        
    # ハイパーリンク
    def hyper_enter(self, event):
        self.log.config(cursor="hand2")

    def hyper_leave(self, event):
        self.log.config(cursor="")

    def hyper_click(self, event, app):
        tags = self.log.tag_names(tk.CURRENT)
        for tag in tags:
            if tag.startswith("hyperlink"):
                break
        else:
            return
        key = int(tag[len("hyperlink"):])
        link = self.hyperlinks.resolve(key)
        if link is not None:
            app.open_hyperlink(link)

    #
    # 入力欄
    #
    def wait_input(self):
        """
        プロセススレッドから呼び出される。
        入力終了イベント発生まで待機する
        """
        self.event_inputend.clear()
        self.inputwaiting = True
        self.event_inputend.wait() # 待機...
        self.inputwaiting = False
        # テキストボックスの最新の中身を取得する
        text = self.lastinput
        self.lastinput = None
        return text
    
    def finish_input(self, text):
        """ 入力完了を通知する """
        self.lastinput = text
        self.event_inputend.set()
    
    def replace_input_text(self, text): 
        """ 入力文字列を代入する """
        self.commandline.delete(1.0, "end")
        self.commandline.insert(1.0, text)
        
    def insert_input_text(self, text):
        """ 入力文字列をカーソル位置に挿入する """
        self.commandline.insert("insert", text)
    
    def pop_input_text(self):
        """ 入力文字列を取り出しクリアする """
        text = self.commandline.get(1.0, tk.END)
        self.commandline.delete(1.0, tk.END)
        return text.rstrip() # 改行文字が最後に付属する?
    
    def run(self):
        self.root.mainloop()
    
    def destroy(self):
        self.root.destroy()
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
#
#
if __name__ == "__main__":
    from machaon.sample import launch_sample_app
    launch_sample_app("tk")
    
    
        
    

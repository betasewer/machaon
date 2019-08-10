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
        self.app.print_title()
        self.screen.update_log(self)
    
    # 入力を取得
    def get_input(self, instr):
        instr += " >>> "
        self.app.message(instr, nobreak=True)
        inputtext = self.screen.wait_input()
        self.app.print_message(AppMessage(inputtext, "input"))
        return inputtext
    
    # コマンドを実行する
    def invoke_command(self, cmdstr):
        tim = datetime.datetime.now().strftime("%Y-%m-%d|%H:%M.%S")
        self.app.message_em("[{}] >>> ".format(tim), nobreak=True)
        self.post_message(AppMessage(cmdstr, "input"))
        self.app.command_process(cmdstr, threading=True)
    
    # コマンド欄を実行する
    def execute_command_input(self):
        text = self.screen.pop_input_text()
        if self.screen.inputwaiting:
            self.screen.finish_input(text)
        else:
            self.add_command_history(text)
            self.invoke_command(text)
        
    # コマンド履歴への追加
    def add_command_history(self, command):
        self._cmdhistory.append(command)
        self._curhistory = len(self._cmdhistory)
    
    def rollback_command_history(self, d):
        if len(self._cmdhistory)==0:
            return
        index = self._curhistory - d
        if index<0 or len(self._cmdhistory)<=index:
            return
        cmd = self._cmdhistory[index]
        self._curhistory = index
        self.screen.replace_input_text(cmd)
    
    def show_command_history(self):
        self.app.message("<< 履歴 >>")
        for i, his in enumerate(self._cmdhistory):
            row = "{} | {}".format(i, his)
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
    
    def on_exit(self):
        self.screen.finish_input("") # 入力待ち状態を解消する
        self.screen.destroy()
        
        
        
#
#
#
class tkLauncherScreen():
    def __init__(self):
        super().__init__()
        # コンソールの色指定
        self.colors = {
            "background" : "#000000",
            "insbackground" : "#00FF00",
            "message" : "#FFFFFF",
            "message_em" : "#00FF00",
            "warning" : "#FF8800",
            "error" : "#FF4444",
            "hyperlink" : "#0088FF",
            "userinput" : "#FFFF00",
        }
        
        # ルートウィジェット
        self.root = tkinter.Tk()
        self.commandline = None
        self.log = None

        # 入力終了イベント＆終了時のテキスト
        self.inputwaiting = False
        self.event_inputend = Event()
        self.lastinput = None
        
        self.hyperlinks = HyperlinkDatabase()
    
    # UIの配置と初期化
    def init_screen(self, app, launcher):
        self.root.title(app.title)
        self.root.geometry("900x200")
        self.root.protocol("WM_DELETE_WINDOW", app.exit)
    
        # コマンド入力欄
        self.commandline = tk.Entry(self.root, relief="solid", font="TkTextFont", 
            bg=self.colors["background"], fg=self.colors["message"],
            insertbackground=self.colors["insbackground"]
        )
        self.commandline.grid(column=0, row=0, sticky="ew", padx=5)
        self.commandline.focus_set()
        self.commandline.bind('<Return>', lambda e:launcher.execute_command_input())
        self.commandline.bind('<Up>', lambda e:launcher.rollback_command_history(1))
        self.commandline.bind('<Down>', lambda e:launcher.rollback_command_history(-1))
        
        # ボタンパネル
        btnpanel = tk.Frame(self.root)
        btnpanel.grid(column=1, row=0, rowspan=2, sticky="new", padx=5)
        b = tk.Button(btnpanel, text=u"ファイル入力...", command=launcher.input_filepath, relief="groove")
        b.pack(side=tk.TOP, fill=tk.X, pady=2)
        b = tk.Button(btnpanel, text=u"作業ディレクトリ...", command=launcher.change_cd_dialog, relief="groove")
        b.pack(side=tk.TOP, fill=tk.X, pady=2)
        b = tk.Button(btnpanel, text=u"画面クリア", command=app.reset_screen, relief="groove")
        b.pack(side=tk.TOP, fill=tk.X, pady=2)
        b = tk.Button(btnpanel, text=u"テーマ", command=app.reset_screen, relief="groove")
        b.pack(side=tk.TOP, fill=tk.X, pady=2)
        b = tk.Button(btnpanel, text=u"ABOUT", command=app.reset_screen, relief="groove")
        b.pack(side=tk.TOP, fill=tk.X, pady=2)
        b = tk.Button(btnpanel, text=u"終了", command=app.exit, relief="groove")
        b.pack(side=tk.TOP, fill=tk.X, pady=2)
        
        # ログウィンドウ
        self.log = tk.scrolledtext.ScrolledText(self.root, wrap="word", font="TkFixedFont")
        self.log.grid(column=0, row=1, sticky="news", padx=5) #  columnspan=2, 
        #self.log['font'] = ('consolas', '12')
        self.log.configure(state='disabled', background=self.colors["background"])
        self.log.tag_configure("message", foreground=self.colors["message"])
        self.log.tag_configure("message_em", foreground=self.colors["message_em"])
        self.log.tag_configure("warn", foreground=self.colors["warning"])
        self.log.tag_configure("error", foreground=self.colors["error"])
        self.log.tag_configure("input", foreground=self.colors["userinput"])
        self.log.tag_configure("hyper", foreground=self.colors["hyperlink"], underline=1)
        self.log.tag_bind("hyper", "<Enter>", lambda e: self.hyper_enter(e))
        self.log.tag_bind("hyper", "<Leave>", lambda e: self.hyper_leave(e))
        self.log.tag_bind("hyper", "<Double-Button-1>", lambda e: self.hyper_click(e, app))
        
        tk.Grid.columnconfigure(self.root, 0, weight=1)
        tk.Grid.rowconfigure(self.root, 1, weight=1)
    
        # フレームを除去       
        #self.root.overrideredirect(True)
    
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
        
    def update_log(self, ui):
        ui.handle_queued_message()
        self.log.after(100, self.update_log, ui)

    def reset_log(self, ui):
        ui.discard_queued_message()
        self.log.configure(state='normal')
        self.log.delete(1.0, tk.END)
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
        self.commandline.delete(0, "end")
        self.commandline.insert(0, text)
        
    def insert_input_text(self, text):
        """ 入力文字列をカーソル位置に挿入する """
        self.commandline.insert("insert", text)
    
    def pop_input_text(self):
        """ 入力文字列を取り出しクリアする """
        text = self.commandline.get()
        self.commandline.delete(0, "end")
        return text
    
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
  

    
    
        
    

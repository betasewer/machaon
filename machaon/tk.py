#!/usr/bin/env python3
# coding: utf-8

import os
import subprocess
import glob
import copy
import queue
import datetime
from threading import Event
from typing import Tuple, Sequence, List

import tkinter as tk
import tkinter.filedialog
import tkinter.scrolledtext
import tkinter.ttk as ttk

from machaon.app import App, AppMessage, BasicCUI
from machaon.command_launcher import CommandLauncher

import codecs

#
#
#
class tkApp(App):
    def __init__(self, title):
        super().__init__(title, tkScreen(), CommandLauncher(self))
        self.launcher.syscommand_help()
        self.launcher.syscommand_cls()
        self.launcher.syscommand_cd()
        self.reset_screen()
        
    def print_message(self, msg):
        # メッセージはすべてキュー
        self.ui.queue_message(msg)
    
    def reset_screen(self):
        self.ui.reset_log() # 全て削除
        self.print_title()
        self.ui.update_log()
    
    def get_input(self, instr):
        instr += " >>> "
        self.message(instr, nobreak=True)
        inputtext = self.ui.wait_input()
        self.print_message(AppMessage(inputtext, "input"))
        return inputtext
    
    def invoke_command(self, cmdstr):
        tim = datetime.datetime.now().strftime("%Y-%m-%d|%H:%M.%S")
        self.message_em("[{}] >>> ".format(tim), nobreak=True)
        self.print_message(AppMessage(cmdstr, "input"))
        self.command_process(cmdstr, threading=True)
    
    def on_exit_command(self, procclass):
        self.message_em("実行終了\n")
    
    def on_exit(self):
        self.ui.finish_input("") # 入力待ち状態を解消する
        
        
#
#
#
class tkScreen(BasicCUI):
    def __init__(self):
        super().__init__()
        self.app = None
        
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
        
        self._cmdhistory = []
        self._curhistory = 0
        
        # 入力終了イベント＆終了時のテキスト
        self.inputwaiting = False
        self.event_inputend = Event()
        self.lastinput = None
        
        self.hyperlinks = HyperlinkDatabase()
    
    #
    def init_with_app(self, app):
        self.app = app
        
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
        self.commandline.bind('<Return>', lambda event:self.execute_input())
        self.commandline.bind('<Up>', lambda event:self.input_from_history(1))
        self.commandline.bind('<Down>', lambda event:self.input_from_history(-1))
        
        # ボタンパネル
        btnpanel = tk.Frame(self.root)
        btnpanel.grid(column=1, row=0, rowspan=2, sticky="new", padx=5)
        b = tk.Button(btnpanel, text=u"ファイル入力...", command=self.input_filepath, relief="groove")
        b.pack(side=tk.TOP, fill=tk.X, pady=2)
        b = tk.Button(btnpanel, text=u"作業ディレクトリ...", command=self.change_cd_dialog, relief="groove")
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
        self.log.tag_bind("hyper", "<Enter>", self._hyper_enter)
        self.log.tag_bind("hyper", "<Leave>", self._hyper_leave)
        self.log.tag_bind("hyper", "<Double-Button-1>", self._hyper_click)
        
        tk.Grid.columnconfigure(self.root, 0, weight=1)
        tk.Grid.rowconfigure(self.root, 1, weight=1)
    
        # フレームを除去       
        #self.root.overrideredirect(True)
    
    # ログウィンドウにメッセージを出力
    def message_handler(self, msg):
        self.insert_log(msg)

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
        
    def update_log(self):
        self.handle_queued_message()
        self.log.after(100, self.update_log)

    def reset_log(self):
        self.discard_queued_message()
        self.log.configure(state='normal')
        self.log.delete(1.0, tk.END)
        self.log.configure(state='disabled')
        
    # ハイパーリンク
    def _hyper_enter(self, event):
        self.log.config(cursor="hand2")

    def _hyper_leave(self, event):
        self.log.config(cursor="")

    def _hyper_click(self, event):
        tags = self.log.tag_names(tk.CURRENT)
        for tag in tags:
            if tag.startswith("hyperlink"):
                break
        else:
            return
        key = int(tag[len("hyperlink"):])
        link = self.hyperlinks.resolve(key)
        if link is not None:
            self.app.open_hyperlink(link)

    def show_hyperlink_database(self):
        for l in self.hyperlinks.loglines():
            self.app.message(l)

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
        self.event_inputend.wait()
        self.inputwaiting = False
        # テキストボックスの最新の中身を取得する
        text = self.lastinput
        self.lastinput = None
        return text
    
    def finish_input(self, text):
        """ 入力完了を通知する """
        self.lastinput = text
        self.event_inputend.set()
    
    def execute_input(self):
        """ コマンド欄の文字列を処理する """
        text = self.commandline.get()
        self.commandline.delete(0, "end") # クリア
        if self.inputwaiting:
            self.finish_input(text)
        else:
            # コマンド履歴への追加
            self._cmdhistory.append(text)
            self._curhistory = len(self._cmdhistory)
            # コマンドとして実行
            self.app.invoke_command(text)
    
    # ダイアログからファイルパスを入力
    def input_filepath(self, *filters:Tuple[str, str]):
        filepath = tkinter.filedialog.askopenfilename(filetypes = filters, initialdir = self.app.get_current_dir())
        self.commandline.insert("insert", "{}".format(filepath))
        
    def input_dirpath(self):
        path = tkinter.filedialog.askdirectory(initialdir = self.app.get_current_dir())
        self.commandline.insert("insert", "{}".format(path))
        
    def input_from_history(self, d):
        if len(self._cmdhistory)==0:
            return
        index = self._curhistory - d
        if index<0 or len(self._cmdhistory)<=index:
            return
        cmd = self._cmdhistory[index]
        self.commandline.delete(0, "end")
        self.commandline.insert(0, cmd)
        self._curhistory = index
    
    def show_history(self):
        self.app.message("<< 履歴 >>")
        for i, his in enumerate(self._cmdhistory):
            row = "{} | {}".format(i, his)
            self.app.message(row)
        
    def set_inputlogging(self, b=True):
        self.inputlogging = b
    
    def change_cd_dialog(self):
        path = tkinter.filedialog.askdirectory(initialdir = self.app.get_current_dir())
        self.app.invoke_command("cd {}".format(path))
    
    def run_mainloop(self):
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
  

    
    
        
    

#!/usr/bin/env python3
# coding: utf-8
import os
from machaon.app import BasicCUI, App, ExitApp
from machaon.command_launcher import CommandLauncher
from machaon.cui import reencode

#
#
#
class ShellUI(BasicCUI):
    def __init__(self, encoding, textwidth=None, maxlinecount=None):
        self.encoding = encoding
        self.preftxtwidth = textwidth
        self.maxlinecount = maxlinecount
        
    def message_handler(self, msg):    
        text = self.printing_text(msg.text, collapse=False)
        if msg.tag=="error":
            text = "!!!{}".format(text)
        elif msg.tag=="warn":
            text = "?..{}".format(text)
            
        nobreak = msg.argument("nobreak", False)
        self.printer(text, nobreak=nobreak)

    def printing_text(self, s, collapse=False):
        if not isinstance(s, str):
            s = str(s)
        if collapse:
            s = self.collapse_text(s)
        if self.encoding is None:
            return s
        else:
            return reencode(s, self.encoding, "replace")
    
    def check_textwidth(self, count):
        if self.preftextwidth is None:
            return True
        return count <= self.preftextwidth
    
    def check_linecount(self, count):
        if self.maxlinecount is None:
            return True
        return count <= self.maxlinecount
    
    #
    # 以下をオーバーライドしてUIをカスタマイズする
    #
    def printer(self, text, **options):
        end = "\n"
        if options["nobreak"]:
            end = ""
        print(text, end=end)
        
    def clear_screen(self):
        os.system('clear')
        
    def scroll_screen(self, index):
        pass
    
    def get_input(self, instr):
        return input(instr)
        
    def destroy(self):
        pass

#
#
#
class WinShellUI(ShellUI):
    def __init__(self):
        super().__init__(encoding="cp932", textwidth=67, maxlinecount=200)

    def clear_screen(self):
        os.system('cls')

#
#
#
class BasicShellApp(App):
    def __init__(self, title, ui):
        super().__init__(title, ui, CommandLauncher(self))
        self.launcher.syscommand_help()
        self.launcher.syscommand_cls()
        self.launcher.syscommand_cd()
        self.launcher.syscommand_exit()
        self.reset_screen()
        
    def on_exit_command(self, procclass):
        self.message("")
    
    def on_exit(self):
        pass
    
    def mainloop(self):
        loop = True
        while loop:
            nextcmd = self.launcher.pop_next_command()
            if nextcmd is None:
                nextcmd = self.ui.get_input(">> ")
            
            if not nextcmd:
                if self.launcher.command_exit("--ask") is ExitApp:
                    break
                else:
                    continue

            ret = self.command_process(nextcmd, threading=False)
            if ret is ExitApp:
                break

# 環境で自動判別する
# def ShellApp():
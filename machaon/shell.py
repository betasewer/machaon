#!/usr/bin/env python3
# coding: utf-8
import os
from machaon.app import BasicCUI, App, ExitApp
from machaon.command_launcher import CommandLauncher
from machaon.cui import reencode, collapse_text

#
#
#
class ShellUI(BasicCUI):
    def __init__(self, encoding, textwidth=None, maxlinecount=None):
        self.encoding = encoding
        self.preftextwidth = textwidth
        self.maxlinecount = maxlinecount
        self.launcher = None
        self.app = None

    def init_with_app(self, app):
        self.app = app
        self.launcher = CommandLauncher(app)
            
    def get_launcher(self):
        return self.launcher

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
            s = collapse_text(s, self.preftextwidth)
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
    
    def printer(self, text, **options):
        end = "\n"
        if options.get("nobreak", False):
            end = ""
        print(text, end=end)
        
    def clear(self):
        os.system('clear')
        
    def get_input(self, instr=None):
        if instr is None:
            instr = ">> "
        else:
            instr += " >> "
        return input(instr)
        
    def reset_screen(self):
        self.clear()
        self.app.print_title()
    
    def run_mainloop(self):
        loop = True
        while loop:
            nextcmd = self.launcher.pop_next_command()
            if nextcmd is None:
                nextcmd = self.get_input()
            
            if not nextcmd:
                if self.launcher.command_exit("--ask") is ExitApp:
                    break
                else:
                    continue

            ret = self.app.exec_command(nextcmd, threading=False)
            if ret is ExitApp:
                break

    def on_exit_command(self, procclass):
        self.printer("")
    
    def on_exit(self):
        pass
            
#
#
#
class WinShellUI(ShellUI):
    def __init__(self):
        super().__init__(encoding="cp932", textwidth=67, maxlinecount=200)

    def clear(self):
        os.system('cls')


# 環境で自動判別する
# def ShellApp():
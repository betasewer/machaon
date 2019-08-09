#!/usr/bin/env python3
# coding: utf-8

import argparse
import glob
from collections import defaultdict  
         
#
# 各アプリはこれを継承する
#
class Processor:
    _command_interface = None

    def __init__(self, app):
        self.app = app
        self.lastresult = None # 

    # 処理の本体：任意の引数
    def init_process(self):
        pass
    
    def process_target(self, target) -> bool: # True/None 成功 / False 中断・失敗
        raise NotImplementedError()
    
    def exit_process(self):
        pass
    
    # 処理が最後まで終わらなかったか？
    def failed(self):
        return self.lastresult is False
        
    #
    # クラス定義後に実行
    #
    @classmethod
    def init_argparser(cls, pser):
        pass
        
    @classmethod
    def setup_argparser(cls, custom_parser=None, args=None):
        if custom_parser is None:
            args = args or {}
            if "prog" not in args:
                args["prog"] = cls.__name__
            cmdparser = CommandParser(**args)
            cls._command_interface = cmdparser
            cls.init_argparser(cls._command_interface)
        else:
            cmdparser = custom_parser()
            cls._command_interface = cmdparser
        return cmdparser is not None
        
    @classmethod
    def get_argparser(cls):
        return cls._command_interface
    
    # 
    @classmethod
    def generates(cls, app, commandstr=None):
        if cls._command_interface is None:
            if not cls.setup_argparser(): # 初回生成時に存在しなければデフォルト引数でパーサを構築
                raise Exception("Failed to setup argparser")
            
        argmap = cls._command_interface.parse_args(commandstr, app)
        if argmap is None:
            return 
        
        #
        # プロセスを生成。
        #
        proc = cls(app)
        if False is proc.init_process(*argmap[InitArg]):
            return
        
        #
        # 先頭引数の処理
        #
        targetargs = argmap[TargetArg]
        if len(targetargs)==0:
            yield ProcessStarter(proc)
        else:
            target = targetargs[0]
            args = targetargs[1:]
            if isinstance(target, list):
                for tg in target:
                    yield ProcessStarter(proc, tg, *args)
            else:
                yield ProcessStarter(proc, target, *args)
                
        #
        proc.exit_process(*argmap[ExitArg])
        

    @classmethod
    def help(cls, app):
        if cls._command_interface is None:
            raise Exception()
        cls._command_interface.help(app.message_io())
    
    @classmethod
    def get_desc(cls):
        return getattr(cls, "__desc__", cls.__name__)
    
        
#
#
#
class ProcessStarter:
    def __init__(self, proc, target=None, *args):
        self.proc = proc
        self.target = target
        self.args = args
        
    def start(self):
        targs = []
        if self.target is not None:
            targs.append(self.target)
        result = self.proc.process_target(*targs, *self.args)
        self.proc.lastresult = result
        return result
    
    def get_target(self):
        return self.target


    
#
InitArg = 0
TargetArg = 1
ExitArg = 2
FilepathArg = 0x10
    
#
# argparseを継承しいくつかの挙動を書き換えている。
#
class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        self.parent = kwargs.pop("parentparser")
        super().__init__(*args, **kwargs)
        
    def exit(self, status=0, message=None):
        raise ArgumentParserExit(status, message)

    def error(self, message):
        raise BadCommand(message)
        
    def print_usage(self, file=None):
        self.parent.push_parser_message(self.format_usage())
    
    def print_help(self, file=None):
        self.parent.push_parser_message(self.format_help())
        
#
class ArgumentParserExit(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message

#
class BadCommand(Exception):
    def __init__(self, error):
        self.error = error

       
#
# argparseをラップする
#
class CommandParser:
    #
    # __init__(["targets"], ("--template","-t"), ...)
    #
    def __init__(self, **kwargs):
        kwargs["parentparser"] = self
        self.argp = ArgumentParser(**kwargs)
        self.argnames = []
        self._dispargs = False
        self._parsermsgs = []
       
    # argparse.add_argumentの引数に加え、以下を指定可能：
    #  files = True/False ファイルパス/globパターンを受け入れ、ファイルパスのリストに展開する
    def add_arg(self, methodtype, *args, **kwargs):
        isfile = kwargs.pop("files", False)
        if isfile:
            kwargs["nargs"] = "+"
            methodtype |= FilepathArg

        act = self.argp.add_argument(*args, **kwargs)
        if any(x for (_,x) in self.argnames if x == act.dest):
            return
        self.argnames.append((methodtype, act.dest))
        
    def init_arg(self, *args, **kwargs):
        self.add_arg(InitArg, *args, **kwargs)
        
    def target_arg(self, *args, **kwargs):
        self.add_arg(TargetArg, *args, **kwargs)
    
    def exit_arg(self, *args, **kwargs):
        self.add_arg(ExitArg, *args, **kwargs)
    
    # 引数解析
    def split_query(self, q):
        splitting = True
        parts = []
        for ch in q:
            if splitting and ch.isspace():
                if parts[-1] == "--":
                    parts[-1] = ""
                    splitting = False
                elif len(parts)>0 and len(parts[-1])>0:
                    parts.append("")
            else:
                if len(parts)==0:
                    parts.append("")
                parts[-1] += ch
        return parts
    
    def parse_args(self, commandstr=None, app=None):
        argmap = defaultdict(list)
        
        if self.argp is None:
            raise ValueError()
        
        if commandstr is None:
            commands = None
        else:
            commands = self.split_query(commandstr)
    
        queue = self.new_parser_message_queue()
        try:
            values = self.argp.parse_args(commands)
        except ArgumentParserExit as e:
            queue.printout(app.message_io())
            return None
        except Exception as e:
            queue.printout(app.message_io())
            raise e

        for typ, name in self.argnames:
            value = getattr(values, name, None)
            if typ & FilepathArg:
                paths = []
                for fpath in value:
                    fpath = app.abspath(fpath)
                    globs = glob.glob(fpath)
                    if len(globs)>0:
                        paths.extend(globs)
                    else:
                        paths.append(fpath)
                value = paths
            argmap[typ&0xF].append(value)
        
        if self._dispargs:
            for funcname, args in self._handler_previews(argmap):
                print("{}({})".format(funcname, ", ".join([str(x) for x in args])))
            print("")
                
        return argmap

    # メッセージ
    def help(self, io):
        queue = self.new_parser_message_queue()
        self.argp.print_help()
        queue.printout(io)
        
    def new_parser_message_queue(self):
        self._parsermsgs = ParserMessageQueue()
        return self._parsermsgs
        
    def push_parser_message(self, msg):
        self._parsermsgs.push(msg)
    
    # デバッグ用
    def disp_signatures(self):
        d = defaultdict(list)
        for mtype, argname in self.argnames:
            d[mtype&0x0F].append(argname)
            
        for funcname, args, in self._handler_previews(d):
            print("{}({})".format(funcname, ", ".join(args)))
            
    def disp_args(self):
        self._dispargs = True
        
    def _handler_previews(self, argmap):
        funcnames = {
            InitArg : "init_process",
            TargetArg : "process_target",
            ExitArg : "exit_process"
        }
        for mtype, args in argmap.items():
            funcname = funcnames[mtype]
            yield funcname, ["self"] + args
    
#
class ParserMessageQueue():
    def __init__(self):
        self.lines = []
    
    def push(self, line):
        self.lines.append(line)
    
    def printout(self, io=None):
        for l in self.lines:
            if io:
                io.write(l+"\n")
            else:
                print(l)
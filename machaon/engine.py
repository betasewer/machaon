#!/usr/bin/env python3
# coding: utf-8
import argparse
import glob
from collections import defaultdict  
from itertools import product
from typing import Sequence
    
#
# ########################################################
#  Command Parser
# ########################################################
#
InitArg = 0
TargetArg = 1
ExitArg = 2
PositTargetArg = 5 # 1+4
FilepathArg = 0x10
JoinListArg = 0x20
    
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
class CommandParser():
    __debugdisp__ = False
    #
    # __init__(["targets"], ("--template","-t"), ...)
    #
    def __init__(self, **kwargs):
        kwargs["parentparser"] = self
        self.argp = ArgumentParser(**kwargs)
        self.argnames = []
        self._parsermsgs = None
        self._compoptions = CompoundOptions()
        self._compoptions.add_option("h")
        self.enable_compound_options = True
       
    # argparse.add_argumentの引数に加え、以下を指定可能：
    #  files = True/False ファイルパス/globパターンを受け入れ、ファイルパスのリストに展開する
    def add_arg(self, argtype, *names, **kwargs):
        isfile = kwargs.pop("files", False)
        if isfile:
            kwargs["nargs"] = "+"
            argtype |= FilepathArg
        
        cstopt = kwargs.pop("const_option", None)
        if cstopt:
            kwargs["action"] = "store_const"
            kwargs["const"] = cstopt
        
        apcstopt = kwargs.pop("append_const_option", None)
        if apcstopt:
            kwargs["action"] = "append_const"
            kwargs["const"] = apcstopt
        
        remopt = kwargs.pop("remainder", False)
        if remopt:
            kwargs["nargs"] = argparse.REMAINDER
            argtype |= JoinListArg

        act = self.argp.add_argument(*names, **kwargs)
        #if (methodtype&TargetArg)>0 and len(names)>0 and not names[0].startswith("-"):
        #    self.argnames.append((methodtype|PositTargetArg, act.dest))
        if not any(x for (_,x) in self.argnames if x == act.dest):
            self.argnames.append((argtype, act.dest))

        # trie
        for name in names:
            if name.startswith("--"):
                pass
            elif name.startswith("-"):
                self._compoptions.add_option(name[1:])
        
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
                if len(parts)>0:
                    if parts[-1] == "--":
                        parts[-1] = ""
                        splitting = False
                    elif len(parts[-1])>0:
                        parts.append("")
            else:
                if len(parts)==0:
                    parts.append("")
                parts[-1] += ch
        return parts
    
    #
    def parse_args(self, commandarg, commandoption=""):
        # 抱合語的オプションの展開
        expandedopts = []
        if self.enable_compound_options:
            expandedopts = self._compoptions.expand(commandoption)
        if not expandedopts and commandoption:
            expandedopts.append(commandoption)

        # コマンド候補を一つずつためす
        results = []
        bad = None
        for expandedopt in expandedopts:
            # クエリの分割
            commands = [*self.split_query(commandarg), *self.split_query(expandedopt)]
            # パーサーによる解析
            self.new_parser_message_queue()
            try:
                parsedargs = self.argp.parse_args(commands)
                # 引数の構築
                expandedcmd = " ".join(commands)
                res = CommandParserResult(expandedcmd)
                for argtype, name in self.argnames:
                    value = getattr(parsedargs, name, None)
                    if argtype&JoinListArg:
                        value = " ".join(value)
                    res.add_arg(argtype, name, value)
                results.append(res)
            except ArgumentParserExit as e:
                expandedcmd = " ".join(commands)
                results.append(CommandParserResult(expandedcmd, messages=self._parsermsgs))
            except BadCommand as b:
                bad = b
                pass
            except Exception as e:
                raise e
            
        if bad is not None:
            raise bad
        return results
    
    # 
    def get_description(self):
        return self.argp.description or ""
    
    def get_prog(self):
        return self.argp.prog or ""

    def get_help(self):
        queue = self.new_parser_message_queue()
        self.argp.print_help()
        return queue
        
    def new_parser_message_queue(self):
        self._parsermsgs = []
        return self._parsermsgs
        
    def push_parser_message(self, msg):
        self._parsermsgs.append(msg)

#
#
#
class CommandParserResult():
    def __init__(self, expandedcmd, *, argvalues=None, messages=None):
        self.expandedcmd = expandedcmd
        self.messages = messages
        self.argvalues = argvalues
        self.argmap = defaultdict(dict)
        self.target_filepath_arg = None
        
    def get_expanded_command(self):
        return self.expandedcmd
    
    def has_message(self):
        return True if self.messages else False
    
    def get_messages(self):
        return self.messages
        
    def add_arg(self, argtype, name, value):
        if argtype&FilepathArg:
            self.target_filepath_arg = value
        else:
            self.argmap[argtype&0xF][name] = value
    
    def get_init_args(self):
        return self.argmap[InitArg]
    
    def get_target_args(self):
        return self.argmap[TargetArg]
    
    def get_multiple_targets(self):
        if self.target_filepath_arg:
            return self.target_filepath_arg
        return None
    
    def get_exit_args(self):
        return self.argmap[ExitArg]

    # パス引数を展開する
    def expand_filepath_arguments(self, app):
        if self.target_filepath_arg:
            paths = []
            for fpath in self.target_filepath_arg:
                fpath = app.abspath(fpath)
                globs = glob.glob(fpath)
                if len(globs)>0:
                    paths.extend(globs)
                else:
                    paths.append(fpath)
            self.target_filepath_arg = paths
    
    #
    def preview_handlers(self, io):
        funcnames = {
            InitArg : "init_process",
            TargetArg : "process_target",
            ExitArg : "exit_process"
        }
        for argtype, args in self.argmap.items():
            io.write("{}({})".format(funcnames[argtype], ", ".join(["self"] + [str(x) for x in args])))

#
# ###############################################################
#　　抱合語的オプション文字列を解析する
# ###############################################################
#
class CompoundOptions:
    def __init__(self, allow_multiple_option=False):
        self.trie = {}
        self._allow_multiple_option = allow_multiple_option
    
    def add_option(self, name):
        d = self.trie
        for ch in name+" ":
            if ch == " ":
                d["$$"] = True
                break
            elif ch not in d:
                d[ch] = {}
            d = d[ch]
        
    #
    def expand(self, optionstr):            
        sprouts = [] # tree, begpos
        def add_new_sprout(tree, begin):
            if sprouts and sprouts[-1][0] is None:
                sprouts[-1] = [tree, begin]
            else:
                sprouts.append([tree, begin])
        
        def grow_sprout(tree, ch):
            if ch in tree:
                # grow sprout
                return tree[ch]
            else:
                # kill sprout
                return None
        ranges = []
        
        i = 0
        loop = True
        while loop:
            if i == len(optionstr):
                loop = False
                ch = None
            else:
                ch = optionstr[i]
                if ch.isspace():
                    loop = False

            add_new_sprout(self.trie, i)
            
            # 苗木をたどる
            firstlen = len(sprouts)
            for si in range(firstlen):
                spr = sprouts[si]
                tree = spr[0]
                if tree is None:
                    continue
                    
                if "$$" in tree:
                    begin = spr[1]
                    ranges.append((begin, i))                    
                    if len(tree) > 1:
                        add_new_sprout(tree, begin)
                    spr[0] = None
                else:
                    spr[0] = grow_sprout(tree, ch)
            
            # 途中で追加された苗木をたどる
            for si in range(firstlen, len(sprouts)):
                spr = sprouts[si]
                spr[0] = grow_sprout(spr[0], ch)
            
            i = i + 1
                
        # オプション文字列の可能な全ての組み合わせを導出する
        righties = defaultdict(list)
        for r in ranges:
            _, end = r
            righties[r] = [(rbeg, _) for (rbeg, _) in ranges if end <= rbeg]
            
        combis = defaultdict(list)
        for r in ranges:
            rset = tuple(righties[r])
            combis[rset].append(r)
        
        lines = []
        for rangeline in product(*combis.values()):
            line = []
            disallow = False
            start = 0
            end = None
            for beg, end in rangeline:
                if start<beg:
                    line.append(optionstr[start:beg])
                option = "-" + optionstr[beg:end]
                if not self._allow_multiple_option and option in line:
                    disallow = True
                    break
                line.append(option)
                start = end
            if disallow:
                continue
            rest = optionstr[end:].strip()
            if rest:
                line.append(rest)
            lines.append(line)
        
        return [" ".join(x) for x in lines]

#
# ###############################################################
#  CommandLauncher
# ###############################################################
#
# 文字列から対応するコマンドを見つけ出す
#
class CommandEngine:
    def __init__(self, app):
        self.app = app
        self.commandsets = []
        self.lastparsefail = None
        self.prefix = ""
        
    def install_commands(self, commandset):
        self.commandsets.append(commandset)
    
    def command_sets(self):
        return self.commandsets
    
    def set_command_prefix(self, prefix):
        self.prefix = prefix

    # コマンドを解析する
    def parse_command(self, commandhead, commandtail):
        self.lastparsefail = None

        # 文字列が示すコマンドエントリを選び出す
        possible_commands = [] # (entry, reststr)
        for cmdset in self.commandsets:
            matches = cmdset.match(commandhead)
            possible_commands.extend(matches)
            if self.prefix:
                matches = cmdset.match(self.prefix + commandhead)
                possible_commands.extend(matches)
        
        # オプションと引数を解析し、全ての可能なコマンド解釈を生成する
        possible_entries = []
        for commandentry, commandoptions in possible_commands:
            process = commandentry.process
            spirit = self.app.access_spirit(process.get_bound_app())
            
            # 引数コマンドを解析
            possible_syntaxes = []
            process.load_lazy_describer(spirit)
            try:
                possible_syntaxes = process.run_argparser(commandtail, commandoptions)
            except BadCommand as b:
                self.lastparsefail = (process, b.error)
            
            # 可能性のある解釈として追加
            for parseresult in possible_syntaxes:                
                possible_entries.append((process, spirit, parseresult))

        return possible_entries
    
    # 
    def get_last_process_parse_fail(self):
        if self.lastparsefail is None:
            return None, None
        return self.lastparsefail # process, error

    #
    def test_command_head(self, commandhead):
        for cmdset in self.commandsets:
            if cmdset.match(commandhead):
                return True
        return False
        
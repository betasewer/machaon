#!/usr/bin/env python3
# coding: utf-8
import sys
import argparse
import glob
from collections import defaultdict  
from itertools import product
from typing import Sequence

         

#
# 各アプリクラスを格納する
#
"""
def __init__(self, app):
    self.app = app

def init_process(self):
    pass

def process_target(self, target) -> bool: # True/None 成功 / False 中断・失敗
    raise NotImplementedError()

def exit_process(self):
    pass
"""

#
# ###################################################################
#  process class / function
# ###################################################################
#
class BasicProcess():
    def __init__(self, argp, bindapp, lazyargdescribe):
        self.argparser = argp
        self.bindapp = bindapp
        self.lazyargdescribe = lazyargdescribe
    
    def load_lazy_describer(self, app):
        if self.lazyargdescribe is not None:
            self.lazyargdescribe(app, self.argparser)
            self.lazyargdescribe = None

    def get_argparser(self):
        return self.argparser
    
    def run_argparser(self, app, commandstr):
        return self.argparser.parse_args(commandstr, app)
    
    def help(self, app):
        self.argparser.help(app.message_io())
    
    def get_prog(self):
        return self.argparser.get_prog()
    
    def get_description(self):
        return self.argparser.get_description()
    
    def get_bound_app(self):
        return self.bindapp

#
class ProcessClass(BasicProcess):
    def __init__(self, klass, argp, bindapp=None, lazyargdescribe=None):
        super().__init__(argp, bindapp, lazyargdescribe)
        self.klass = klass
        
    # 
    def generate_instances(self, spirit, argmap):
        # プロセスを生成
        proc = self.klass(spirit)
        if hasattr(proc, "init_process"):
            if False is proc.init_process(*argmap[InitArg]):
                return
        
        # 先頭引数の処理
        posittargets = argmap[PositTargetArg]
        if len(posittargets)==0:
            withtarget = False
            target = None
        else:
            withtarget = True
            target = posittargets[0] 
        targetargs = posittargets[1:] + argmap[TargetArg]

        if isinstance(target, list):
            for tg in target:
                yield ProcessInstance(proc.process_target, tg, targetargs, withtarget)
        else:
            yield ProcessInstance(proc.process_target, target, targetargs, withtarget)
                
        # 後処理
        if hasattr(proc, "exit_process"):
            proc.exit_process(*argmap[ExitArg])


#
class ProcessFunction(BasicProcess):
    def __init__(self, fn, argp, bindapp=None, bindargs=None, lazyargdescribe=None):
        super().__init__(argp, bindapp, lazyargdescribe)
        self.fn = fn
        self.bindargs = bindargs or ()

    def generate_instances(self, spirit, argmap):
        # 束縛引数
        args = []
        if self.bindapp is not None:
            args.append(spirit)
        args.extend(self.bindargs)
        args.extend(argmap[PositTargetArg]+argmap[TargetArg])

        yield ProcessInstance(self.fn, None, args, withtarget=False)

#
#  Process Function + Instance + parsed-arguments
#
class ProcessInstance():
    def __init__(self, targetfn, target, args, withtarget):
        self.targetfn = targetfn
        self.target = target
        self.args = args
        self.withtarget = withtarget
        self.last_invoked_result = None 
        
    def start(self):
        target = []
        if self.withtarget:
            target.append(self.target)
        result = self.targetfn(*target, *self.args)
        self.last_invoked_result = result
        return result
    
    def has_target(self):
        return self.withtarget
    
    def get_target(self):
        return self.target
        
    # 処理が最後まで終わらなかったか？
    def failed(self):
        return self.last_invoked_result is False
        
#
# ###################################################################
#  command and command package
# ###################################################################
#
auxiliary_command = 1
hidden_command = 2

# process + command keyword
class CommandEntry():
    def __init__(self, process, keywordset, commandtype):
        self.process = process
        self.keywords = keywordset # 展開済みのキーワード
        self.commandtype = commandtype

    def match(self, target):
        for keyword in self.keywords:
            if target.startswith(keyword):
                rest = target[len(keyword):]
                return rest
        return None
    
    def get_keywords(self):
        return self.keywords
        
    def get_description(self):
        return self.process.get_description()
    
    def get_bound_app(self):
        return self.process.bindapp

#
#
#
class CommandSet:
    def __init__(self, prefixes, entries, *, description=""):
        self.entries = entries
        self.prefixes = prefixes
        self.description = description
        
    def match(self, target):
        m = []
        if self.prefixes:
            hit = None
            for pfx in self.prefixes:
                if target.startswith(pfx):
                    hit = pfx
                    break
            if hit is None:
                return m
                
            target = target[len(pfx):]
            if target.startswith("."):
                target = target[1:]
        
        for e in self.entries:
            rest = e.match(target)
            if rest is None:
                continue
            m.append((e, rest))
        return m
    
    def get_description(self):
        return self.description
    
    def get_prefixes(self):
        return self.prefixes
    
    def get_entries(self):
        return self.entries
    
    def display_entries(self, *, forcehidden=False):
        entries = []
        for x in sorted(self.entries, key=lambda x: x.commandtype):
            if not forcehidden and x.commandtype == hidden_command:
                continue
            entries.append(x)
        return entries

#
# build CommandEntry
#
class CommandBuilder():
    def __init__(self, 
        process=None, *, 
        prog=None, 
        bindargs=None, 
        bindapp=None,
        custom_command_parser=None, 
        auxiliary=False,
        hidden=False,
        **kwargs
    ):
        self.process = process
        self.prog = prog
        self.bindargs = bindargs
        self.bindapp = bindapp
        self.auxiliary = auxiliary
        self.hidden = hidden
        self.cmdinitargs = kwargs
        self.cmdargs = []
        self.custom_cmdparser = custom_command_parser
        self.lazy_describers = []
        
        # コマンド自体に定義された初期化処理があれば呼ぶ
        if hasattr(process, "describe"):
            describer = CommandBuilder.BuildDescriber(self)
            process.describe(describer)

    #
    class BuildDescriber():
        def __init__(self, builder):
            self.builder = builder
            
        def describe(self, 
            prog=None, 
            bindargs=None, 
            bindapp=None,
            custom_command_parser=None, 
            auxiliary=None,
            hidden=None,
            **kwargs
        ):
            if prog is not None:
                self.builder.prog = prog
            if bindargs is not None:
                self.builder.bindargs = bindargs
            if bindapp is not None:
                self.builder.bindapp = bindapp
            if custom_command_parser is not None:
                self.builder.custom_cmd_parser = custom_command_parser
            if auxiliary is not None:
                self.builder.auxiliary = auxiliary
            if hidden is not None:
                self.builder.hidden = hidden
            self.builder.cmdinitargs.update(kwargs)
            return self.builder
            
        def lazy_describe(self, fn):
            self.builder.lazy_describe(fn)
    
    #
    def __getitem__(self, commandstr):
        def _command(**kwargs):
            cmdtype, *cmds = commandstr.split()
            self.cmdargs.append((cmdtype, cmds, kwargs))
            return self
        return _command
    
    #
    def lazy_describe(self, fn):
        self.lazy_describers.append(fn)

    #
    def build_entry(self, app, setname, keywords):
        firstkwd, *kwds = keywords

        prog = self.prog
        if prog is None:
            prog = "{}.{}".format(setname, firstkwd) if setname else firstkwd

        # 引数パーサの作成       
        if self.custom_cmdparser is not None:
            argp = self.custom_cmdparser(prog=prog, **self.cmdinitargs)
        else:
            argp = CommandParser(prog=prog, **self.cmdinitargs)

        for cmdtype, cmds, kwa in self.cmdargs:
            if cmdtype == "target":
                argp.target_arg(*cmds, **kwa)
            elif cmdtype == "init":
                argp.init_arg(*cmds, **kwa)
            elif cmdtype == "exit":
                argp.exit_arg(*cmds, **kwa)
            else:
                raise ValueError("Undefined command type '{}'".format(cmdtype))
        
        # bindapp
        bindapp = self.bindapp
        if bindapp is True:
            from machaon.app import App
            bindapp = App
        elif not bindapp:
            bindapp = None
        else:
            app.touch_spirit(bindapp) # Appクラスを登録
            
        # 遅延コマンド初期化処理を実行する
        if self.lazy_describe:
            def lazy_arg_describe(boundapp, argp):
                for lzydesc in self.lazy_describers:
                    lzydesc(boundapp, argp)
        else:
            lazy_arg_describe = None
        
        # プロセスインスタンス
        if isinstance(self.process, type):
            proc = ProcessClass(self.process, argp, bindapp=bindapp, lazyargdescribe=lazy_arg_describe)
        else:
            proc = ProcessFunction(self.process, argp, bindapp=bindapp, bindargs=self.bindargs, lazyargdescribe=lazy_arg_describe)
        
        # 特殊なコマンドの種別
        typecode = 0
        if self.auxiliary: 
            typecode = auxiliary_command
        if self.hidden: 
            typecode = hidden_command

        return CommandEntry(proc, (firstkwd, *kwds), typecode)

#
#
#
class CommandPackage():
    def __init__(self, *, description, bindapp=True):
        self.desc = description
        self.bindapp = bindapp
        self.builders = []
    
    def __getitem__(self, commandstr):
        def _command(builder=None, *, process=None, **kwargs):
            cmds = commandstr.split()

            if builder is None:
                if process is None:
                    raise ValueError("CommandPackage: 'builder' or 'process' argument is required")
                builder = CommandBuilder(process, **kwargs)

            if self.bindapp is not None:
                builder.bindapp = self.bindapp

            self.builders.append([cmds, builder])
            return self
        return _command
    
    #
    def build_commands(self, app, command_prefixes, exclude=()):
        if not command_prefixes:
            setname = None
        else:
            setname = command_prefixes[0]

        entries = []
        for cmds, builder in self.builders:
            if len(cmds)==0 or cmds[0] in exclude:
                continue

            entry = builder.build_entry(app, setname, cmds)
            entries.append(entry)
        
        return CommandSet(command_prefixes, entries, description=self.desc)
    
    # パッケージをまとめる
    def annex(self, *others):
        p = CommandPackage(description=self.desc, bindapp=self.bindapp)
        p.builders = self.builders
        for other in others:
            p.builders += other.builders
        return p

#
#       
#
def describe_command(
    process,
    *,
    prog=None, 
    bindargs=None, 
    custom_command_parser=None, 
    auxiliary=False,
    hidden=False,
    **kwargs
):
    return CommandBuilder(
        process, 
        prog=prog, bindargs=bindargs, custom_command_parser=custom_command_parser,
        auxiliary=auxiliary, hidden=hidden,
        **kwargs
    )

#
def describe_command_package(
    description,
    bindapp=True
):
    return CommandPackage(
        description=description,
        bindapp=bindapp
    )


    
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
    def add_arg(self, methodtype, *names, **kwargs):
        isfile = kwargs.pop("files", False)
        if isfile:
            kwargs["nargs"] = "+"
            methodtype |= FilepathArg
        
        cstopt = kwargs.pop("const_option", None)
        if cstopt:
            kwargs["action"] = "store_const"
            kwargs["const"] = cstopt

        act = self.argp.add_argument(*names, **kwargs)
        if (methodtype&TargetArg)>0 and len(names)>0 and not names[0].startswith("-"):
            self.argnames.append((methodtype|PositTargetArg, act.dest))
        elif not any(x for (_,x) in self.argnames if x == act.dest):
            self.argnames.append((methodtype, act.dest))

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
    def parse_args(self, commandstr, app=None):
        # 抱合語的オプションの展開
        expandedcmds = []
        if self.enable_compound_options:
            possibles = self._compoptions.expand(commandstr)
            expandedcmds = possibles or [commandstr] # TODO:解釈を選べるようにする
        else:
            expandedcmds.append(commandstr)

        # コマンド候補を一つずつためす
        argvalues = None
        bad = None
        expandedcmd = ""
        for expandedcmd in expandedcmds:
            # クエリの分割
            commands = self.split_query(expandedcmd)
            # パーサーによる解析
            self.new_parser_message_queue()
            try:
                argvalues = self.argp.parse_args(commands)
                if argvalues:
                    break
            except ArgumentParserExit as e:
                return None, expandedcmd
            except BadCommand as b:
                bad = b
                pass
            except Exception as e:
                raise e
        else:
            if bad is not None:
                raise bad
            return None, commandstr

        #
        argmap = defaultdict(list)
        for typ, name in self.argnames:
            value = getattr(argvalues, name, None)
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
        
        if CommandParser.__debugdisp__:
            for funcname, args in self._handler_previews(argmap):
                print("{}({})".format(funcname, ", ".join([str(x) for x in args])))
            print("")
        
        return argmap, expandedcmd
    
    # 
    def get_description(self):
        return self.argp.description or ""
    
    def get_prog(self):
        return self.argp.prog or ""

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
    
    def print_parser_message(self, app, **msgoptions):
        if self._parsermsgs is None:
            raise Exception("")
        self._parsermsgs.printout(app.message_io(**msgoptions))
    
    # デバッグ用
    def disp_signatures(self):
        d = defaultdict(list)
        for mtype, argname in self.argnames:
            d[mtype&0x0F].append(argname)
            
        for funcname, args, in self._handler_previews(d):
            print("{}({})".format(funcname, ", ".join(args)))
            
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
class CommandLauncher:
    def __init__(self, app):
        self.app = app
        self.lastcmdstr = ""
        self.nextcmdstr = None
        self.commandsets = []
        
    def install_commands(self, commandset:CommandSet):
        self.commandsets.append(commandset)
    
    # コマンドを処理
    def translate_command(self, commandstr=""):
        spl = commandstr.split(maxsplit=1) # 空白で区切る
        cmdstr = spl[0] if len(spl)>0 else ""
        argstr = spl[1] if len(spl)>1 else ""
        cmdparts = cmdstr # 

        # コマンド文字列が示すエントリを選び出す
        m = [] # (entry, reststr)
        for cmdset in self.commandsets:
            m.extend(cmdset.match(cmdparts))

        if len(m)==0:
            return None, None
        elif len(m)>1:
            # 完全一致しているものを優先する
            # TODO: ひとつを選ばせる
            m = sorted(m, key=lambda x:len(x[1]))[0:1]
        
        # 抱合的オプション
        chosenentry = m[0][0]
        if len(m[0][1])>0:
            argstr = m[0][1] + " " + argstr

        return (chosenentry, argstr.strip())
    
    # self.app.launcher.redirect_command("")
    def redirect_command(self, command: str):
        self.nextcmdstr = command
    
    def pop_next_command(self):
        nextcmd = None
        if self.nextcmdstr is not None:
            nextcmd = self.nextcmdstr
            self.nextcmdstr = None
        return nextcmd
    
    def command_sets(self):
        return self.commandsets


    


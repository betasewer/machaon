#!/usr/bin/env python3
# coding: utf-8
from typing import Sequence

from machaon.process import ProcessTargetClass, ProcessTargetFunction, Spirit
from machaon.engine import CommandParser

#
# ###################################################################
#  command and command package
# ###################################################################
#
auxiliary_command = 1
hidden_command = 2

# process + command keyword
class CommandEntry():
    def __init__(self, process_target, keywordset, commandtype):
        self.process_target = process_target
        self.keywords = keywordset # 展開済みのキーワード
        self.commandtype = commandtype

    def match(self, target):
        for keyword in self.keywords:
            if target.startswith(keyword):
                rest = target[len(keyword):]
                return rest
        return None
    
    def get_target(self):
        return self.process_target
    
    def get_keywords(self):
        return self.keywords

    def get_description(self):
        return self.process_target.get_description()
        

# set of CommandEntry
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
        target=None, *, 
        prog=None, 
        args=None, 
        spirit=None,
        custom_command_parser=None, 
        auxiliary=False,
        hidden=False,
        **kwargs
    ):
        self.target = target
        self.prog = prog
        self.args = args
        self.spirit = spirit
        self.auxiliary = auxiliary
        self.hidden = hidden
        self.cmdinitargs = kwargs
        self.cmdargs = []
        self.custom_cmdparser = custom_command_parser
        self.lazy_describers = []
        
        # コマンド自体に定義された初期化処理があれば呼ぶ
        if hasattr(target, "describe"):
            describer = CommandBuilder.BuildDescriber(self)
            target.describe(describer)

    #
    class BuildDescriber():
        def __init__(self, builder):
            self.builder = builder
            
        def describe(self, 
            prog=None, 
            args=None, 
            spirit=None,
            custom_command_parser=None, 
            auxiliary=None,
            hidden=None,
            **kwargs
        ):
            if prog is not None:
                self.builder.prog = prog
            if args is not None:
                self.builder.args = args
            if spirit is not None:
                self.builder.spirit = spirit
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
        def _command(**commandkwargs):
            cmdtype, *cmds = commandstr.split()
            self.cmdargs.append((cmdtype, cmds, commandkwargs))
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
        
        # spirit
        spirit = self.spirit
        if spirit is True:
            spirit = Spirit
        elif not spirit:
            spirit = None
        
        # 遅延コマンド初期化処理を実行する
        if self.lazy_describe:
            def lazy_arg_describe(boundspirit, argp):
                for lzydesc in self.lazy_describers:
                    lzydesc(boundspirit, argp)
        else:
            lazy_arg_describe = None
        
        # コマンドで実行する処理
        if isinstance(self.target, type):
            targ = ProcessTargetClass(self.target, argp, spirittype=spirit, lazyargdescribe=lazy_arg_describe)
        else:
            targ = ProcessTargetFunction(self.target, argp, spirittype=spirit, args=self.args, lazyargdescribe=lazy_arg_describe)
        
        # 特殊なコマンドの種別
        typecode = 0
        if self.auxiliary: 
            typecode = auxiliary_command
        if self.hidden: 
            typecode = hidden_command

        return CommandEntry(targ, (firstkwd, *kwds), typecode)

#
#
#
class CommandPackage():
    def __init__(self, *, description, spirit):
        self.desc = description
        self.spirit = spirit
        self.builders = []
    
    def __getitem__(self, commandstr):
        def _command(builder=None, *, target=None, **kwargs):
            cmds = commandstr.split()

            if builder is None:
                if target is None:
                    raise ValueError("CommandPackage: 'builder' or 'target' argument is required")
                builder = CommandBuilder(target, **kwargs)

            if self.spirit is not None and builder.spirit is None:
                builder.spirit = self.spirit

            self.builders.append([cmds, builder])
            return self
        return _command
    
    #
    def build_commands(self, app, command_prefixes):
        if not command_prefixes:
            setname = None
        else:
            setname = command_prefixes[0]

        entries = []
        for cmds, builder in self.builders:
            if len(cmds)==0:
                continue
            entry = builder.build_entry(app, setname, cmds)
            entries.append(entry)
        
        return CommandSet(command_prefixes, entries, description=self.desc)
    
    # パッケージをまとめて新しいパッケージに
    def annexed(self, *others):
        p = CommandPackage(description=self.desc, spirit=self.spirit)
        p.builders = self.builders
        for other in others:
            p.builders += other.builders
        return p
    
    # コマンドを除外して新しいパッケージに
    def excluded(self, *excludenames):
        p = CommandPackage(description=self.desc, spirit=self.spirit)
        for cmds, builder in self.builders:
            if cmds[0] in excludenames:
                continue
            p.builders.append((cmds, builder))
        return p

#
#       
#
def describe_command(
    target,
    *,
    prog=None, 
    args=None, 
    custom_command_parser=None, 
    auxiliary=False,
    hidden=False,
    **kwargs
):
    return CommandBuilder(
        target, 
        prog=prog, args=args, custom_command_parser=custom_command_parser,
        auxiliary=auxiliary, hidden=hidden,
        **kwargs
    )

#
def describe_command_package(
    description,
    spirit=True
):
    return CommandPackage(
        description=description,
        spirit=spirit
    )


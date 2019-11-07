#!/usr/bin/env python3
# coding: utf-8
from typing import Sequence

from machaon.process import ProcessClass, ProcessFunction
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
    def annex(self, *others):
        p = CommandPackage(description=self.desc, bindapp=self.bindapp)
        p.builders = self.builders
        for other in others:
            p.builders += other.builders
        return p
    
    # コマンドを除外して新しいパッケージに
    def excluded(self, *excludenames):
        p = CommandPackage(description=self.desc, bindapp=self.bindapp)
        for cmds, builder in self.builders:
            if cmds[0] in excludenames:
                continue
            p.builders.append((cmds, builder))
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


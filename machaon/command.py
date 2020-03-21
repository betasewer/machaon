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
normal_command = 0
auxiliary_command = 1
hidden_command = 2

# process + command keyword
class CommandEntry():
    def __init__(
        self, 
        keywords,
        prog=None, 
        description="",
        builder=None,
        commandtype=normal_command,
    ):
        self.target = None
        self.keywords = keywords # 展開済みのキーワード
        self.builder = builder
        self.prog = prog
        self.description = description
        self.commandtype = commandtype

    def match(self, target):
        for keyword in self.keywords:
            if target.startswith(keyword):
                rest = target[len(keyword):]
                return rest
        return None
    
    def load(self):
        if self.builder:
            process_target = self.builder.build_target(self)
            self.target = process_target
            self.builder = None
        return self.target
    
    def get_prog(self):
        return self.prog
    
    def get_keywords(self):
        return self.keywords

    def get_description(self):
        return self.description
    
    def is_hidden(self):
        return self.commandtype == hidden_command


# set of CommandEntry
class CommandSet:
    def __init__(self, name, prefixes, entries, *, description=""):
        self.name = name
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
    
    def get_name(self):
        return self.name
    
    def get_description(self):
        return self.description
    
    def get_prefixes(self):
        return self.prefixes
    
    def get_entries(self):
        return self.entries
    
    def display_entries(self, *, forcehidden=False):
        entries = []
        for x in sorted(self.entries, key=lambda x: x.commandtype):
            if not forcehidden and x.is_hidden():
                continue
            entries.append(x)
        return entries

#
# build CommandEntry
#
class CommandBuilder():
    def __init__(self, 
        target, 
        *, 
        from_module=None,
        prog=None, 
        description="",
        commandtype=normal_command,
        args=None, 
        spirit=None,
        custom_command_parser=None, 
        **kwargs
    ):
        self.target = target
        self.prog = prog
        self.description = description
        self.args = args
        self.spirit = spirit
        self.custom_cmdparser = custom_command_parser
        self.frommodule = from_module
        self.commandtype = commandtype
        self.cmdinitargs = kwargs

        self.cmdargs = []
        self.lazy_describers = []

        #
        if isinstance(target, str) and self.frommodule is None:
            raise ValueError("'target'に識別名(str)を指定した場合、'from_module'にモジュール名の指定が必要です")

    #
    def __getitem__(self, commandstr):
        def _command(**commandkwargs):
            cmdtype, *cmds = commandstr.split()
            self.cmdargs.append((cmdtype, cmds, commandkwargs))
            return self
        return _command

    #
    def describe(self, 
        args=None, 
        spirit=None,
        custom_command_parser=None, 
        **kwargs
    ):
        if args is not None:
            self.args = args
        if spirit is not None:
            self.spirit = spirit
        if custom_command_parser is not None:
            self.custom_cmd_parser = custom_command_parser
        self.cmdinitargs.update(kwargs)
        return self

    #
    def lazy_describe(self, fn):
        self.lazy_describers.append(fn)
    
    #
    #
    #
    def create_entry(self, keywords, setname=None):
        firstkwd, *_kwds = keywords

        prog = self.prog
        if prog is None:
            prog = "{}.{}".format(setname, firstkwd) if setname else firstkwd

        return CommandEntry(
            keywords,
            prog = prog,
            description = self.description, 
            builder = self,
            commandtype = self.commandtype
        )
    
    #
    #
    #
    def build_target(self, entry):
        prog = entry.get_prog()

        # コマンドをロードする
        target = self.target
        if isinstance(target, str):
            if isinstance(self.frommodule, str):
                import importlib
                mod = importlib.import_module(self.frommodule)
                member = getattr(mod, target, None)
                if member is None:
                    raise ValueError("コマンド'{}'のターゲット'{}'が見つかりません".format(prog, target))
                target = member
            
        # コマンド自体に定義された初期化処理があれば呼ぶ
        if hasattr(target, "describe"):
            target.describe(self)

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
        spirittype = self.spirit
        if spirittype is None:
            spirittype = Spirit
        
        # 遅延コマンド初期化処理を定義する
        if self.lazy_describers:
            def lazy_arg_describe(spirit, argparser):
                for lzydesc in self.lazy_describers:
                    lzydesc(spirit, argparser)
        else:
            lazy_arg_describe = None
        
        # コマンドで実行する処理
        if isinstance(target, type):
            targ = ProcessTargetClass(target, argp, spirittype=spirittype, lazyargdescribe=lazy_arg_describe)
        else:
            targ = ProcessTargetFunction(target, argp, spirittype=spirittype, args=self.args, lazyargdescribe=lazy_arg_describe)
        
        return targ
        


#
#
#
class CommandPackage():
    def __init__(self, name, *, description, spirit):
        self.name = name
        self.desc = description
        self.spirit = spirit
        self.builders = []

    def __getitem__(self, commandstr):
        def _command(builder=None, *, 
            target=None, 
            **kwargs
        ):
            cmds = commandstr.split()
            if builder is None:
                if target is None:
                    raise ValueError("CommandPackage: 'entry' or 'target' argument is required")
                builder = describe_command(target, **kwargs)

            if self.spirit is not None and builder.spirit is None:
                builder.spirit = self.spirit
            self.builders.append([cmds, builder])
            return self
        return _command
    
    #
    def create_commands(self, app, command_prefixes):
        if not command_prefixes:
            setname = None
        else:
            setname = command_prefixes[0]

        entries = []
        for cmds, builder in self.builders:
            if len(cmds)==0:
                continue
            entry = builder.create_entry(cmds, setname)
            entries.append(entry)
        
        return CommandSet(self.name, command_prefixes, entries, description=self.desc)
    
    # パッケージをまとめて新しいパッケージに
    def annexed(self, *others):
        p = CommandPackage(self.name, description=self.desc, spirit=self.spirit)
        p.builders = self.builders
        for other in others:
            p.builders += other.builders
        return p
    
    # コマンドを除外して新しいパッケージに
    def excluded(self, *excludenames):
        p = CommandPackage(self.name, description=self.desc, spirit=self.spirit)
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
    description="",
    prog=None, 
    spirit=None,
    args=None, 
    custom_command_parser=None, 
    auxiliary=False,
    hidden=False,
    from_module=None,
    **kwargs
):
    typecode = normal_command
    if auxiliary: 
        typecode = auxiliary_command
    if hidden: 
        typecode = hidden_command

    return CommandBuilder(
        target, 
        prog=prog, 
        description=description, 
        from_module=from_module,
        spirit=spirit,
        args=args, 
        commandtype=typecode,
        custom_command_parser=custom_command_parser,
        **kwargs
    )

#
def describe_command_package(
    package_name,
    description,
    spirit=None
):
    return CommandPackage(
        package_name,
        description=description,
        spirit=spirit
    )


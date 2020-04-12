#!/usr/bin/env python3
# coding: utf-8
from typing import Sequence

from machaon.process import ProcessTargetClass, ProcessTargetFunction, Spirit
from machaon.parser import CommandParser
from machaon.engine import CommandEntry, CommandSet

#
# ###################################################################
#  command and command package
# ###################################################################
#
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
        commandtype="normal",
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
            argp = CommandParser(prog=prog, description=self.description)

        for cmdtype, cmds, kwa in self.cmdargs:
            if cmdtype in ("target", "init", "exit"):
                kwa["methodtype"] = cmdtype
                argp.add_arg(*cmds, **kwa)
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
    typecode = "normal"
    if auxiliary: 
        typecode = "auxiliary"
    if hidden: 
        typecode = "hidden"

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


#!/usr/bin/env python3
# coding: utf-8
from typing import Sequence, Union

from machaon.engine import (
    CommandEntry, CommandSet, 
    NORMAL_COMMAND, INSTANT_COMMAND, HIDDEN_COMMAND
)

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
        spirit=None,
    ):
        self.target = target
        self.prog = prog
        self.description = description
        self.spirit = spirit
        self.frommodule = from_module
        self.commandtype = commandtype

        self.argdescs = []
        self.lazy_describers = []

    # 直前に実行されるコマンド初期化処理
    def lazy_describe(self, fn):
        self.lazy_describers.append(fn)
    
    #
    #
    #
    def create_entry(self, keywords, setkeyword=None):
        firstkwd, *_kwds = keywords

        prog = self.prog
        if prog is None:
            prog = "{}.{}".format(setkeyword, firstkwd) if setkeyword else firstkwd

        return CommandEntry(
            keywords,
            prog = prog,
            builder = self,
            commandtype = self.commandtype
        )
    
    def get_lazy_action_describer(self):
        if self.lazy_describers:
            def lazy_arg_describe(spirit, action):
                for lzydesc in self.lazy_describers:
                    lzydesc(spirit, action)
        else:
            lazy_arg_describe = None
        return lazy_arg_describe

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
                builder = describe_command(target, **kwargs)
                if builder.target is None:
                    raise ValueError("CommandPackage: 'entry' or 'target' argument is required")

            if self.spirit is not None and builder.spirit is None:
                builder.spirit = self.spirit
            self.builders.append([cmds, builder])
            return self
        return _command
    
    #
    def create_commands(self, app, command_prefixes):
        if not command_prefixes:
            setkwd = None
        else:
            setkwd = command_prefixes[0]

        entries = []
        for cmds, builder in self.builders:
            if len(cmds)==0:
                continue
            entry = builder.create_entry(cmds, setkwd)
            entries.append(entry)
        
        return CommandSet(self.name, command_prefixes, entries, description=self.desc)
    
    # パッケージをまとめて新しいパッケージに
    def annex(self, *others):
        p = CommandPackage(self.name, description=self.desc, spirit=self.spirit)
        p.builders = self.builders
        for other in others:
            p.builders += other.builders
        return p
    
    # コマンドを除外して新しいパッケージに
    def exclude(self, *excludenames):
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
    target=None,
    *,
    description="",
    prog=None, 
    spirit=None,
    construct_object=None,
    hidden=False,
    from_module=None,
):
    typecode = NORMAL_COMMAND
    if construct_object: 
        typecode = INSTANT_COMMAND
        if target is None:
            target = construct_object
    if hidden: 
        typecode = HIDDEN_COMMAND

    return CommandBuilder(
        target, 
        prog=prog, 
        description=description, 
        from_module=from_module,
        spirit=spirit,
        commandtype=typecode,
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


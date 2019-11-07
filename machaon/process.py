#!/usr/bin/env python3
# coding: utf-8
import sys
from typing import Sequence
import inspect

         
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
    
    def run_argparser(self, commandarg, commandoption=""):
        return self.argparser.parse_args(commandarg, commandoption)
    
    def get_help(self):
        return self.argparser.get_help()
    
    def get_prog(self):
        return self.argparser.get_prog()
    
    def get_description(self):
        return self.argparser.get_description()
    
    def get_bound_app(self):
        return self.bindapp

#
#
#
class ProcessClass(BasicProcess):
    def __init__(self, klass, argp, bindapp=None, lazyargdescribe=None):
        super().__init__(argp, bindapp, lazyargdescribe)
        self.klass = klass
        
        if hasattr(klass, "init_process"):
            self.init_invoker = ProcessInvoker(klass.init_process)
        else:
            self.init_invoker = None
        
        self.target_invoker = ProcessInvoker(klass.process_target)
            
        if hasattr(klass, "exit_process"):
            self.exit_invoker = ProcessInvoker(klass.exit_process)
        else:
            self.exit_invoker = None

    # 
    def generate_instances(self, spirit, parsedcommand):
        # プロセスを生成
        proc = self.klass(spirit)
        if self.init_invoker:
            if False is self.init_invoker.invoke(proc, **parsedcommand.get_init_args()):
                return
        
        # 先頭引数の処理
        targs = parsedcommand.get_target_args()
        multitarget = parsedcommand.get_multiple_targets()
        if multitarget:
            for a_target in multitarget:
                yield self.target_invoker.bind(proc, target=a_target, **targs)
        else:
            yield self.target_invoker.bind(proc, **targs)

        # 後処理
        if self.exit_invoker:
            self.exit_invoker.invoke(proc, **parsedcommand.get_exit_args())

#
#
#
class ProcessFunction(BasicProcess):
    def __init__(self, fn, argp, bindapp=None, bindargs=None, lazyargdescribe=None):
        super().__init__(argp, bindapp, lazyargdescribe)
        self.bindargs = bindargs or ()
        self.target_invoker = ProcessInvoker(fn)

    def generate_instances(self, spirit, parsedcommand):
        # 束縛引数
        args = []
        if self.bindapp is not None:
            args.append(spirit)
        args.extend(self.bindargs)
        yield self.target_invoker.bind(*args, **parsedcommand.get_target_args())
    
#
#
#
class ProcessInvoker:
    def __init__(self, fn, fnargnames=None, *args, **argmap):
        self.fn = fn
        self.fnargnames = fnargnames
        self.args = args
        self.argmap = argmap

        # inspectで引数名を取り出す
        if self.fnargnames is None:
            names = []
            sig = inspect.signature(self.fn)
            for _, p in sig.parameters.items():
                names.append(p.name)
            self.fnargnames = names
        
        self.last_not_found_args = []
    
    def bind(self, *args, **kwa):
        return ProcessInvoker(self.fn, self.fnargnames, *self.args, *args, **self.argmap, **kwa)
    
    def invoke(self, *args, **kwa):
        kwargs = {}
        kwargs.update(self.argmap)
        kwargs.update(kwa)
        
        self.last_not_found_args = []

        values = []
        values.extend(self.args)
        values.extend(args)
        for aname in self.fnargnames[len(values):]:
            if aname in kwargs:
                values.append(kwargs[aname])
            else:
                self.last_not_found_args.append(aname)
        
        return self.fn(*values)

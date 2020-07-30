from typing import DefaultDict, Any, List, Sequence, Dict, Tuple, Optional

import inspect
from collections import defaultdict

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
#  action class / function
# ###################################################################
#
class Action():
    def __init__(self, 
        prog, 
        description="", 
        spirittype=None, 
        lazyargdescribe=None, 
    ):
        self.prog = prog
        self.description = description
        self.spirittype = spirittype
        self.lazyargdescribe = lazyargdescribe
        self.argdefs: DefaultDict[str, List[ActionArgDef]] = defaultdict(list)
        self.resdefs: List[ActionResultDef] = []

    # 実行前に呼び出される
    def load(self, generic_spirit): # return Spirit
        spi = generic_spirit
        if self.spirittype:
            spi = self.spirittype(generic_spirit.app)
            spi.inherit(generic_spirit)
        
        if self.lazyargdescribe is not None:
            self.lazyargdescribe(spi, self)
            self.lazyargdescribe = None # 初回のロード時のみ発動する

        return spi
    
    def get_help(self):
        return "<Action.get_help not implemented yet>"
    
    def get_prog(self):
        return self.prog
    
    def get_description(self):
        return self.description

    def get_valid_labels(self):
        raise NotImplementedError()
    
    def get_inspection(self):
        raise NotImplementedError()
    
    def is_instant_action(self):
        return False

    #
    def add_argument(self, label, argname, typename, **kwargs):
        if not label:
            label = "target"
        elif label not in self.get_valid_labels(): 
            raise ValueError("'{}'はこのアクションの呼び出しタイミング名ではありません".format(label))
        a = ActionArgDef(argname, typename, **kwargs)
        self.argdefs[label].append(a)

    def find_argument(self, argname):
        for defs in self.argdefs.values():
            for d in defs:
                if d.name == argname:
                    return d
        return None

    def add_result(self, typename, **kwargs):
        r = ActionResultDef(typename, **kwargs)
        self.resdefs.append(r)
    
    def create_argument_parser_action(self, argname):
        d = self.find_argument(argname)
        if d is None:
            raise ValueError("コマンド'{}'の引数ではありません: {}".format(self.prog, argname))
    
        prog = "{}.{}".format(self.prog, argname)
        action = ObjectConstructorAction(d.typename, prog)
        return action

    #
    def invoke(self, invocation): # should return invocation
        raise NotImplementedError()
    
    #
    def prepare_arguments(self, label, invocations):
        # 引数を収集する
        kwargs = {}
        for argdef in self.argdefs[label]:        
            if argdef.is_parameter():
                kwargs[argdef.name] = invocations.pop_parameter()
            else:
                obj = invocations.pop_object(argdef.typename)
                if obj:
                    kwargs[argdef.name] = obj.value
        
        return kwargs
    
    #
    def invoke_function(self, label, invocations, invoker, preargs, kwargs):
        # 呼び出しを行なう
        this_inv = None
        if False: # argforeach
            raise NotImplementedError()
        else:
            this_inv = invoker.prepare(*preargs, **kwargs)
            invoker.invoke(this_inv)
            if not invocations.push_invocation_and_continue(label, this_inv):
                return False
        return True
    
    #
    def pick_result_objects(self, results):
        for rdef, r in zip(self.resdefs, results):
            yield rdef, r


#
#
#
class ActionClass(Action):
    def __init__(self, klass, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.klass = klass
        
        if hasattr(klass, "init_process"):
            self.init_invoker = FunctionInvoker(klass.init_process)
        else:
            self.init_invoker = None
        
        if hasattr(klass, "process_target"):
            self.target_invoker = FunctionInvoker(klass.process_target)
        else:
            raise TypeError("process_target")
        
        if hasattr(klass, "exit_process"):
            self.exit_invoker = FunctionInvoker(klass.exit_process)
        else:
            self.exit_invoker = None
    
    def get_valid_labels(self):
        labels = (
            ("init", self.init_invoker), 
            ("target", self.target_invoker),
            ("exit", self.exit_invoker)
        )
        return [x for (x,inv) in labels if inv is not None]
    
    def get_inspection(self):
        return "class", self.klass.__qualname__, self.klass.__module__

    # 
    def invoke(self, invocation):
        # プロセスを生成
        proc = self.klass(invocation.spirit)
        if self.init_invoker:
            kwargs = self.prepare_arguments("init", invocation)
            if not self.invoke_function("init", invocation, self.init_invoker, (proc,), kwargs):
                return invocation

        # メイン処理
        kwargs = self.prepare_arguments("target", invocation)
        if not self.invoke_function("target", invocation, self.target_invoker, (proc,), kwargs):
            return invocation

        # 後処理
        if self.exit_invoker:
            kwargs = self.prepare_arguments("exit", invocation)
            if not self.invoke_function("exit", invocation, self.exit_invoker, (proc,), kwargs):
                return invocation

        return invocation

#
#
#
class ActionFunction(Action):
    def __init__(self, fn, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_invoker = FunctionInvoker(fn)
    
    def get_valid_labels(self):
        return ["target"]
        
    def get_inspection(self):
        return "function", self.target_invoker.fn.__qualname__, self.target_invoker.fn.__module__

    def invoke(self, invocation):
        # 束縛引数
        preargs = [
            invocation.spirit
        ]
        
        # メイン処理
        kwargs = self.prepare_arguments("target", invocation)
        self.invoke_function("target", invocation, self.target_invoker, preargs, kwargs)
        return invocation

#
#
#
class ObjectConstructorAction(Action):
    def __init__(self, 
            typecode, 
            prog, 
            description=None
        ):
        if description is None:
            description = "Parse {}.".format(prog)
        super().__init__(prog, description, None, None)

        self.typecode = typecode
        self._parsefn_invoker = FunctionInvoker(ObjectConstructorAction._parser_function)
        self.add_result(typecode, help="Parsed value")
    
    def load(self, spirit):
        return spirit

    def is_instant_action(self):
        return True
        
    def get_valid_labels(self):
        return ["target"]
    
    def get_inspection(self):
        fn = ObjectConstructorAction._parser_function
        return "instant-parser-function", fn.__qualname__, fn.__module__
    
    # 型のパーサ関数をよびだす
    @staticmethod
    def _parser_function(ttraits, parameter):
        return ttraits.convert_from_string(parameter)

    def invoke(self, invocation):
        ttraits = invocation.get_object_desktop().get_type(self.typecode)

        # 束縛引数 - 型クラス＋かならずparameterをとる
        args = []
        args.append(ttraits)
        args.append(invocation.pop_parameter())
        
        # メイン処理
        self.invoke_function("target", invocation, self._parsefn_invoker, args, {})

        # 返り値オブジェクトを設定する
        result = invocation.get_last_result()
        if result is not None:
            if not isinstance(result, tuple):
                result = (result,)

            for resdef, resval in zip(self.resdefs, result):
                invocation.spirit.push_object(value=resval, typename=resdef.get_typename())
        
        return invocation

#
#
#
class ActionArgDef:
    def __init__(self, argname, typename, help=""):
        self.name = argname
        self.typename = typename
        self.help = help

    def get_name(self):
        return self.name
    
    def get_typename(self):
        return self.typename
    
    def is_parameter(self):
        return self.typename == "parameter"
    
    def get_help(self):
        return self.help

#
#
#
class ActionResultDef:
    def __init__(self, typename, help=""):
        self.typename = typename
        self.help = help

    def get_typename(self):
        return self.typename    

    def get_help(self):
        return self.help

#
#
#
class FunctionInvoker:
    def __init__(self, fn):
        self.fn = fn
        self.argnames = None # args, kwargs
        self.kwargvarname = None

        # inspectで引数名を取り出す
        names = []
        sig = inspect.signature(self.fn)
        for _, p in sig.parameters.items():
            if p.kind == inspect.Parameter.VAR_KEYWORD:
                self.kwargvarname = p.name
            elif p.kind == inspect.Parameter.VAR_POSITIONAL:
                pass
            else:
                names.append(p.name)
        self.argnames = names
    
    @property
    def fnqualname(self):
        # デバッグ用
        return self.fn.__qualname__
    
    #
    def prepare(self, *args, **kwargs):
        argmap = {}
        argmap.update(kwargs)

        values = []
        values.extend(args)

        paramnames = self.argnames[len(values):]
        remained_argnames = {k.replace("-","_"): k for k in argmap.keys()}
        missing_args = []
        for paramname in paramnames:
            if paramname in remained_argnames:
                valuekey = remained_argnames.pop(paramname)
                values.append(argmap[valuekey])
            else:
                missing_args.append(paramname)
            
        if missing_args:
            raise MissingArgumentError(self.fnqualname, missing_args)
        
        kwargs = {}
        if self.kwargvarname:
            for pname, aname in remained_argnames.items():
                if pname in argmap:
                    kwargs[pname] = argmap[aname]
            
            for pname in kwargs.keys():
                remained_argnames.pop(pname)

        unused_args = list(remained_argnames.values())
        
        #
        entry = InvocationEntry(values, kwargs)
        entry.set_arg_errors(missing_args, unused_args)
        return entry
    
    #
    def prepare_next_target(self, entry, **kwargs):
        entry = entry.clone()
        target_arg = kwargs["target"]
        if "target" in self.argnames:
            entry.args[self.argnames.index("target")] = target_arg
        else:
            raise ValueError("'target' argument not found")
        return entry
    
    #
    def invoke(self, invocation):
        from machaon.process import ProcessInterrupted

        # 関数を実行する
        result = None
        exception = None
        try:
            result = self.fn(*invocation.args, **invocation.kwargs)
        except ProcessInterrupted as e:
            raise e
        except Exception as e:
            exception = e

        invocation.set_result(result, exception)
        return invocation

#
class MissingArgumentError(Exception):
    def __init__(self, fnqualname, missings):
        self.fnqualname = fnqualname
        self.missings = missings

#
#
#
class InvocationEntry():
    def __init__(self, args, kwargs):
        self.args = args
        self.kwargs = kwargs
        self.result = None
        self.missing_args = []
        self.unused_args = []
        self.exception = None
    
    def clone(self):
        inv = InvocationEntry(self.args, self.kwargs)
        inv.result = self.result
        inv.missing_args = self.missing_args
        inv.unused_args = self.unused_args
        inv.exception = self.exception
        return inv

    def set_arg_errors(self, missing_args, unused_args):
        self.missing_args = missing_args
        self.unused_args = unused_args
    
    def set_result(self, result, exception):
        self.result = result
        self.exception = exception
    
    def is_failed(self):
        if self.exception:
            return True
        return False

    def is_init_failed(self):
        if self.exception:
            return True
        else:
            return self.result is False

#
#
#
class ActionInvocation:
    def __init__(self, spirit, parameter, objdesktop):
        self.spirit = spirit
        self.parameter: str = parameter
        self.objdesktop = objdesktop
        self.entries: DefaultDict[str, List[InvocationEntry]] = defaultdict(list)
        self.last_exception = None
    
    def get_object_desktop(self):
        return self.objdesktop
        
    def pop_object(self, typename):
        value = self.objdesktop.pick_by_type(typename)
        return value
    
    def pop_parameter(self):
        p = self.parameter
        self.parameter = None
        return p
    
    def push_invocation_and_continue(self, label: str, entry: InvocationEntry):
        self.entries[label].append(entry)
        if entry.is_failed():
            self.last_exception = entry.exception
            return False
        if label == "init" and entry.is_init_failed():
            self.last_exception = ActionInitFailed()
            return False
        return True
    
    def initerror(self, excep: BaseException):
        entry = InvocationEntry((), {})
        entry.set_result(None, excep)
        self.push_invocation_and_continue("init", entry)

    def get_entries_of(self, label):
        return self.entries[label]
    
    def get_last_result(self):
        if self.entries["target"]:
            return self.entries["target"][-1].result
        return None
    
    def arg_errors(self):
        for label in ("init", "target", "exit"):
            if label not in self.entries or not self.entries[label]:
                continue
            tail = self.entries[label][-1] # 同じラベルであればエラーも同一のはず
            yield label, tail.missing_args, tail.unused_args

    def get_last_exception(self):
        return self.last_exception

#
class ActionInitFailed(Exception):
    pass


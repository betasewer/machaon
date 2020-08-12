from typing import DefaultDict, Any, List, Sequence, Dict, Tuple, Optional

import inspect
from collections import defaultdict

from machaon.object.object import Object, ObjectValue
from machaon.object.importer import maybe_import_target, import_member

#
# 
#
class MissingArgumentError(Exception):
    def __init__(self, fnqualname, missings):
        self.fnqualname = fnqualname
        self.missings = missings
        
#
class InvocationFailed(Exception):
    def __init__(self, context):
        self.context = context


#
# ###################################################################
#  action class / function
# ###################################################################
#


"""
class __Action():
    def __init__(self):
        pass

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


class FunctionInvoker:
    def __init__(self, fn):
        self.fn = fn
        self.argnames = None # args, kwargs
        self.kwargvarname = None
        self.argdefaults = {}

        # inspectで引数名を取り出す
        names = []
        sig = inspect.signature(self.fn)
        for _, p in sig.parameters.items():
            if p.kind == inspect.Parameter.VAR_KEYWORD:
                self.kwargvarname = p.name
            elif p.kind == inspect.Parameter.VAR_POSITIONAL:
                pass
            else:
                defval = p.default
                if defval is not inspect.Parameter.empty:
                    self.argdefaults[p.name] = defval
                names.append(p.name)
        self.argnames = names
    
    @property
    def fnqualname(self):
        # デバッグ用
        return self.fn.__qualname__

    def prepare_next_target(self, entry, **kwargs):
        entry = entry.clone()
        target_arg = kwargs["target"]
        if "target" in self.argnames:
            entry.args[self.argnames.index("target")] = target_arg
        else:
            raise ValueError("'target' argument not found")
        return entry
"""
#
# target = method-name => ActionFunction
# target = python.xuthus.component.concat
#
def load_method_action(this_type, target, method):
    # 型定義のメソッドを取り出す
    typefn = None
    if not maybe_import_target(target):
        typefn = this_type.get_method_delegation(target)

    if typefn is not None:
        return typefn
    
    # Pythonのモジュールからロードする
    loaded = import_member(target)
    
    if hasattr(loaded, "describe_method"):
        # アクション自体に定義されたメソッド初期化処理を呼ぶ
        loaded.describe_method(method)
    
    if isinstance(loaded, type):
        callobj = loaded()
    else:
        callobj = loaded
    
    if not callable(callobj):
        raise ValueError("アクションとして無効です：{}".format(callobj))

    return callobj

#
#
#
class InvocationEntry():
    def __init__(self, args, kwargs):
        self.args = args
        self.kwargs = kwargs
        self.results = [] # ObjectValue
        self.missing_args = []
        self.unused_args = []
        self.exception = None
    
    def clone(self):
        inv = InvocationEntry(self.args, self.kwargs)
        inv.results = self.results
        inv.missing_args = self.missing_args
        inv.unused_args = self.unused_args
        inv.exception = self.exception
        return inv

    def push_result(self, typename, value):
        self.results.append(ObjectValue(typename, value))
    
    def get_first_result(self) -> Optional[ObjectValue]:
        if self.results:
            return self.results[0]
        return None

    def set_exception(self, exception):
        self.exception = exception
    
    def set_arg_errors(self, missing_args, unused_args):
        self.missing_args = missing_args
        self.unused_args = unused_args

    def is_failed(self):
        if self.exception:
            return True
        return False

#
#
#
class InvocationContext:
    def __init__(self, *, spirit=None, parameter=""):
        self.spirit = spirit
        self.parameter: str = parameter
        self.input_objects = ObjectDesktop()
        self.invocations: List[InvocationEntry] = []
        self._last_exception = None

    #def push_input_object(self, obj):
    #    self.input_objects.

    def get_self_object(self) -> Optional[Object]:
        return self.input_objects.pick_self()
        
    def get_selected_objects(self) -> Sequence[Object]:
        return self.input_objects.pick_selected()
    
    def get_selected_objects_typedict(self):
        objmap = defaultdict(list) # type: DefaultDict[str, List[Object]]
        for obj in self.get_selected_objects():
            objmap[obj.get_typename()].append(obj)
        return objmap
    
    def get_selected_objects_and_parameter(self, num):
        objs = []
        objs.extend(self.get_selected_objects())
        if len(objs) < num:
            objs.append(self.get_parameter_object())
        return objs

    def get_parameter(self) -> str:
        return self.parameter
    
    def get_parameter_object(self, name="parameter") -> Object:
        return Object(name, None, self.parameter)

    def push_invocation(self, entry: InvocationEntry):
        self.invocations.append(entry)
        if entry.is_failed():
            self._last_exception = entry.exception
    
    def get_last_invocation(self) -> Optional[InvocationEntry]:
        if self.invocations:
            return self.invocations[-1]
        return None
    
    def get_last_result(self) -> Optional[ObjectValue]:
        ent = self.get_last_invocation()
        if ent:
            return ent.get_first_result()
        return None
    
    def get_last_exception(self) -> Optional[Exception]:
        return self._last_exception
    
    def is_failed(self):
        return self._last_exception is not None

    def arg_errors(self):
        raise NotImplementedError()
        '''
        for label in ("init", "target", "exit"):
            if label not in self.entries or not self.entries[label]:
                continue
            tail = self.entries[label][-1] # 同じラベルであればエラーも同一のはず
            yield label, tail.missing_args, tail.unused_args
        '''

    def set_pre_invoke_error(self, excep: BaseException):
        entry = InvocationEntry((), {})
        entry.set_exception(excep)
        self.push_invocation(entry)
        
#
# datasetやformulaで値を評価するために呼ばれるコンテクスト
#
class MemberInvocationContext(InvocationContext):
    def __init__(self, objtype, objval):
        super().__init__(spirit=None, parameter="")
        self.push_input_object(Object("subject", objtype, objval))

    def get_evaluated_value(self):
        if self.is_failed():
            raise InvocationFailed(self)
        objval = self.get_last_result()
        return objval.value

#
#
# メソッドの実行
#
#
INVOCATION_NEGATE_RESULT = 0x1
INVOCATION_REVERSE_ARGS = 0x2

#
#
#
class BasicInvocation():
    def __init__(self, modifier):
        self.modifier = modifier

    def modifier_name(self):
        m = []
        if self.modifier & INVOCATION_REVERSE_ARGS:
            m.append("arg-reversed")
        if self.modifier & INVOCATION_NEGATE_RESULT:
            m.append("result-negated")
        if not m:
            m.append("straight")
        return " ".join(m)
    
    def invoke(self, invocations):
        # 引数とアクションを生成
        action, inventry = self.prepare_invoke(invocations)

        if self.modifier & INVOCATION_REVERSE_ARGS:
            inventry.reverse_args()

        # 実行
        from machaon.process import ProcessInterrupted
        result = None
        try:
            result = action(*inventry.args, **inventry.kwargs)
        except ProcessInterrupted as e:
            raise e
        except Exception as e:
            inventry.set_exception(e)
        
        # 返り値をまとめる
        if result is not None:
            self.result_invoke(result, inventry)
        
        if self.modifier & INVOCATION_NEGATE_RESULT:
            inventry.negate_result()
        
        # 格納
        invocations.push_invocation(inventry)
    
    #
    # これらをオーバーロードする
    #
    def prepare_invoke(self, invocations):
        raise NotImplementedError()
    
    def result_invoke(self, result, entry):
        raise NotImplementedError()
    
    def is_task(self):
        raise NotImplementedError()


#
# 型に定義されたメソッドの呼び出し 
#
class TypeMethodInvocation(BasicInvocation):
    def __init__(self, method, modifier=0):
        super().__init__(modifier)
        self.method = method

    def __str__(self):
        return "<TypeMethodInvocation '{}' {}>".format(self.method.get_name(), self.modifier_name())
    
    def is_task(self):
        return self.method.is_task()
        
    def get_result_typehint(self):
        return self.method.get_result_typecode()
    
    def prepare_invoke(self, invocations):
        # 引数をオブジェクトの集合から収集
        selfobj = invocations.get_self_object()
        if selfobj is None:
            raise ValueError("self object is not set")

        args = []
        if self.method.is_task():
            # Taskアクションにはspiritを渡す
            args.append(invocations.spirit)
        args.append(selfobj.value)

        # 仮引数の型を基準に収集する
        objmap = invocations.get_selected_objects_typedict()
        kwargs = {}
        for param in self.method.get_params():
            if param.is_parameter():
                kwargs[param.name] = invocations.get_parameter()
            else:
                if len(objmap[param.typename]) > 0:    
                    obj = objmap[param.typename].pop(0)
                    kwargs[param.name] = obj.value
                elif not param.is_required():
                    kwargs[param.name] = param.get_default()   
        
        # 実行
        entry = InvocationEntry(args, kwargs)
        action = self.method.load_action(selfobj.type)
        return action, entry

    def result_invoke(self, result, entry):
        # 返り値を設定する
        if isinstance(result, tuple):
            for definition, value in zip(self.method.results, result):
                entry.push_result(definition.typename, value)
        else:
            entry.push_result(self.method.results[0].typename, result)

#
# 定義のわからないメソッドを実行するたびに呼び出す
#
class InstanceMethodInvocation(BasicInvocation):
    def __init__(self, attrname, arity, modifier=0):
        super().__init__(modifier)
        self.attrname = attrname
        self.arity = arity
        if arity is not None and arity < 1:
            raise ValueError("Arity must be more than 0")

    def __str__(self):
        return "<InstanceMethodInvocation '{}' {}>".format(self.attrname, self.modifier_name())
    
    def is_task(self):
        return False

    def prepare_invoke(self, invocations):
        # 引数をオブジェクトの集合から収集
        selfobj = invocations.get_self_object()
        if selfobj is None:
            raise ValueError("self object is not set")
        
        # 値に定義されたメソッドを取得
        method = getattr(selfobj.value, self.attrname, None)
        if method is None:
            raise ValueError("")
        
        arity = self.arity
        if arity is None:
            sig = inspect.signature(method)
            arity = len(sig.parameters)
        
        # 決められた数の引数を、オブジェクト集合の上から順に取る
        args = []
        args.append(selfobj.value)
        args.extend([o.value for o in invocations.get_selected_objects_and_parameter(arity-1)])

        # 実行
        entry = InvocationEntry(args, {})
        return method, entry
    
    def result_invoke(self, result, entry):
        # 返り値を設定する
        entry.push_result(type(result), result)

#
# 定義のわからないメソッドを実行するたびに呼び出す
#
class StaticMethodInvocation(BasicInvocation):
    def __init__(self, function, arity, modifier=0):
        super().__init__(modifier)
        self.fn = function
        if arity is None:
            sig = inspect.signature(function)
            arity = len(sig.parameters)
        self.arity = arity

    def __str__(self):
        name = ".".join([self.fn.__module__, self.fn.__name__])
        return "<StaticMethodInvocation '{}' {}>".format(name, self.modifier_name())
    
    def is_task(self):
        return False

    def prepare_invoke(self, invocations):        
        # 決められた数の引数を、オブジェクト集合の上から順に取る
        arity = self.arity
        args = [o.value for o in invocations.get_selected_objects_and_parameter(arity)]

        # 実行
        entry = InvocationEntry(args, {})
        return self.fn, entry
    
    def result_invoke(self, result, entry):
        # 返り値を設定する
        entry.push_result(type(result), result)


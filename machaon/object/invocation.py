from typing import DefaultDict, Any, List, Sequence, Dict, Tuple, Optional, Union

import inspect
from collections import defaultdict

from machaon.object.type import Type, TypeModule
from machaon.object.object import Object, ObjectValue, ObjectCollection

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
class BadMethodInvocation(Exception):
    def __init__(self, name):
        self.name = name

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

    def push_result(self, typename: str, value: Any):
        self.results.append(ObjectValue(typename, value))
    
    def get_first_result(self) -> Optional[ObjectValue]:
        if self.results:
            return self.results[0]
        return None

    def set_exception(self, exception):
        self.exception = exception

    def is_failed(self):
        if self.exception:
            return True
        return False

#
#
#
class InvocationContext:
    def __init__(self, *, input_objects, type_module, spirit=None):
        self.type_module: TypeModule = type_module
        self.input_objects: ObjectCollection = input_objects # 外部のオブジェクト参照
        self.subject_object: Union[None, Object, Dict[str, Object]] = None  # 無名関数の引数とするオブジェクト
        self.local_objects: List[Object] = []                # メソッドの返り値を置いておく
        self.spirit = spirit
        self.invocations: List[InvocationEntry] = []
        self._last_exception = None
    
    def get_spirit(self):
        return self.spirit
    
    #
    def inherit(self):
        cxt = InvocationContext(input_objects=self.input_objects, type_module=self.type_module, spirit=self.spirit)
        return cxt

    # 
    def push_local_object(self, obj: Object):
        self.local_objects.append(obj)
    
    def top_local_object(self) -> Optional[Object]:
        if not self.local_objects:
            return None
        return self.local_objects[-1]

    def pop_local_object(self):
        if not self.local_objects:
            return
        self.local_objects.pop()

    def clear_local_objects(self) -> List[Object]:
        objs = self.local_objects
        self.local_objects = []
        return objs

    #
    def get_object(self, name) -> Optional[Object]:
        for x in self.input_objects.pick_by_name(name):
            return x.object
        return None
        
    def get_object_by_type(self, typename) -> Optional[Object]:
        for x in self.input_objects.pick_by_type(typename):
            return x.object
        return None

    def get_selected_objects(self) -> List[Object]:
        li = [] # type: List[Object]
        for x in self.input_objects.pick_all():
            if x.selected:
                li.append(x.object)
        return li

    def get_selected_objects_typedict(self):
        objmap = defaultdict(list) # type: DefaultDict[str, List[Object]]
        for x in self.input_objects.pick_all():
            if x.selected:
                obj = x.object
                objmap[obj.get_typename()].append(obj)
        return objmap
    
    def push_object(self, name: str, obj: Object):
        self.input_objects.push(name, obj)
    
    #
    def set_subject(self, subject: Union[Object, Dict[str, Object]]):
        if isinstance(subject, Object) or isinstance(subject, dict):
            self.subject_object = subject
        else:
            raise TypeError("subject Bad Type: " + str(subject))
    
    def clear_subject(self):
        self.subject_object = None
    
    def get_subject(self):
        return self.subject_object
        
    #    
    def get_type(self, typename) -> Optional[Type]:
        return self.type_module.get(typename, fallback=True)
        
    def new_type(self, typename) -> Type:
        return self.type_module.new(typename)

    #
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
        # コマンド解析の失敗など、呼び出す前に起きたエラーを格納する
        entry = InvocationEntry((), {})
        entry.set_exception(excep)
        self.push_invocation(entry)
        
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
        self.result_typehint = None

    def modifier_name(self):
        m = []
        if self.modifier & INVOCATION_REVERSE_ARGS:
            m.append("arg-reversed")
        if self.modifier & INVOCATION_NEGATE_RESULT:
            m.append("result-negated")
        if not m:
            m.append("straight")
        return " ".join(m)
    
    def invoke(self, context: InvocationContext, *args):
        # 引数とアクションを生成
        action, inventry = self.prepare_invoke(context, *args)

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
            typenames = self.get_result_typenames()
            if not isinstance(result, tuple):
                result = (result,)
            for i, value in enumerate(result):
                if isinstance(value, Object):
                    inventry.push_result(value.get_typename(), value.value)
                elif i<len(typenames):
                    inventry.push_result(typenames[i], value)
                else:
                    inventry.push_result(type(value).__name__, value)
        
        if self.modifier & INVOCATION_NEGATE_RESULT:
            inventry.negate_result()
        
        # 格納
        context.push_invocation(inventry)
    
    def set_result_typehint(self, typename: str):
        self.result_typehint = typename
        
    def get_result_typehint(self):
        return self.result_typehint
    
    #
    # これらをオーバーロードする
    #
    def prepare_invoke(self, context: InvocationContext, *args):
        raise NotImplementedError()
    
    def result_invoke(self, result, entry: InvocationEntry):
        # 返り値を設定する
        typename = type(result).__name__
        entry.push_result(typename, result)
    
    def get_result_typenames(self):
        return []

    def is_task(self):
        return False
    
    def is_parameter_consumer(self):
        return False
    
    def get_max_arity(self):
        return 0xFFFF # 不明なので適当な大きい値

    def get_min_arity(self):
        return 0 # 不明なので0

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

    def is_parameter_consumer(self):
        return self.method.is_trailing_params_consumer()
    
    def prepare_invoke(self, context: InvocationContext, *argobjects):
        selfobj, *argobjs = argobjects
        
        # メソッドの実装を読み込む
        self.method.load(selfobj.type)

        args = []
        if self.method.is_type_bound():
            # 型オブジェクトを渡す
            args.append(selfobj.type)

        if self.method.is_task():
            # Taskアクションにはspiritを渡す
            args.append(context.get_spirit())

        args.append(selfobj.value)
        args.extend([x.value for x in argobjs])
        
        # 引数が足りなければ、仮引数の型を基準に収集する
        kwargs = {}
        if len(args) < 0:
            objmap = context.get_selected_objects_typedict()
            for param in self.method.get_params():
                if len(objmap[param.typename]) > 0:    
                    obj = objmap[param.typename].pop(0)
                    kwargs[param.name] = obj.value
                elif not param.is_required():
                    kwargs[param.name] = param.get_default() # デフォルト引数で埋めておく
        
        # 実行
        entry = InvocationEntry(args, kwargs)
        return self.method.get_action(), entry

    def get_result_typenames(self):
        return [x.typename for x in self.method.results]
    
    def get_max_arity(self):
        cnt = self.method.get_acceptable_argument_max()
        if cnt is None:
            return 0xFFFF # メソッドから最大数を得る
        return cnt

    def get_min_arity(self):
        return 0 # 暗黙の取得もあり得るので0


#
# 定義のわからないメソッドを実行するたびに呼び出す
#
class InstanceMethodInvocation(BasicInvocation):
    def __init__(self, attrname, modifier=0):
        super().__init__(modifier)
        self.attrname = attrname

    def __str__(self):
        return "<InstanceMethodInvocation '{}' {}>".format(self.attrname, self.modifier_name())
    
    def prepare_invoke(self, context, *argobjects):
        selfval, *args = [x.value for x in argobjects]

        # 値に定義されたメソッドを取得
        method = getattr(selfval, self.attrname, None)
        if method is None:
            raise BadMethodInvocation(self.attrname)

        # 実行
        entry = InvocationEntry(args, {})
        return method, entry
    
#
# グローバルな関数を呼び出す
#
class StaticMethodInvocation(BasicInvocation):
    def __init__(self, function, modifier=0):
        super().__init__(modifier)
        self.fn = function
        try:
            sig = inspect.signature(self.fn)
            minarg = 0
            for p in sig.parameters.values():
                if p.default != inspect.Parameter.empty:
                    break
                minarg += 1
            self.arity = (minarg, len(sig.parameters))
        except ValueError:
            self.arity = (0, 0xFFFF)

    def __str__(self):
        name = ".".join([self.fn.__module__, self.fn.__name__])
        return "<StaticMethodInvocation '{}' {}>".format(name, self.modifier_name())
    
    def prepare_invoke(self, invocations, *argobjects):
        # そのままの引数で
        args = [x.value for x in argobjects]
        entry = InvocationEntry(args, {})
        return self.fn, entry
    
    def get_max_arity(self):
        return self.arity[1]

    def get_min_arity(self):
        return self.arity[0]
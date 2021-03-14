from typing import DefaultDict, Any, List, Sequence, Dict, Tuple, Optional, Union, Generator

import inspect
from collections import defaultdict

from machaon.core.type import Type, TypeModule
from machaon.core.object import Object, ObjectValue, ObjectCollection
from machaon.core.method import Method, MethodParameter, MethodResult, METHOD_FROM_INSTANCE, METHOD_FROM_FUNCTION, RETURN_SELF, parse_typename_syntax
from machaon.core.symbol import normalize_method_target, normalize_method_name, is_valid_object_bind_name, BadObjectBindName

#
# 
#
class BadInstanceMethodInvocation(Exception):
    def __init__(self, name):
        self.name = name

class BadFunctionInvocation(Exception):
    def __init__(self, name):
        self.name = name
    
class MessageNoReturn(Exception):
    pass

#
INVOCATION_RETURN_RECIEVER = "<reciever>"

#
#
#
class InvocationEntry():
    def __init__(self, invocation, action, args, kwargs, *, exception=None):
        self.invocation = invocation
        self.action = action
        self.args = args
        self.kwargs = kwargs
        self.results = [] # ObjectValue
        self.exception = exception
        
        if self.invocation:
            mod = self.invocation.modifier
            if mod & INVOCATION_REVERSE_ARGS:
                # 引数逆転
                self.args = reversed(self.args)
    
    def clone(self):
        inv = InvocationEntry(self.invocation, self.action, self.args, self.kwargs, exception=self.exception)
        inv.results = self.results
        inv.exception = self.exception
        return inv

    def invoke(self):
        """ アクションを実行し、返り値を保存する """
        from machaon.process import ProcessInterrupted
        result = None
        try:
            result = self.action(*self.args, **self.kwargs)
        except ProcessInterrupted as e:
            raise e
        except Exception as e:
            self.exception = e

        # 返り値をまとめる
        specs = self.invocation.get_result_specs()
        if not isinstance(result, tuple):
            result = (result,)
        for i, value in enumerate(result):
            if isinstance(value, Object):
                self.results.append(value)
            elif i<len(specs):
                spec = specs[i]
                self.results.append((value, spec))
            else:
                self.results.append((value,))
        
        # 返り値を否定
        if self.invocation.modifier & INVOCATION_NEGATE_RESULT:
            for ret in self.results:
                ret.value = not ret.value
    
    def result_objects(self, context) -> Generator[Object, None, None]:
        """ 返り値をオブジェクトに変換する """       
        for ret in self.results:
            if isinstance(ret, Object):
                yield ret
            else:
                value = ret[0]
                retspec = None
                if len(ret)>1:
                    retspec = ret[1]
                    # 型名から型オブジェクトを得る
                    rettype = context.select_type(retspec.get_typename())
                else:
                    retspec = None
                    rettype = None

                if retspec and retspec.is_return_self():
                    # <return-self>
                    yield Object(rettype, INVOCATION_RETURN_RECIEVER)
                    continue
                elif value is None:
                    # Noneが返された
                    err = MessageNoReturn()
                    yield context.new_invocation_error_object(err)
                    continue

                # Any型の場合は値から推定する
                if rettype is None or rettype.is_any():
                    deducedtype = context.deduce_type(value)
                    if deducedtype is not None:
                        rettype = deducedtype
                    else:
                        rettype = context.get_type("Any")

                # 値の型が異なる場合は、暗黙の型変換を行う
                if not rettype.check_value_type(type(value)):
                    typeparams = retspec.get_typeparams() if retspec else tuple()
                    value = rettype.conversion_construct(context, value, *typeparams)
                
                yield Object(rettype, value)

    def is_failed(self):
        if self.exception:
            return True
        return False

#    
LOG_MESSAGE_BEGIN = 1
LOG_MESSAGE_CODE = 2
LOG_MESSAGE_EVAL = 3
LOG_MESSAGE_EVALRET = 4
LOG_MESSAGE_END = 10
LOG_RUN_FUNCTION = 11

def instant_return_test(context, value, typename, typeparams=()):
    """ メソッド返り値テスト用 """
    from machaon.core.method import MethodResult
    typespec = MethodResult(typename, typeparams=typeparams)
    inv = InvocationEntry(None, None, (), {})
    inv.results.append((value, typespec))
    return next(inv.result_objects(context), None)

#
#
#
class InvocationContext:
    def __init__(self, *, input_objects, type_module, spirit=None, subject=None):
        self.type_module: TypeModule = type_module
        self.input_objects: ObjectCollection = input_objects  # 外部のオブジェクト参照
        self.subject_object: Union[None, Object, Dict[str, Object]] = subject       # 無名関数の引数とするオブジェクト
        self.local_objects: List[Object] = []                                       # メソッドの返り値を置いておく
        self.spirit = spirit
        self.invocations: List[InvocationEntry] = []
        self._last_exception = None
        self._log = []
    
    def get_spirit(self):
        return self.spirit
    
    @property
    def root(self):
        return self.spirit.app
    
    #
    def inherit(self, subject=None):
        return InvocationContext(
            input_objects=self.input_objects, 
            type_module=self.type_module, 
            spirit=self.spirit,
            subject=subject
        )

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
        for x in self.input_objects.pick(name):
            return x.object
        return None

    def get_selected_objects(self) -> List[Object]:
        li = [] # type: List[Object]
        for x in self.input_objects.pick_all():
            if x.selected:
                li.append(x.object)
        return li

    def push_object(self, name: str, obj: Object):
        self.input_objects.push(name, obj)
        
    def bind_object(self, name: str, obj: Object):
        if not is_valid_object_bind_name(name):
            raise BadObjectBindName(name)
        self.input_objects.push(name, obj)
    
    #
    def set_subject(self, subject: Object):
        self.subject_object = subject

    def clear_subject(self):
        self.subject_object = None
    
    #    
    def get_type(self, typename, *, scope=None) -> Optional[Type]:
        """ 型名を渡し、型定義を取得する """
        return self.type_module.get(typename, scope=scope)
    
    def select_type(self, typename, *, scope=None) -> Type:
        """ 型名を渡し、無ければAny型を取得する """
        if scope is None and "." in typename:
            scope, _, typename = typename.rpartition(".")

        if scope:
            # スコープ名でパッケージを検索
            package = self.root.get_package(scope, fallback=False)
            self.root.load_pkg(package)
        
        t = self.type_module.get(typename, scope=scope)
        if t is None:
            anytype = self.type_module.get("Any")
            if anytype is None:
                raise ValueError("Any type is not defined")
            return anytype
        else:
            return t

    def new_type(self, typecode: Any, scope=None) -> Type:
        """ 型定義クラス／型名を渡し、無ければ新たに定義して返す """
        return self.type_module.new(typecode, scope=scope)
    
    def new_temp_type(self, describer: Any) -> Type:
        """ 新しい型を作成するが、モジュールに登録しない """
        return Type.from_dict(describer)
    
    def deduce_type(self, value: Any) -> Optional[Type]:
        """ 値から型を推定する """
        if isinstance(value, Object):
            return value.type
        value_type = type(value) 
        return self.type_module.deduce(value_type)
    
    def new_object(self, value: Any, *, type=None, conversion=None) -> Object:
        """ 型名と値からオブジェクトを作る。値の型変換を行う 
        Params:
            typecode_or_value(Any): 型を示すもの。valueを省略した場合は値をとり、型を推定する
            *value(Any): 値
        KeywordParams:
            conversion(str): 値の変換方法
        """
        if type:
            t = self.new_type(type)
            convvalue = t.construct_from_value(self, value)
            return t.new_object(convvalue)
        elif conversion:
            tname, _, doc = conversion.partition(":")
            typename, doc, typeparams = parse_typename_syntax(tname.strip(), doc.strip())
            t = self.new_type(typename)
            convvalue = t.construct_from_value(self, value, *typeparams)
            return t.new_object(convvalue)
        else:
            valtype = self.deduce_type(value)
            if valtype is None:
                raise ValueError("値'{}'から型を推定できません".format(value))
            convvalue = valtype.construct_from_value(self, value)
            return valtype.new_object(convvalue)
    
    def new_invocation_error_object(self, exception=None):
        """ エラーオブジェクトを作る """
        if exception is None: 
            exception = self.get_last_exception()
        from machaon.process import ProcessError
        return self.new_type(ProcessError).new_object(ProcessError(self, exception))

    #
    def push_invocation(self, entry: InvocationEntry):
        self.invocations.append(entry)
        if entry.is_failed():
            self._last_exception = entry.exception
    
    def get_last_invocation(self) -> Optional[InvocationEntry]:
        if self.invocations:
            return self.invocations[-1]
        return None
    
    def last_result_objects(self) -> Generator[Object, None, None]:
        ent = self.get_last_invocation()
        if ent is None:
            return
        for ret in ent.result_objects(self):
            yield ret

    def get_last_exception(self) -> Optional[Exception]:
        return self._last_exception
    
    def is_failed(self):
        return self._last_exception is not None
    
    def push_extra_exception(self, exception):
        """ 呼び出し以外の場所で起きた例外を保存する """
        self._last_exception = exception

    #
    def add_log(self, logcode, *args):
        """ 実行ログの収集 """
        self._log.append((logcode, *args))
    
    def pprint_log(self, printer=None):
        """ 蓄積されたログを出力する """
        if printer is None: 
            printer = print

        if not self._log:
            printer(" --- no log ---")
            return
        
        for code, *args in self._log:
            if code == LOG_MESSAGE_BEGIN:
                source = args[0]
                title = "message"
                line = source
            elif code == LOG_MESSAGE_CODE:
                ccode, *values = args
                if len(values)>0:
                    term, *values = values
                else:
                    term = " "
                title = "term"
                line = "{} -> {}".format(term, ", ".join([ccode.as_term_flags()] + [str(x) for x in values]))
            elif code == LOG_MESSAGE_EVAL:
                msg = args[0]
                title = "evaluating"
                line = msg.sexprs()
            elif code == LOG_MESSAGE_EVALRET:
                value = args[0]
                title = "return"
                line = str(value)
            elif code == LOG_MESSAGE_END:
                title = "end-of-message"
                line = ""
            elif code == LOG_RUN_FUNCTION:
                cxt = args[0]
                if cxt is not self:
                    printer(" BEGIN ->")
                    cxt.pprint_log(printer=printer)
                    printer(" END <-")
                continue
            else:
                raise ValueError("不明なログコード:"+",".join([code,*args]))

            pad = 16-len(title)
            printer(" {}:{}{}".format(title, pad*" ", line))

        if self._last_exception:
            err = self._last_exception
            printer(" ERROR: {}".format(type(err).__name__))


def instant_context(subject=None):
    """ 即席実行用のコンテキスト """
    t = TypeModule()
    t.add_fundamental_types()

    from machaon.process import TempSpirit
    spi = TempSpirit()
    
    return InvocationContext(
        input_objects=ObjectCollection(),
        type_module=t,
        subject=subject,
        spirit=spi
    )
        
#
#
# メソッドの実行
#
#
INVOCATION_NEGATE_RESULT = 0x1
INVOCATION_REVERSE_ARGS = 0x2
INVOCATION_NORMALIZED_NAME = 0x4

#
#
#
class BasicInvocation():
    MOD_NEGATE_RESULT = INVOCATION_NEGATE_RESULT
    MOD_REVERSE_ARGS = INVOCATION_REVERSE_ARGS
    MOD_NORMALIZED_NAME = INVOCATION_NORMALIZED_NAME

    def __init__(self, modifier):
        self.modifier = modifier
        self.result_typehint = None
    
    def display(self):
        raise NotImplementedError()

    def __str__(self):
        inv = " ".join([x for x in self.display() if x])
        return "<Invocation {}>".format(inv)
    
    def get_method_name(self):
        raise NotImplementedError()

    def get_method_doc(self):
        raise NotImplementedError()

    def modifier_name(self, straight=False):
        m = []
        if self.modifier & INVOCATION_REVERSE_ARGS:
            m.append("reverse-args")
        if self.modifier & INVOCATION_NEGATE_RESULT:
            m.append("negate")
        if not m and straight:
            m.append("straight")
        return " ".join(m)
    
    def invoke(self, context: InvocationContext, *argobjects: Object):
        inventry = self.prepare_invoke(context, *argobjects)
        inventry.invoke()
        context.push_invocation(inventry)
    
    def set_result_typehint(self, typename: str):
        self.result_typehint = typename
        
    def get_result_typehint(self):
        return self.result_typehint
    
    #
    # これらをオーバーロードする
    #
    def prepare_invoke(self, context: InvocationContext, *args) -> InvocationEntry:
        raise NotImplementedError()
    
    def get_result_specs(self):
        return []

    def is_task(self):
        return False
    
    def is_parameter_consumer(self):
        return False
    
    def get_max_arity(self):
        return 0xFFFF # 不明なので適当な大きい値

    def get_min_arity(self):
        return 0 # 不明なので0
    
    def get_parameter_spec(self, index):
        return None # 不明

#
def get_object_value(obj, spec=None):
    if spec and spec.is_object():
        return obj
    elif obj.is_pretty_view():
        return obj.value.get_object().value
    else:
        return obj.value

#
# 型に定義されたメソッドの呼び出し 
#
class TypeMethodInvocation(BasicInvocation):
    def __init__(self, type, method, modifier=0):
        super().__init__(modifier)
        self.type = type
        self.method = method
    
    def get_method_name(self):
        return self.method.get_name()

    def get_method_doc(self):
        return self.method.get_doc()
    
    def display(self):
        return ("TypeMethod", self.method.get_action_target(), self.modifier_name())
    
    def query_method(self, this_type):
        self.method.load(this_type)
        return self.method
    
    def is_task(self):
        return self.method.is_task()

    def is_parameter_consumer(self):
        return self.method.is_trailing_params_consumer()

    def prepare_invoke(self, context: InvocationContext, *argobjects):
        selfobj, *argobjs = argobjects
        
        # メソッドの実装を読み込む
        self.method.load(self.type)

        args = []
        if self.method.is_type_bound():
            # 型オブジェクトを渡す
            args.append(self.type.get_describer_instance())

        # インスタンスを渡す
        selfvalue = get_object_value(selfobj, self.get_parameter_spec(-1))
        args.append(selfvalue)
    
        if self.method.is_context_bound():
            # コンテクストを渡す
            args.append(context)
        
        if self.method.is_spirit_bound():
            # spiritを渡す
            args.append(context.get_spirit())
        
        # 引数オブジェクトを整理する
        for i, argobj in enumerate(argobjs):
            argspec = self.get_parameter_spec(i)
            a = get_object_value(argobj, argspec)
            args.append(a)
        
        action = self.method.get_action()
        return InvocationEntry(self, action, args, {})   
    
    def get_action(self):
        return self.method.get_action()
    
    def get_result_specs(self):
        return self.method.get_results()

    def get_max_arity(self):
        cnt = self.method.get_acceptable_argument_max()
        if cnt is None:
            return 0xFFFF # 最大数不明
        return cnt

    def get_min_arity(self):
        return self.method.get_required_argument_min()

    def get_parameter_spec(self, index) -> Optional[MethodParameter]:
        if self.is_parameter_consumer():
            p = self.method.params[-1]
        else:
            p = self.method.get_param(index)
        return p

#
# 名前だけで定義のわからないメソッドを呼び出す
#
class InstanceMethodInvocation(BasicInvocation):
    def __init__(self, attrname, modifier=0):
        super().__init__(modifier)
        self.attrname = normalize_method_target(attrname)
        self._m = None
    
    def get_method_name(self):
        return normalize_method_name(self.attrname)
    
    def get_method_doc(self):
        return ""
    
    def display(self):
        return ("InstanceMethod", self.attrname, self.modifier_name())
    
    def query_method(self, this_type):
        if self._m:
            return self._m
        
        value_type = this_type.get_value_type()
        fn = getattr(value_type, self.attrname, None)
        if fn is None:
            raise BadInstanceMethodInvocation(self.attrname)
        
        if getattr(fn,"__self__",None) is not None:
            # クラスメソッドを排除する
            return None
            
        if not callable(fn):
            # 定数の類を取り除く
            return None

        mth = Method(normalize_method_name(self.attrname), flags=METHOD_FROM_INSTANCE)
        mth.load_from_function(fn, this_type)
        self._m = mth
        return mth
    
    def resolve_instance_method(self, args):
        instance, *trailingargs = args
        method = getattr(instance, self.attrname, None)
        if method is None:
            raise BadInstanceMethodInvocation(self.attrname)

        if not callable(method):
            # 引数なしの関数に変換する
            def nullary(v):
                def _method():
                    return v
                return _method
            method = nullary(method)
        
        return method, instance, trailingargs
    
    def prepare_invoke(self, context, *argobjects):
        method, _inst, args = self.resolve_instance_method([get_object_value(x) for x in argobjects])
        return InvocationEntry(self, method, args, {})
    
    def get_result_specs(self):
        return [MethodResult("Any")] # 値から推定する

#
# グローバルな関数を呼び出す
#
class FunctionInvocation(BasicInvocation):
    def __init__(self, function, modifier=0, *, do_inspect=True):
        super().__init__(modifier)
        self.fn = function
        self.arity = (0, 0xFFFF) # (min, max)
        if do_inspect:
            try:
                sig = inspect.signature(self.fn)
                minarg = 0
                for p in sig.parameters.values():
                    if p.default != inspect.Parameter.empty:
                        break
                    minarg += 1
                if len(sig.parameters) < 1:
                    raise BadFunctionInvocation(self.fn.__name__) # レシーバを受ける引数が最低必要
                self.arity = (minarg-1, len(sig.parameters)-1) # レシーバの分を引く
            except ValueError:
                pass

    def get_method_name(self):
        return normalize_method_name(self.fn.__name__)
    
    def get_method_doc(self):
        return self.fn.__doc__
    
    def display(self):
        name = ".".join([self.fn.__module__, self.fn.__qualname__])
        return ("Function", name, self.modifier_name())
    
    def query_method(self, _this_type):
        mth = Method(normalize_method_name(self.fn.__name__), flags=METHOD_FROM_FUNCTION)
        mth.load_from_function(self.fn)
        return mth
    
    def prepare_invoke(self, invocations, *argobjects):
        # そのままの引数で
        args = [get_object_value(x) for x in argobjects]
        return InvocationEntry(self, self.fn, args, {})
    
    def get_action(self):
        return self.fn

    def get_max_arity(self):
        return self.arity[1]

    def get_min_arity(self):
        return self.arity[0]
        
    def get_result_specs(self):
        return [MethodResult("Any")] # 値から推定する

#
class ObjectRefInvocation(BasicInvocation):
    def __init__(self, name, obj, modifier):
        super().__init__(modifier)
        self.name = name
        self.object = obj
    
    def get_method_name(self):
        return self.name

    def get_method_doc(self):
        return "Object '{}'".format(self.name)
    
    def display(self):
        return ("ObjectRef", self.name, self.modifier_name())
    
    def query_method(self, this_type):
        raise NotImplementedError()
    
    def is_task(self):
        return False

    def is_parameter_consumer(self):
        return False

    def prepare_invoke(self, _context: InvocationContext, *_argobjects):
        return InvocationEntry(self, self.get_action(), (), {})

    def get_action(self):
        return _objrefgetter(self.object)
    
    def get_result_specs(self):
        r = MethodResult(self.object.get_typename())
        return [r]

    def get_max_arity(self):
        return 0

    def get_min_arity(self):
        return 0

    def get_parameter_spec(self, index) -> Optional[MethodParameter]:
        return None


def _objrefgetter(obj):
    def _get():
        return obj
    return _get

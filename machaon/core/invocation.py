from typing import DefaultDict, Any, List, Sequence, Dict, Tuple, Optional, Union, Generator

import inspect

from machaon.core.type import Type, TypeModule
from machaon.core.typedecl import TypeProxy, parse_type_declaration
from machaon.core.object import EMPTY_OBJECT, Object, ObjectCollection
from machaon.core.method import Method, MethodParameter, MethodResult, METHOD_FROM_INSTANCE, METHOD_FROM_FUNCTION
from machaon.core.symbol import (
    BadTypename,
    normalize_method_target, normalize_method_name, 
    is_valid_object_bind_name, BadObjectBindName, full_qualified_name, 
    SIGIL_DEFAULT_RESULT, SIGIL_SCOPE_RESOLUTION
)

#
# 
#
class BadInstanceMethodInvocation(Exception):
    def __init__(self, valuetype, name):
        self.valuetype = valuetype
        self.name = name
    
    def __str__(self):
        return "'{}'のインスタンスにメソッド'{}'は存在しません".format(full_qualified_name(self.valuetype), self.name)


class BadFunctionInvocation(Exception):
    def __init__(self, name):
        self.name = name


class BadObjectMemberInvocation(Exception):
    pass


class UnresolvedObjectMemberInvocation(Exception):
    pass


INVOCATION_RETURN_RECIEVER = "<reciever>"

def _default_result_object(context):
    return context.get_type("Str").new_object(SIGIL_DEFAULT_RESULT)

def _new_process_error_object(context, error, objectType):
    from machaon.process import ProcessError
    errtype = context.get_type("Error")
    return objectType(errtype, ProcessError(context, error))

#
#
#
class InvocationEntry():
    """
    関数の呼び出し引数と返り値。
    """
    def __init__(self, invocation, action, args, kwargs, *, exception=None):
        self.invocation = invocation
        self.action = action
        self.args = args
        self.kwargs = kwargs
        self.result = EMPTY_OBJECT
        self.exception = exception
        self.message = None
        
        if self.invocation:
            mod = self.invocation.modifier
            if mod & INVOCATION_REVERSE_ARGS:
                # 引数逆転
                self.args = reversed(self.args)
    
    def clone(self):
        inv = InvocationEntry(self.invocation, self.action, self.args, self.kwargs, exception=self.exception)
        inv.result = self.result
        inv.exception = self.exception
        return inv
    
    def get_args(self):
        """ @method alias-name [args]
        引数。
        Returns:
            Tuple:
        """
        return self.args
    
    def get_kwargs(self):
        """ @method alias-name [kwargs]
        キーワード引数。
        Returns:
            ObjectCollection:
        """
        return self.kwargs

    def get_result(self):
        """ @method alias-name [result]
        返り値。
        Returns:
            Object:
        """
        return self.result

    def _invokeaction(self):
        """ アクションを実行（デバッグ用） """
        return self.action(*self.args, **self.kwargs)

    def invoke(self, context):
        """ アクションを実行し、返り値を保存する """
        from machaon.process import ProcessInterrupted
        result = None
        try:
            result = self.action(*self.args, **self.kwargs)
        except ProcessInterrupted as e:
            raise e
        except Exception as e:
            self.exception = e
        
        # 返り値を構成
        self.result = self.result_object(context, value=result)
        return self.result
    
    def result_spec(self):
        return self.invocation.get_result_spec()

    def result_object(self, context, *, value, spec=None, objectType=None) -> Object:
        """ 返り値をオブジェクトに変換する """
        isobject = isinstance(value, Object)
        if objectType is None:
            if isobject:
                objectType = type(value)
            else:
                objectType = Object
        
        # エラーが発生した
        if self.exception:
            return _new_process_error_object(context, self.exception, objectType)

        if isinstance(value, Object):
            rettype = value.type
            retval = value.value
        else:
            retval = value
            retspec = spec or self.result_spec()
            if retspec is None:
                raise ValueError("result_spec must be specified as MethodResult instance")
            rettype = retspec.get_typedecl().instance(context)
            if retspec.is_return_self():
                # return reciever 型は無視される
                return objectType(rettype, INVOCATION_RETURN_RECIEVER) 

        # Noneが返された
        if retval is None:
            if self.invocation.modifier & INVOCATION_DEFAULT_RESULT:
                return _default_result_object(context)
            else:
                return objectType(context.get_type("None"), None) # そのままNoneを返す
        
        # NEGATEモディファイアを適用            
        if self.invocation.modifier & INVOCATION_NEGATE_RESULT:
            retval = not retval
        
        # Any型の指定がある場合は、型を値から推定する
        if rettype is None or rettype.is_any():
            deducedtype = context.deduce_type(retval)
            if deducedtype is not None:
                rettype = deducedtype
            else:
                rettype = context.get_type("Any") # 推定もできなかった
        
        # 返り値型に値が適合しない場合は、型変換を行う
        if not rettype.check_value_type(type(retval)):
            retval = rettype.construct(context, retval)
        
        return objectType(rettype, retval)

    def is_failed(self):
        if self.exception:
            return True
        return False
    
    def set_message(self, message):
        self.message = message


#    
LOG_MESSAGE_BEGIN = 1
LOG_MESSAGE_CODE = 2
LOG_MESSAGE_EVAL_BEGIN = 3
LOG_MESSAGE_EVAL_END = 4
LOG_MESSAGE_END = 10
LOG_RUN_FUNCTION = 11

def instant_return_test(context, value, typename):
    """ メソッド返り値テスト用 """
    from machaon.core.method import MethodResult
    inv = BasicInvocation(0)
    entry = InvocationEntry(inv, None, (), {})
    decl = parse_type_declaration(typename)
    return entry.result_object(context, value=value, spec=MethodResult(decl))

#
#
#
class InvocationContext:
    """
    メソッドの呼び出しコンテキスト
    """
    def __init__(self, *, input_objects, type_module, spirit=None, subject=None):
        self.type_module: TypeModule = type_module
        self.input_objects: ObjectCollection = input_objects  # 外部のオブジェクト参照
        self.subject_object: Union[None, Object, Dict[str, Object]] = subject       # 無名関数の引数とするオブジェクト
        self.spirit = spirit
        self.invocations: List[InvocationEntry] = []
        self._last_exception = None
        self._log = []
    
    def get_spirit(self):
        return self.spirit
    
    @property
    def root(self):
        return self.spirit.root
    
    #
    def inherit(self, subject=None):
        return InvocationContext(
            input_objects=self.input_objects, 
            type_module=self.type_module, 
            spirit=self.spirit,
            subject=subject
        )

    #
    def get_object(self, name) -> Optional[Object]:
        elem = self.input_objects.get(name)
        if elem:
            return elem.object
        return None

    def get_selected_objects(self) -> List[Object]:
        li = [] # type: List[Object]
        for x in self.input_objects.pick_all():
            if x.selected:
                li.append(x.object)
        return list(reversed(li))

    def push_object(self, name: str, obj: Object):
        self.input_objects.push(name, obj)
        
    def bind_object(self, name: str, obj: Object):
        if not is_valid_object_bind_name(name):
            raise BadObjectBindName(name)
        self.input_objects.push(name, obj)
    
    def store_object(self, name: str, obj: Object):
        self.input_objects.store(name, obj)
    
    #
    def set_subject(self, subject: Object):
        self.subject_object = subject

    def clear_subject(self):
        self.subject_object = None
    
    #    
    def select_type(self, typecode, *, scope=None) -> Optional[TypeProxy]:
        """ 型名を渡し、型定義を取得する。関連するパッケージをロードする """
        if isinstance(typecode, TypeProxy):
            return typecode
        
        if scope is None:
            if isinstance(typecode, str) and SIGIL_SCOPE_RESOLUTION in typecode:
                typecode, _, scope = typecode.rpartition(SIGIL_SCOPE_RESOLUTION)
        if scope:
            # 関連パッケージをロードする
            package = self.root.get_package(scope, fallback=False)
            self.root.load_pkg(package)
        
        t = self.type_module.get(typecode, scope=scope)
        if t is None:
            return None
        return t

    def get_type(self, typename, *, scope=None) -> TypeProxy:
        """ 型名を渡し、型定義を取得する """
        t = self.type_module.get(typename, scope=scope)
        if t is None:
            raise BadTypename(typename)
        return t
    
    def deduce_type(self, value: Any) -> Optional[TypeProxy]:
        """ 値から型を推定する """
        if isinstance(value, Object):
            return value.type
        value_type = type(value) 
        t = self.type_module.deduce(value_type)
        if t is None:
            return None
        return t

    def define_type(self, typecode, *, scope=None) -> Type:
        """ 型を定義する """
        return self.type_module.define(typecode, scope=scope)

    def define_temp_type(self, describer: Any) -> Type:
        """ 新しい型を作成するが、モジュールに登録しない """
        return Type(describer).load()
    
    def new_object(self, value: Any, *args, type=None, conversion=None) -> Object:
        """ 型名と値からオブジェクトを作る。値の型変換を行う 
        Params:
            value(Any): 値; Noneの場合、デフォルトコンストラクタを呼び出す
            args(Sequence[Any]): 追加のコンストラクタ引数
        KeywordParams:
            type(Any): 型を示す値（型名、型クラス、型インスタンス）
            conversion(str): 値の変換方法を示す文字列
        """
        if type:
            t = self.select_type(type)
            if t is None:
                t = self.define_type(type) # 無ければ定義して返す 
            if value is None and not args:
                convobj = t.construct_obj(self, None) # デフォルトコンストラクタ
            else:
                convobj = t.construct_obj(self, value)
            return convobj
        elif conversion:
            typedecl = parse_type_declaration(conversion)
            tins = typedecl.instance(self, args)
            return tins.construct_obj(self, value)
        else:
            if isinstance(value, Object):
                return value
            if value is None:
                return self.get_type("None").new_object(value)
            valtype = self.deduce_type(value)
            if valtype:
                return valtype.construct_obj(self, value)
            else:
                return self.get_type("Any").new_object(value)
    
    def new_invocation_error_object(self, exception=None):
        """ エラーオブジェクトを作る """
        if exception is None: 
            exception = self.get_last_exception()
        return _new_process_error_object(self, exception, Object)
    
    def begin_invocation(self, entry: InvocationEntry):
        """ 呼び出しの直前に """
        self.invocations.append(entry)
        index = len(self.invocations)-1
        self.add_log(LOG_MESSAGE_EVAL_BEGIN, index)
        return index

    def finish_invocation(self, entry: InvocationEntry):
        """ 呼び出しの直後に """
        index = len(self.invocations)-1
        self.add_log(LOG_MESSAGE_EVAL_END, index)
        if entry.is_failed():
            self._last_exception = entry.exception
        return index
    
    def get_last_invocation(self) -> Optional[InvocationEntry]:
        if self.invocations:
            return self.invocations[-1]
        return None

    def get_last_exception(self) -> Optional[Exception]:
        """ @method alias-name [error]
        直前の呼び出しで発生した例外を返す。
        Returns:
            Error:
        """
        return self._last_exception
    
    def is_failed(self):
        """ @method
        エラーが発生したか
        Returns:
            bool:
        """
        return self._last_exception is not None
    
    def get_process(self):
        """ @method alias-name [process]
        紐づけられたプロセスを得る。
        Returns:
            Process:
        """
        return self.spirit.process
    
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
        
        subindex = None
        for code, *args in self._log:
            if code == LOG_MESSAGE_BEGIN:
                source = args[0].source
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
            elif code == LOG_MESSAGE_EVAL_BEGIN:
                invindex = args[0]
                title = "evaluating"
                line = self.invocations[invindex].message.sexpr()
            elif code == LOG_MESSAGE_EVAL_END:
                invindex = args[0]
                title = "return"
                line = str(self.invocations[invindex].result)
            elif code == LOG_MESSAGE_END:
                title = "end-of-message"
                line = ""
            elif code == LOG_RUN_FUNCTION:
                if subindex is None: subindex = 0
                subindex += 1
                continue
            else:
                raise ValueError("不明なログコード:"+",".join([code,*args]))
            
            pad = 16-len(title)
            printer(" {}:{}{}".format(title, pad*" ", line))

        if subindex is not None:
            title = "sub-contexts"
            if subindex > 1:
                line = "0-{}".format(subindex-1)
            else:
                line = "0"
            pad = 16-len(title)
            printer(" {}:{}{}".format(title, pad*" ", line))

        if self._last_exception:
            err = self._last_exception
            printer("  ERROR: {}".format(type(err).__name__))
        
    def get_message(self):
        """ @method alias-name [message] 
        実行されたメッセージ。
        Returns:
            Str:
        """
        for code, *values in self._log:
            if code == LOG_MESSAGE_BEGIN:
                return values[0].source
        raise ValueError("実行ログに記録がありません")
    
    def get_invocations(self):
        """ @method alias-name [all-invocation]
        呼び出された関数のリスト。
        Returns:
            Sheet[ObjectCollection](message-expression, result):
        """ 
        vals = []
        for inv in self.invocations:
            vals.append({
                "message-expression" : inv.message.sexpr(),
                "#delegate" : inv
            })
        return vals
    
    def get_errors(self, _app):
        """ @task alias-name [all-error]
        サブコンテキストも含めたすべてのエラーを表示する。
        Returns:
            Sheet[ObjectCollection](context-id, message-expression, error):
        """
        errors = []

        cxts = []
        cxts.append(("", self))
        i = 0
        while i < len(cxts):
            l, cxt = cxts[i]
            err = cxt.get_last_exception()
            if err:
                errors.append({
                    "context-id" : l,
                    "message-expression" : cxt.get_message(),
                    "error" : err,
                    "#delegate" : cxt
                })
            
            for j, subcxt in enumerate(cxt.get_subcontext_list()):
                if not l:
                    sublevel = "{}".format(j)
                else:
                    sublevel = "{}-{}".format(l,j)
                cxts.append((sublevel, subcxt))
            i += 1

        return errors

    def get_subcontext(self, index):
        """ @method alias-name [sub-context sub]
        呼び出しの中でネストしたコンテキストを取得する。
        Params:
            index(str): ネスト位置を示すインデックス。(例:0-4-1)
        Returns:
            Context:
        """
        if isinstance(index, str):
            indices = [int(x) for x in index.split("-")]
        else:
            indices = [index]
        
        subcxt = None
        logs = self._log
        for i, idx in enumerate(indices):
            submessages = [x for x in logs if x[0] == LOG_RUN_FUNCTION]
            if idx<0 or idx>= len(submessages):
                raise IndexError("'{}'に対応する子コンテキストはありません".format(index))
            subcxt = submessages[idx][1]
            # 次のレベルへ
            logs = subcxt._log 
        return subcxt
    
    def get_subcontext_list(self):
        """ @method alias-name [all-sub-context all-sub]
        サブコンテキストの一覧。
        Returns:
            Sheet[Context](is-failed, message, last-result):
        """
        rets = []
        submessages = [x for x in self._log if x[0] == LOG_RUN_FUNCTION]
        for values in submessages:
            subcxt = values[1]
            rets.append(subcxt)
        return rets
    
    def get_last_result(self):
        """ @method alias-name [last-result]
        最後に返されたメッセージの実行結果。
        Returns:
            Any:
        """
        inv = self.get_last_invocation()
        if inv:
            return inv.result
        return None

    def pprint_log_as_message(self, app):
        """ @method spirit alias-name [log]
        ログを表示する。
        """ 
        self.pprint_log(lambda x: app.post("message", x))
    
    def constructor(self, context, value):
        """ @meta """
        if isinstance(value, int):
            from machaon.process import Process
            proc = Process.constructor(Process, context, value)
            cxt = proc.get_last_invocation_context()
            if cxt is None:
                raise ValueError("プロセス'{}'にコンテキストが紐づいていません".format(value))
            return cxt
        elif isinstance(value, str):
            procindex, sep, sublevel = value.partition("-")
            if not sep:
                raise ValueError("[プロセスID]-[サブコンテキスト]の形式で指定してください")
            cxt = InvocationContext.constructor(self, context, int(procindex))
            if sublevel:
                return cxt.get_subcontext(sublevel)
            else:
                return cxt
        else:
            raise TypeError(value)

_instant_context_types = None

def instant_context(subject=None):
    """ 即席実行用のコンテキスト """
    global _instant_context_types
    if _instant_context_types is None:
        t = TypeModule()
        t.add_fundamental_types()

        from machaon.package.package import create_package
        pkg = create_package("machaon.shell", "module:machaon.types.shell")
        for x in pkg.load_type_definitions():
            t.define(x)
        
        _instant_context_types = t

    from machaon.process import TempSpirit
    spi = TempSpirit()
    
    return InvocationContext(
        input_objects=ObjectCollection(),
        type_module=_instant_context_types,
        subject=subject,
        spirit=spi
    )
        
#
#
# メソッドの実行
#
#
INVOCATION_NEGATE_RESULT       = 0x001
INVOCATION_REVERSE_ARGS        = 0x002
INVOCATION_DELEGATED_RECIEVER  = 0x004
INVOCATION_BASE_RECIEVER       = 0x008
INVOCATION_SHOW_HELP           = 0x010
INVOCATION_DEFAULT_RESULT      = 0x020

#
#
#
class BasicInvocation():
    MOD_NEGATE_RESULT = INVOCATION_NEGATE_RESULT
    MOD_REVERSE_ARGS = INVOCATION_REVERSE_ARGS
    MOD_BASE_RECIEVER = INVOCATION_BASE_RECIEVER
    MOD_SHOW_HELP = INVOCATION_SHOW_HELP
    MOD_DEFAULT_RESULT = INVOCATION_DEFAULT_RESULT

    def __init__(self, modifier):
        self.modifier = modifier
    
    def display(self):
        raise NotImplementedError()

    def __str__(self):
        inv = " ".join([x for x in self.display() if x])
        return "<{}>".format(inv)
    
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
        if self.modifier & INVOCATION_BASE_RECIEVER:
            m.append("basic")
        if self.modifier & INVOCATION_DEFAULT_RESULT:
            m.append("default")
        if self.modifier & INVOCATION_SHOW_HELP:
            m.append("help")
        if not m and straight:
            m.append("straight")
        return " ".join(m)
    
    def resolve_object_value(self, obj, spec=None):
        if spec and spec.is_object():
            return obj
        else:
            return obj.value

    #
    # これらをオーバーロードする
    #
    def prepare_invoke(self, context: InvocationContext, *args) -> InvocationEntry:
        raise NotImplementedError()
    
    def get_result_spec(self):
        return MethodResult() # 値から推定する

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
# 型に定義されたメソッドの呼び出し 
#
class TypeMethodInvocation(BasicInvocation):
    def __init__(self, type, method, modifier=0):
        super().__init__(modifier)
        self.type = type
        self.method = method
    
    def get_method(self):
        return self.method
        
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
            args.append(self.method.make_type_instance(self.type))

        # インスタンスを渡す
        selfvalue = self.resolve_object_value(selfobj, self.get_parameter_spec(-1))
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
            a = self.resolve_object_value(argobj, argspec)
            args.append(a)
        
        action = self.method.get_action()
        return InvocationEntry(self, action, args, {})   
    
    def get_action(self):
        return self.method.get_action()
    
    def get_result_spec(self):
        return self.method.get_result()

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
    
    def get_method_name(self):
        return self.attrname
    
    def get_method_doc(self):
        return ""
    
    def display(self):
        return ("InstanceMethod", self.attrname, self.modifier_name())
    
    def query_method_from_value_type(self, value_type):
        """ インスタンス型から推定してMethodオブジェクトを作成する """
        fn = getattr(value_type, self.attrname, None)
        if fn is None:
            raise BadInstanceMethodInvocation(value_type, self.attrname)
        
        if getattr(fn,"__self__",None) is not None:
            # クラスメソッドを排除する
            return None
            
        if not callable(fn):
            # 定数の類を取り除く
            return None

        mth = Method(self.attrname, flags=METHOD_FROM_INSTANCE)
        mth.load_from_function(fn)
        self._m = mth
        return mth
    
    def query_method_from_instance(self, instance):
        """ インスタンスからMethodオブジェクトを作成する """
        fn = self.resolve_instance_method(instance)
        mth = Method(self.attrname, flags=METHOD_FROM_INSTANCE)
        mth.load_from_function(fn)
        return mth
    
    def resolve_instance_method(self, instance):
        method = getattr(instance, self.attrname, None)
        if method is None:
            raise BadInstanceMethodInvocation(type(instance), self.attrname)

        if not callable(method):
            # 引数なしの関数に変換する
            method = _nullary(method)
        
        return method
    
    def prepare_invoke(self, context, *argobjects):
        a = [self.resolve_object_value(x) for x in argobjects]
        instance, *args = a
        method = self.resolve_instance_method(instance)
        return InvocationEntry(self, method, args, {})
    
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
        name = full_qualified_name(self.fn)
        return ("Function", name, self.modifier_name())
    
    def get_method(self):
        mth = Method(normalize_method_name(self.fn.__name__), flags=METHOD_FROM_FUNCTION)
        mth.load_from_function(self.fn)
        return mth
    
    def prepare_invoke(self, invocations, *argobjects):
        # そのままの引数で
        args = [self.resolve_object_value(x) for x in argobjects]
        return InvocationEntry(self, self.fn, args, {})
    
    def get_action(self):
        return self.fn

    def get_max_arity(self):
        return self.arity[1]

    def get_min_arity(self):
        return self.arity[0]
        
    def get_result_spec(self):
        return MethodResult() # 値から推定する


#
class ObjectMemberGetterInvocation(BasicInvocation):
    def __init__(self, name, typename, modifier=0):
        super().__init__(modifier)
        self.typename = typename
        self.name = name
    
    def is_task(self):
        return False

    def is_parameter_consumer(self):
        return False
    
    def get_action(self):
        return None
    
    def get_result_spec(self):
        decl = parse_type_declaration(self.typename)
        return MethodResult(decl)
    
    def get_parameter_spec(self, index) -> Optional[MethodParameter]:
        return None

    def get_max_arity(self):
        return 0

    def get_min_arity(self):
        return 0

    def prepare_invoke(self, _context, colarg):
        if self.name == "#=":
            obj = colarg.value.get_delegation()
            if obj is None:
                raise BadObjectMemberInvocation()
        else:
            elem = colarg.value.get(self.name)
            if elem is None:
                raise BadObjectMemberInvocation()
            obj = elem.object
        return InvocationEntry(self, _nullary(obj), (), {})

def _nullary(v):
    def _method():
        return v
    return _method

#
class ObjectMemberInvocation(BasicInvocation):
    def __init__(self, name, modifier=0):
        super().__init__(modifier)
        self.name = name
        self._resolved = None
    
    def resolve(self, collection):
        if self._resolved is not None:
            return
        
        if self.name == "#=":
            # delegate先オブジェクトの型に明示的に変換してメンバを取得する
            self._resolved = ObjectMemberGetterInvocation(self.name, collection.get_delegation().get_typename(), self.modifier)
            return

        item = collection.get(self.name)
        if item is not None:
            # メンバを取得する
            self._resolved = ObjectMemberGetterInvocation(self.name, item.object.get_typename(), self.modifier)
            return

        from machaon.core.message import select_method
        delg = collection.get_delegation()
        if delg is not None and not (self.modifier & INVOCATION_BASE_RECIEVER):
            # delegate先オブジェクトのメンバを暗黙的に参照する
            self._resolved = select_method(self.name, delg.type, reciever=delg.value, modbits=self.modifier)
            self.modifier |= INVOCATION_DELEGATED_RECIEVER
        else:
            # ジェネリックなメソッドを参照する
            self._resolved = select_method(self.name, modbits=self.modifier)
            if isinstance(self._resolved, InstanceMethodInvocation): # ObjectCollectionのインスタンスメソッドは使用しない
                self._resolved = TypeConstructorInvocation("None", 0) # Noneを返し、エラーにはしない
        
        self.must_be_resolved()

    def get_method_name(self):
        return self.name

    def get_method_doc(self):
        return "オブジェクトのメンバ'{}'".format(self.name)

    def display(self):
        return ("ObjectMember", self.name, self.modifier_name())
    
    def must_be_resolved(self):
        if self._resolved is None:
            raise UnresolvedObjectMemberInvocation(self.name)

    def is_task(self):
        self.must_be_resolved()
        return self._resolved.is_task()

    def is_parameter_consumer(self):
        self.must_be_resolved()
        return self._resolved.is_parameter_consumer()

    def prepare_invoke(self, context: InvocationContext, *argobjects):
        colarg, *args = argobjects
        # 実行時に呼び出しを解決する
        self.resolve(colarg.value)
        # 呼び出しエントリを作成する
        if self.modifier & INVOCATION_DELEGATED_RECIEVER:        
            delg = colarg.value.get_delegation()
            if delg is None:
                raise BadObjectMemberInvocation()
            entry = self._resolved.prepare_invoke(context, delg, *args)
        else:
            entry = self._resolved.prepare_invoke(context, colarg, *args)
        entry.invocation = self # 呼び出し元をすり替える
        return entry
    
    def get_action(self):
        self.must_be_resolved()
        return self._resolved.get_action()
    
    def get_result_spec(self):
        self.must_be_resolved()
        return self._resolved.get_result_spec()

    def get_max_arity(self):
        self.must_be_resolved()
        return self._resolved.get_max_arity()

    def get_min_arity(self):
        self.must_be_resolved()
        return self._resolved.get_min_arity()

    def get_parameter_spec(self, index) -> Optional[MethodParameter]:
        self.must_be_resolved()
        return self._resolved.get_parameter_spec(index)


class TypeConstructorInvocation(BasicInvocation):
    def __init__(self, typename, modifier):
        super().__init__(modifier)
        self._typename = typename
    
    def get_method_name(self):
        return self._typename

    def get_method_doc(self):
        return "型'{}'のコンストラクタ".format(self._typename)

    def display(self):
        return ("TypeConstructor", self._typename, self.modifier_name())
    
    def is_task(self):
        return False

    def is_parameter_consumer(self):
        return False

    def prepare_invoke(self, context: InvocationContext, *argobjects):
        argobj, *_args = argobjects
        # 型の実装を取得する
        t = context.select_type(self._typename)
        if t is None:
            raise BadTypename(self._typename)
        # 変換コンストラクタの呼び出しを作成
        arg = self.resolve_object_value(argobj)
        return InvocationEntry(self, t.construct, (context, arg), {})
    
    def get_action(self):
        raise ValueError("型変換関数は取得できません")
    
    def get_max_arity(self):
        return 0

    def get_min_arity(self):
        return 0

    def get_parameter_spec(self, index) -> Optional[MethodParameter]:
        return None
    
    def get_result_spec(self):
        decl = parse_type_declaration(self._typename)
        return MethodResult(decl)


class Bind1stInvocation(BasicInvocation):
    def __init__(self, method, arg, argtype, modifier=0):
        super().__init__(modifier)
        self._method = method # TypeMethodInvocation
        self._arg = arg # Object
        self._argtype = argtype # str
    
    def get_method_name(self):
        return self._method.get_method_name()

    def get_method_doc(self):
        return self._method.get_method_doc()

    def display(self):
        return ("Bind1st[{}({})]".format(self._arg, self._argtype), self._method.display()[1], self.modifier_name())
    
    def is_task(self):
        return False

    def is_parameter_consumer(self):
        return False

    def prepare_invoke(self, context: InvocationContext, *argobjects):
        argobj, *_args = argobjects
        bindargobj = context.new_object(self._arg, type=self._argtype)
        return self._method.prepare_invoke(context, argobj, bindargobj)
    
    def get_action(self):
        raise self._method.get_action()
    
    def get_max_arity(self):
        return 0

    def get_min_arity(self):
        return 0

    def get_parameter_spec(self, index) -> Optional[MethodParameter]:
        return None
    
    def get_result_spec(self):
        return self._method.get_result_spec()
    
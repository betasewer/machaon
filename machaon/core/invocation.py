from typing import DefaultDict, Any, List, Sequence, Dict, Tuple, Optional, Union, Generator

import inspect

from machaon.core.type import Type, TypeModule
from machaon.core.typedecl import (
    PythonType, TypeProxy, 
    parse_type_declaration, make_conversion_from_value_type
)
from machaon.core.object import EMPTY_OBJECT, Object, ObjectCollection
from machaon.core.method import METHOD_INVOKEAS_BOUND_METHOD, METHOD_INVOKEAS_FUNCTION, Method, MethodParameter, MethodResult, instance_invokeas, make_method_from_value
from machaon.core.symbol import (
    BadTypename,
    normalize_method_target, normalize_method_name, 
    is_valid_object_bind_name, BadObjectBindName, full_qualified_name, 
    SIGIL_DEFAULT_RESULT, SIGIL_SCOPE_RESOLUTION
)

#
# 
#
class ArgumentTypeError(Exception):
    def __init__(self, spec, value):
        super().__init__()
        self.spec = spec
        self.value = value
    
    def __str__(self):
        if hasattr(self.spec, "name"):
            spec = "引数'{}'の型'{}'".format(self.spec.name, self.spec.typename)
        else:
            spec = "型'{}'".format(self.spec.typename)
        value = repr(self.value)
        return "{}は{}に適合しません".format(value, spec)

class BadInstanceMethodInvocation(Exception):
    def __init__(self, valuetype, name):
        super().__init__()
        self.valuetype = valuetype
        self.name = name
    
    def __str__(self):
        return "'{}'のインスタンスにメソッド'{}'は存在しません".format(full_qualified_name(self.valuetype), self.name)

class BadFunctionInvocation(Exception):
    def __init__(self, name):
        self.name = name

class BadObjectMemberInvocation(Exception):
    pass

class RedirectUnresolvedInvocation(Exception):
    pass


INVOCATION_RETURN_RECIEVER = "<reciever>"

def _default_result_object(context):
    return context.get_type("Str").new_object(SIGIL_DEFAULT_RESULT)

def _new_process_error_object(context, error, objectType):
    from machaon.types.stacktrace import ErrorObject
    return objectType(context.get_type("Error"), ErrorObject(context, error))

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

    def invoke(self, 
        context # context
    ):
        """ アクションを実行し、返り値を保存する """
        from machaon.process import ProcessInterrupted
        result = None
        try:
            result = self.action(*self.args, **self.kwargs)
        except ProcessInterrupted as e:
            raise e
        except Exception as e:
            self.exception = e
        
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
                # レシーバオブジェクトを返す
                reciever = self.message.get_reciever_value()
                if isinstance(reciever, Object):
                    return objectType(reciever.type, reciever.value)
                else:
                    return objectType(rettype, reciever)

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
        if rettype is None or rettype.is_any_type():
            rettype = context.deduce_type(retval)
        
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


INVOCATION_FLAG_PRINT_STEP     = 0x0001
INVOCATION_FLAG_RAISE_ERROR    = 0x0002
INVOCATION_FLAG_SEQUENTIAL     = 0x0004
INVOCATION_FLAG_INHERIT_BIT_SHIFT  = 16 # 0xFFFF0000
INVOCATION_FLAG_INHERIT_REMBIT_SHIFT = 32

#
#
#
class InvocationContext:
    """
    メソッドの呼び出しコンテキスト
    """
    def __init__(self, *, input_objects, type_module, spirit=None, subject=None, flags=0, parent=None):
        self.type_module: TypeModule = type_module
        self.input_objects: ObjectCollection = input_objects  # 外部のオブジェクト参照
        self.subject_object: Union[None, Object, Dict[str, Object]] = subject       # 無名関数の引数とするオブジェクト
        self.spirit = spirit
        self.invocations: List[InvocationEntry] = []
        self.invocation_flags = flags
        self._extra_exception = None
        self._log = []
        self.log = self._add_log
        self.parent = parent # 継承元のコンテキスト
    
    def get_spirit(self):
        return self.spirit
    
    @property
    def root(self):
        return self.spirit.root
    
    #
    def inherit(self, subject=None):
        # 予約されたフラグを取り出して結合する
        preserved_flags = 0xFFFF & (self.invocation_flags >> INVOCATION_FLAG_INHERIT_BIT_SHIFT)
        flags = (0xFFFF & self.invocation_flags) | preserved_flags
        remove_flags = 0xFFFF & (self.invocation_flags >> INVOCATION_FLAG_INHERIT_REMBIT_SHIFT)
        flags = flags & ~remove_flags
        # subject以外は全て引き継がれる
        return InvocationContext(
            input_objects=self.input_objects, 
            type_module=self.type_module, 
            spirit=self.spirit,
            subject=subject,
            flags=flags,
            parent=self
        )

    def inherit_sequential(self):
        """ 連続実行を行う呼び出しのコンテクストを生成する """
        cxt = self.inherit()
        cxt.remove_flags(INVOCATION_FLAG_PRINT_STEP)
        cxt.set_flags(INVOCATION_FLAG_SEQUENTIAL|INVOCATION_FLAG_RAISE_ERROR)
        cxt.disable_log()
        return cxt

    def get_depth(self):
        """@method
        継承の深さを計算する
        Returns:
            Int: 1で始まる深さの数値
        """
        level = 1
        p = self.parent
        while p:
            level += 1
            p = p.parent
        return level
    
    def set_flags(self, flags, inherit_set=False, inherit_remove=False):
        if inherit_remove:
            # 以降の継承コンテキストで削除されるフラグをセット
            self.invocation_flags |= (flags << INVOCATION_FLAG_INHERIT_REMBIT_SHIFT)
        elif inherit_set:
            # 以降の継承コンテキストで有効化されるフラグをセット
            self.invocation_flags |= (flags << INVOCATION_FLAG_INHERIT_BIT_SHIFT)
        else:
            self.invocation_flags |= flags
    
    def remove_flags(self, flags):
        self.invocation_flags &= ~flags

    def is_set_print_step(self) -> bool:
        return (self.invocation_flags & INVOCATION_FLAG_PRINT_STEP) > 0
    
    def is_set_raise_error(self) -> bool:
        return (self.invocation_flags & INVOCATION_FLAG_RAISE_ERROR) > 0
    
    def is_sequential_invocation(self) -> bool: 
        return (self.invocation_flags & INVOCATION_FLAG_SEQUENTIAL) > 0

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
    
    def get_py_type(self, type) -> PythonType:
        """ Pythonの型 """
        return PythonType(type)
    
    def deduce_type(self, value: Any) -> TypeProxy:
        """ 値から型を推定する """
        if isinstance(value, Object):
            return value.type
        value_type = type(value) 
        t = self.type_module.deduce(value_type)
        if t is not None:
            return t
        return PythonType(value_type)

    def define_type(self, typecode, *, scope=None) -> Type:
        """ 型を定義する """
        return self.type_module.define(typecode, scope=scope)

    def define_temp_type(self, describer: Any) -> Type:
        """ 新しい型を作成するが、モジュールに登録しない """
        return Type(describer).load()

    def instantiate_type(self, conversion, *args) -> TypeProxy:
        """ 型をインスタンス化する """
        typedecl = parse_type_declaration(conversion)
        tins = typedecl.instance(self, args)
        return tins
    
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
                if isinstance(value, str):
                    raise BadTypename(value)
                else:
                    t = self.define_type(type) # 無ければ定義して返す 
            if value is None and not args:
                convobj = t.construct_obj(self, None) # デフォルトコンストラクタ
            else:
                convobj = t.construct_obj(self, value)
            return convobj
        elif conversion:
            tins = self.instantiate_type(conversion, *args)
            return tins.construct_obj(self, value)
        else:
            if isinstance(value, Object):
                return value
            if value is None:
                return self.get_type("None").new_object(value)
            valtype = self.deduce_type(value)
            return valtype.construct_obj(self, value)
    
    def new_invocation_error_object(self, exception=None):
        """ エラーオブジェクトを作る """
        if exception is None: 
            exception = self.get_last_exception()
        return _new_process_error_object(self, exception, Object)
    
    def begin_invocation(self, entry: InvocationEntry):
        """ 呼び出しの直前に """
        if self.is_sequential_invocation():
            # 上書きする
            if not self.invocations:
                self.invocations.append(entry)
            else:
                self.invocations[-1] = entry 
        else:
            self.invocations.append(entry)
        index = len(self.invocations)-1
        self.log(LOG_MESSAGE_EVAL_BEGIN, index)
        return index

    def finish_invocation(self, entry: InvocationEntry):
        """ 呼び出しの直後に """
        index = len(self.invocations)-1
        self.log(LOG_MESSAGE_EVAL_END, index)
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
        if self._extra_exception:
            return self._extra_exception
        inv = self.get_last_invocation()
        if inv:
            return inv.exception
        return None
    
    def is_failed(self):
        """ @method
        エラーが発生したか
        Returns:
            bool:
        """
        return self.get_last_exception() is not None
    
    def get_process(self):
        """ @method alias-name [process]
        紐づけられたプロセスを得る。
        Returns:
            Process:
        """
        return self.spirit.process
    
    def push_extra_exception(self, exception):
        """ 呼び出し以外の場所で起きた例外を保存する """
        self._extra_exception = exception

    def _add_log(self, logcode, *args):
        """ 実行ログを追加する """
        self._log.append((logcode, *args))

    def disable_log(self):
        """ ログを蓄積しない """
        self.log = _context_no_log
    
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

        if self._extra_exception:
            err = self._extra_exception
            printer("  ERROR: {}".format(type(err).__name__))
        
    def get_message(self):
        """ @method alias-name [message] 
        実行されたメッセージ。
        Returns:
            Str:
        """
        for code, *values in self._log:
            if code == LOG_MESSAGE_BEGIN:
                return values[0]
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
            cxt = InvocationContext.constructor(self, context, int(procindex))
            if sep:
                return cxt.get_subcontext(sublevel)
            else:
                return cxt
        else:
            raise TypeError(value)

# ログを無へ流す
def _context_no_log(*a, **kw):
    pass

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

def resolve_object_value(obj, spec=None):
    if spec and spec.is_object():
        return obj
    else:
        return obj.value

def check_argument_value_type(context, spec, value):
    if spec is None:
        return True
    if spec.is_type_uninstantiable():
        return True
    t = spec.get_typedecl().instance(context)
    return t.check_value_type(type(value))

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
    
    def set_modifier(self, modifier):
        self.modifier = modifier
    
    def display(self):
        raise NotImplementedError()

    def __str__(self):
        inv = " ".join([x for x in self.display() if x])
        return "<Invocation {}>".format(inv)
        
    def __repr__(self):
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
        if self.modifier & INVOCATION_BASE_RECIEVER:
            m.append("basic")
        if self.modifier & INVOCATION_DEFAULT_RESULT:
            m.append("default")
        if self.modifier & INVOCATION_SHOW_HELP:
            m.append("help")
        if not m and straight:
            m.append("straight")
        return " ".join(m)
    
    def _prepare(self, context: InvocationContext, *argvalues) -> InvocationEntry:
        """ デバッグ用: ただちに呼び出しエントリを構築する """
        args = [context.new_object(x) for x in argvalues]
        return self.prepare_invoke(context, *args)

    def _invoke(self, context: InvocationContext, *argvalues):
        """ デバッグ用: 引数を与えアクションを実行する """
        return self._prepare(context, *argvalues)._invokeaction()

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
    

class TypeMethodInvocation(BasicInvocation):
    """
    型に定義されたメソッドを呼び出す 
    """
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
        selfspec = self.get_parameter_spec(-1)
        selfvalue = resolve_object_value(selfobj, selfspec)
        if not check_argument_value_type(context, selfspec, selfvalue):
            raise ArgumentTypeError(selfspec, selfvalue)
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
            argvalue = resolve_object_value(argobj, argspec)
            if not check_argument_value_type(context, argspec, argvalue):
                raise ArgumentTypeError(argspec, argvalue)
            args.append(argvalue)
        
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


class RedirectorInvocation(BasicInvocation):
    def __init__(self, modifier):
        super().__init__(modifier)
        self._resolved = None

    def redirect_prepare_invoke(context, *argobjects):
        raise NotImplementedError()
    
    def must_be_resolved(self):
        if self._resolved is None:
            raise RedirectUnresolvedInvocation(self.display())

    def is_task(self):
        self.must_be_resolved()
        return self._resolved.is_task()

    def is_parameter_consumer(self):
        self.must_be_resolved()
        return self._resolved.is_parameter_consumer()

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
        
    def prepare_invoke(self, context: InvocationContext, *argobjects):
        entry = self.redirect_prepare_invoke(context, *argobjects)
        entry.invocation = self # 呼び出し元をすり替える
        return entry


class InstanceMethodInvocation(BasicInvocation):
    """
    インスタンスに紐づいたメソッドを呼び出す
    """
    def __init__(self, attrname, modifier=0, minarg=0, maxarg=0xFFFF):
        super().__init__(modifier)
        self.attrname = normalize_method_target(attrname)
        self.minarg = minarg
        self.maxarg = maxarg
    
    def get_method_name(self):
        return self.attrname
    
    def get_method_doc(self):
        return ""
    
    def get_max_arity(self):
        return self.maxarg

    def get_min_arity(self):
        return self.minarg
    
    def display(self):
        return ("InstanceMethod", self.attrname, self.modifier_name())
    
    def resolve_bound_method(self, instance):
        if not hasattr(instance, self.attrname):
            raise BadInstanceMethodInvocation(type(instance), self.attrname)
        value = getattr(instance, self.attrname)
        if callable(value):
            return value
        else:
            return _GetProperty(value, self.attrname)
    
    def prepare_invoke(self, context, *argobjects):
        a = [resolve_object_value(x) for x in argobjects]
        instance, *args = a
        method = self.resolve_bound_method(instance)
        return InvocationEntry(self, method, args, {})
    

class _GetProperty:
    def __init__(self, v, n):
        self.value = v
        self.name = n

    @property
    def __name__(self):
        return self.name

    def __repr__(self):
        return "<GetProperty '{}'>".format(self.name)

    def __call__(self, _this=None):
        return self.value
    
class FunctionInvocation(BasicInvocation):
    """
    インスタンスに紐づかない関数を呼び出す
    """
    def __init__(self, function, modifier=0, minarg=0, maxarg=0xFFFF):
        super().__init__(modifier)
        self.fn = function
        self.minarg = minarg
        self.maxarg = maxarg

    def get_method_name(self):
        return normalize_method_name(self.fn.__name__)
    
    def get_method_doc(self):
        return self.fn.__doc__
    
    def display(self):
        name = full_qualified_name(self.fn)
        return ("Function", name, self.modifier_name())
    
    def prepare_invoke(self, invocations, *argobjects):
        args = [resolve_object_value(x) for x in argobjects] # そのまま実行
        return InvocationEntry(self, self.fn, args, {})
    
    def get_action(self):
        return self.fn

    def get_max_arity(self):
        return self.maxarg

    def get_min_arity(self):
        return self.minarg
        
    def get_result_spec(self):
        return MethodResult() # 値から推定する


class ObjectMemberInvocation(RedirectorInvocation):
    """
    ObjectCollectionのアイテムに対する呼び出し
    """
    def __init__(self, name, modifier=0):
        super().__init__(modifier)
        self.name = name
    
    def get_method_name(self):
        return self.name

    def get_method_doc(self):
        return "オブジェクトのメンバ'{}'".format(self.name)

    def display(self):
        return ("ObjectMember", self.name, self.modifier_name())
    
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

    def redirect_prepare_invoke(self, context: InvocationContext, *argobjects):
        colarg, *args = argobjects
        
        # 実行時に呼び出しを解決する
        self.resolve(colarg.value)

        # 呼び出しエントリを作成する
        if self.modifier & INVOCATION_DELEGATED_RECIEVER:        
            delg = colarg.value.get_delegation()
            if delg is None:
                raise BadObjectMemberInvocation()
            return self._resolved.prepare_invoke(context, delg, *args)
        else:
            return self._resolved.prepare_invoke(context, colarg, *args)


class ObjectMemberGetterInvocation(BasicInvocation):
    """
    ObjectCollectionのアイテムを取得する
    """
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
        collection = colarg.value
        if self.name == "#=":
            obj = collection.get_delegation()
            if obj is None:
                raise BadObjectMemberInvocation("#delegate")
        else:
            elem = collection.get(self.name)
            if elem is None:
                raise BadObjectMemberInvocation(self.name)
            obj = elem.object
        return InvocationEntry(self, _GetProperty(obj, self.name), (), {})


class TypeConstructorInvocation(BasicInvocation):
    """
    型コンストラクタを呼び出す
    """
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
        arg = resolve_object_value(argobj)
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
    """
    第1引数を固定して呼び出す
    """
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
    

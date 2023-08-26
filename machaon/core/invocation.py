from typing import Optional

from machaon.core.type.decl import (
    TypeInstanceDecl, parse_type_declaration
)
from machaon.core.object import EMPTY_OBJECT, Object, ObjectCollection
from machaon.core.method import MethodParameter, MethodResult, Method, ImmediateValue
from machaon.core.symbol import (
    normalize_method_target, normalize_method_name, full_qualified_name
)

#
# 
#
class BadInstanceMethodInvocation(Exception):
    def __init__(self, valuetype, name):
        super().__init__(valuetype, name)
    
    def __str__(self):
        valtype, name = self.args
        return "'{}'のインスタンスにメソッド'{}'は存在しません".format(full_qualified_name(valtype), name)

class BadFunctionInvocation(Exception):
    def __init__(self, name):
        self.name = name

class BadObjectMemberInvocation(Exception):
    pass

class RedirectUnresolvedInvocation(Exception):
    pass


INVOCATION_RETURN_RECIEVER = "<reciever>"

#
#
#
class InvocationEntry():
    """
    関数の呼び出し引数と返り値。
    """
    def __init__(self, invocation, action, args, kwargs, result_spec=None, *, exception=None):
        self.invocation = invocation
        self.action = action
        self.args = args
        self.kwargs = kwargs
        self.result = EMPTY_OBJECT
        self.result_spec = result_spec or MethodResult()
        self.exception = exception
        self._message = None
        
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
        context.begin_invocation(self)

        args = self.args
        kwargs = self.kwargs
        if "IGNORE_ARGS" in self.invocation.modifier:
            args = ()
            kwargs = {}

        result = None
        from machaon.process import ProcessInterrupted
        try:
            result = self.action(*args, **kwargs)
        except ProcessInterrupted as e:
            raise e
        except Exception as e:
            self.exception = e
        
        context.finish_invocation()
        
        self.result = self.result_object(context, value=result)
        return self.result

    def result_object(self, context, *, value, objectType=None) -> Object:
        """ 返り値をオブジェクトに変換する """
        if objectType is None:
            if isinstance(value, Object):
                objectType = type(value)
            else:
                objectType = Object
        
        # エラーが発生した
        if self.exception:
            return context.new_invocation_error_object(self.exception, objectType)
    
        negate = ("NEGATE_RESULT" in self.invocation.modifier) # NEGATEモディファイアを適用

        # 型を決めて値を返す
        try:
            rettype, retval = self.result_spec.make_result_value(
                context, value, message=self.message, negate=negate
            )
            return objectType(rettype, retval)
        except Exception as e:
            self.exception = e
            return context.new_invocation_error_object(e, objectType)

    def is_failed(self):
        if self.exception:
            return True
        return False
    
    def set_message(self, message):
        self._message = message

    @property
    def message(self):
        if self._message is not None:
            return self._message
        else:
            # 引数なしの呼び出しがなされたと解釈する
            from machaon.core.message import Message, ResultStackRef
            return Message(ResultStackRef(), self.invocation)

#
#
# メソッドの実行
#
#
def resolve_object_value(obj, spec=None):
    if spec and spec.is_object():
        return obj
    else:
        return obj.value

def parameter_spec(t, i):
    spec = t.get_parameter_spec(i)
    if spec is not None:
        return spec
    return MethodParameter("param") # デフォルトのパラメータスペックを返す

#
#
#
class BasicInvocation():
    def __init__(self, modifier=None):
        self.modifier = modifier or set()
        if isinstance(modifier, int):
            raise TypeError("int modifier here, TO BE REMOVED")
    
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
        m.extend(x.lower().replace("_","-") for x in self.modifier)
        if not m and straight:
            m.append("straight")
        return " ".join(m)

    def _prepare(self, context, *argvalues) -> InvocationEntry:
        """ デバッグ用: ただちに呼び出しエントリを構築する """
        args = [context.new_object(x) for x in argvalues]
        return self.prepare_invoke(context, *args)

    def _invoke(self, context, *argvalues):
        """ デバッグ用: 引数を与えアクションを実行する """
        return self._prepare(context, *argvalues)._invokeaction()

    #
    # これらをオーバーロードする
    #
    def prepare_invoke(self, context, *args) -> InvocationEntry:
        raise NotImplementedError()
    
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
    def __init__(self, type, method, modifier=None):
        super().__init__(modifier)
        self.type = type
        self.method: Method = method
    
    def get_method(self):
        return self.method
        
    def get_method_name(self):
        return self.method.get_name()

    def get_method_doc(self):
        return self.method.get_doc()
    
    def display(self):
        return ("TypeMethod", self.method.get_action_target(), self.modifier_name())
    
    def is_task(self):
        return self.method.is_task()

    def is_parameter_consumer(self):
        return self.method.is_trailing_params_consumer()

    def prepare_invoke(self, context, *argobjects):
        selfobj, *argobjs = argobjects
        
        # メソッドの実装を読み込む
        self.method.load_from_type(self.type)

        args = []
        if self.method.is_type_bound():
            # 型オブジェクトを渡す
            args.append(self.method.make_type_instance(self.type))

        # インスタンスを渡す
        selfspec = parameter_spec(self, -1)
        args.append(selfspec.make_argument_value(context, selfobj))

        if self.method.is_context_bound():
            # コンテクストを渡す
            args.append(context)
        
        if self.method.is_spirit_bound():
            # spiritを渡す
            args.append(context.get_spirit())
        
        # 引数オブジェクトを整理する
        args.extend(self.method.make_argument_row(context, argobjs))
        
        action = self.method.get_action()
        result_spec = self.method.get_result()
        return InvocationEntry(self, action, args, {}, result_spec)   
    
    def get_action(self):
        return self.method.get_action()

    def get_max_arity(self):
        cnt = self.method.get_acceptable_argument_max()
        if cnt is None:
            return 0xFFFF # 最大数不明
        return cnt

    def get_min_arity(self):
        return self.method.get_required_argument_min()

    def get_parameter_spec(self, index) -> Optional[MethodParameter]:
        if index == -1:
            return self.method.get_param(-1)
        elif self.is_parameter_consumer():
            return self.method.params[-1]
        else:
            return self.method.get_param(index)


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
    
    def get_max_arity(self):
        self.must_be_resolved()
        return self._resolved.get_max_arity()

    def get_min_arity(self):
        self.must_be_resolved()
        return self._resolved.get_min_arity()

    def get_parameter_spec(self, index) -> Optional[MethodParameter]:
        self.must_be_resolved()
        return self._resolved.get_parameter_spec(index)
        
    def prepare_invoke(self, context, *argobjects):
        entry = self.redirect_prepare_invoke(context, *argobjects)
        entry.invocation = self # 呼び出し元をすり替える
        return entry


class InstanceMethodInvocation(BasicInvocation):
    """
    インスタンスに紐づいたメソッドを呼び出す
    """
    def __init__(self, attrname, modifier=None, minarg=0, maxarg=0xFFFF):
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
    
    def is_task(self):
        return True
    
    def display(self):
        return ("InstanceMethod", self.attrname, self.modifier_name())
    
    def resolve_bound_method(self, instance):
        if not hasattr(instance, self.attrname):
            raise BadInstanceMethodInvocation(type(instance), self.attrname)
        value = getattr(instance, self.attrname)
        if callable(value):
            return value
        else:
            return ImmediateValue(value, self.attrname)
    
    def prepare_invoke(self, context, *argobjects):
        a = [resolve_object_value(x) for x in argobjects]
        instance, *args = a
        method = self.resolve_bound_method(instance)
        return InvocationEntry(self, method, args, {})


class FunctionInvocation(BasicInvocation):
    """
    インスタンスに紐づかない関数を呼び出す
    """
    def __init__(self, function, modifier=None, minarg=0, maxarg=0xFFFF):
        super().__init__(modifier)
        if callable(function):
            self.fn = function
        else:
            self.fn = ImmediateValue(function, None)
        self.minarg = minarg
        self.maxarg = maxarg

    def get_method_name(self):
        if(hasattr(self.fn, "get_action_name")):
            name = self.fn.get_action_name()
        else:
            name = full_qualified_name(self.fn) or "<unnamed>"
        return normalize_method_name(name)
    
    def get_method_doc(self):
        if isinstance(self.fn, ImmediateValue):
            return repr(self.fn)
        else:
            return getattr(self.fn, "__doc__", "<no document>")
    
    def display(self):
        return ("Function", self.get_method_name(), self.modifier_name())
    
    def prepare_invoke(self, context, *argobjects):
        args = [resolve_object_value(x) for x in argobjects] # そのまま実行
        return InvocationEntry(self, self.fn, args, {})
    
    def get_action(self):
        return self.fn

    def get_max_arity(self):
        return self.maxarg

    def get_min_arity(self):
        return self.minarg
        
    def is_task(self):
        return True


class MessageInvocation(BasicInvocation):
    """
    メッセージ関数を呼び出す
    """
    def __init__(self, message, modifier=None):
        super().__init__(modifier)
        self.msg = message

    def get_method_name(self):
        return '({})'.format(self.msg.get_expression())
    
    def get_method_doc(self):
        return '({})'.format(self.msg.get_expression())
    
    def display(self):
        return ("Message", self.msg.get_expression(), self.modifier_name())
    
    def prepare_invoke(self, context, *argobjects):
        subject, *_a = argobjects
        args = [context, subject]
        return InvocationEntry(self, self.get_action(), args, {})
    
    def get_action(self):
        def _run(context, subj):
            return self.msg.run(subj, context)
        return _run

    def get_max_arity(self):
        return 0

    def get_min_arity(self):
        return 0

    def is_task(self):
        return True


class TypeConstructorInvocation(BasicInvocation):
    """
    型コンストラクタを呼び出す
    """
    def __init__(self, typeconversion, modifier=None):
        super().__init__(modifier)
        self._type = parse_type_declaration(typeconversion)

    def get_method_name(self):
        return self._type.to_string()

    def get_method_doc(self):
        return "型'{}'のコンストラクタ".format(self._type.to_string())

    def display(self):
        return ("TypeConstructor", self._type.to_string(), self.modifier_name())
    
    def is_task(self):
        return False

    def is_parameter_consumer(self):
        return False

    def prepare_invoke(self, context, *argobjects):
        # 型の実装を取得する
        t = self._type.instance(context)
        # コンストラクタ引数を作成
        result_spec = MethodResult(TypeInstanceDecl(t))
        argvals = [x.value for x in argobjects] # オブジェクトを剝がす
        return InvocationEntry(self, t.construct, (context, *argvals), {}, result_spec)
    
    def get_action(self):
        raise ValueError("型変換関数の実体は取得できません")
    
    def get_max_arity(self):
        return 0xFFFF # インスタンス化が必要

    def get_min_arity(self):
        return 0 # 後ろに続く引数はデフォルトでゼロ

    def get_parameter_spec(self, index) -> Optional[MethodParameter]:
        if isinstance(self._type, TypeInstanceDecl):
            mth = Method(params=self._type.instance_constructor_params())
            return mth.get_param(index)
        else:
            return None # 不明：推測する


class Bind1stInvocation(BasicInvocation):
    """
    第1引数を固定して呼び出す
    """
    def __init__(self, method, arg, argtype, modifier=None):
        super().__init__(modifier)
        self._method = method # TypeMethodInvocation
        self._arg = arg # Object
        self._argtype = argtype # str
    
    def get_method_name(self):
        return self._method.get_method_name()

    def get_method_doc(self):
        return self._method.get_method_doc()

    def display(self):
        return ("Bind1st", "{}({})/{}".format(self._method.display()[1], self._arg, self._argtype), self.modifier_name())
    
    def is_task(self):
        return False

    def is_parameter_consumer(self):
        return False

    def prepare_invoke(self, context, *argobjects):
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

    

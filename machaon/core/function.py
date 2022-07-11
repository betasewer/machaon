from machaon.core.symbol import (
    SIGIL_TYPE_INDICATOR
)
from machaon.core.message import (
    MessageEngine, select_method, select_method_by_object, Message, EvalContext, ResultStackRef
)
from machaon.core.object import Object
from machaon.core.invocation import BasicInvocation

#
# api
#
def run_function(expression: str, subject, context, *, raiseerror=False) -> Object:
    """
    文字列をメッセージとして実行する。
    Params:
        expression(str): メッセージ
        subject(Object): *引数
        context(InvocationContext): コンテキスト
    Returns:
        Object: 実行の戻り値
    """
    if not isinstance(expression, str):
        raise TypeError("expression must be str")
    
    if raiseerror:
        context.set_flags("RAISE_ERROR", inherit_set=True)

    f = MessageEngine(expression)
    return f.run_function(subject, context)
    
def run_function_print_step(expression: str, subject, context, *, raiseerror=False):
    """
    経過を表示しつつメッセージを実行する。
    """
    context.set_flags("PRINT_STEP")
    return run_function(expression, subject, context, raiseerror=raiseerror)


#
#　関数オブジェクト
#
class FunctionExpression():
    def get_expression(self) -> str:
        raise NotImplementedError()
    
    def get_type_conversion(self) -> str:
        raise NotImplementedError()
    
    def run(self, subject, context, **kwargs) -> Object:
        raise NotImplementedError()
        
    def run_here(self, context, **kwargs) -> Object:
        raise NotImplementedError()


class MessageExpression(FunctionExpression):
    """
    メッセージを実行する。
    """
    def __init__(self, expression, typeconv):
        self.f = MessageEngine(expression)
        self.typeconv = typeconv
    
    def get_expression(self) -> str:
        return self.f.get_expression()
    
    def get_type_conversion(self):
        return self.typeconv
    
    def run(self, subject, context, **kwargs):
        return self.f.run_function(subject, context, **kwargs)
    
    def run_here(self, context, **kwargs):
        return self.f.run_here(context, **kwargs)

    def bind(self, *args):
        raise NotImplementedError()


class SelectorExpression(FunctionExpression):
    """
    主題オブジェクトのメンバ（引数0のメソッド）を取得する
    Functionの機能制限版だが、キャッシュを利用する
    """
    def __init__(self, selector, typeconv):
        self.selector = selector
        self.typeconv = typeconv
        self.bindargs = []
        self._args = None
        self._selc = None
        
    def _make_invocation(self, context, subject):
        if self._args is None:
            self._args = [context.new_object(x) for x in self.bindargs]
            self._selc = context.new_object(self.selector)
        
        invocation = select_method_by_object(self._selc, subject.type, reciever=subject.value)
        entry = invocation.prepare_invoke(context, subject, *(context.new_object(x) for x in self._args))
        return entry

    def get_expression(self) -> str:
        if isinstance(self.selector, str):
            return self.selector
        elif isinstance(self.selector, BasicInvocation):
            return self.selector.display()[1]
        else:
            return self.selector
    
    def get_type_conversion(self):
        return self.typeconv
    
    def run(self, subject, context, **kwargs):
        """ その場でメッセージを構築し実行 """
        subcontext = context.inherit(subject)        
        try:
            entry = self._make_invocation(context, subject)
            subcontext.log_message_begin(self.get_expression())

            result = entry.invoke(subcontext)
            
            subcontext.log_message_end()
            context.log_message_begin_sub(subcontext)
        
            return result        
        except Exception as e:
            return context.new_object(e, type="Error")
    
    def run_here(self, context, **kwargs):
        """ コンテクストそのままで実行 """
        subject = context.subject_object        
        try:
            entry = self._make_invocation(context, subject)
            return entry.invoke(context)
        except Exception as e:
            return context.new_object(e, type="Error")
        
    def bind(self, *args):
        self.bindargs = args


def parse_function_message(expression):
    """
    メッセージ式から関数オブジェクトを作成する。
    Params:
        expression(str):
    """
    # 式の型指定子と式本体に分ける
    spl = expression.split(maxsplit=2)
    if len(spl) > 2 and spl[1] == SIGIL_TYPE_INDICATOR:
        typeconv = spl[0]
        body = spl[2]
    else:
        body = expression
        typeconv = None
    
    body = body.strip()
    if typeconv:
        typeconv = typeconv.strip()
    
    partscount = len(body.split())
    if partscount > 1:
        return MessageExpression(body, typeconv)
    elif partscount == 1:
        return SelectorExpression(body, typeconv)
    else:
        raise ValueError("Invalid expression")


def parse_function(expression):
    """
    メッセージ式や任意の値から関数オブジェクトを作成する。
    Params:
        expression(Any):
    """
    if isinstance(expression, str):
        return parse_function_message(expression.strip())
    else:
        return SelectorExpression(expression, None)


class SequentialMessageExpression(FunctionExpression):
    """
    同じコンテキストで同型のメッセージを複数回実行する
    """
    def __init__(self, parent_context, f, argspec = None, cache = True):
        self.f = f
        self.context = parent_context.inherit_sequential()
        self.memberspecs = {}
        self._argforge = lambda x: x # 単一の引数
        self._subjecttype = None
        self.cached = cache
        
        # 事前に型をインスタンス化しておく
        if isinstance(argspec, dict): 
            for key, typename in argspec.items():
                t = self.context.instantiate_type(typename)
                if key == "@":
                    self._subjecttype = t
                else:
                    self.memberspecs[key] = t
                
            def collectionarg(kwargs):
                objc = {}
                for k, v in kwargs.items():
                    t = self.memberspecs.get(k, None)
                    objc[k] = self.context.new_object(v, type=t)
                return objc
            self._argforge = collectionarg # ObjectCollectionにまとめる
            self._subjecttype = self.context.get_type("ObjectCollection")

        elif isinstance(argspec, str):
            self._subjecttype = self.context.instantiate_type(argspec)

    def get_expression(self) -> str:
        return self.f.get_expression()
    
    def get_type_conversion(self):
        return self.f.get_type_conversion()

    def get_context(self):
        return self.context

    def set_subject_type(self, conversion):
        self._subjecttype = self.context.instantiate_type(conversion)
    
    def run(self, subject, _context=None, **kwargs) -> Object:
        """ 共通メンバの実装 オブジェクトを返す """
        self.context.set_subject(subject) # subjecttypeは無視する
        return self.f.run_here(self.context, cache=self.cached)
        
    def run_here(self, _context=None, **kwargs) -> Object:
        """ 共通メンバの実装  """
        return self.f.run_here(self.context, cache=self.cached)

    def __call__(self, arg):
        """ コード内で実行する（複数の引数に対応） オブジェクトではなく値を返す"""
        argvalue = self._argforge(arg)
        subject = self.context.new_object(argvalue, type=self._subjecttype)
        self.context.set_subject(subject)
        o = self.f.run_here(self.context, cache=self.cached) # 同じコンテキストで実行
        return o.value
    
    def nousecache(self):
        """ メッセージのキャッシュを使用しない """
        self.cached = False

    def bind(self, *args):
        self.f.bind(*args)
    
    @classmethod
    def instant(cls, expression):
        # 文字列を受け取り、即席のコンテキストでインスタンスを作る
        from machaon.core.context import instant_context
        cxt = instant_context()
        return parse_sequential_function(expression, cxt)


def parse_sequential_function(expression, context, argspec=None):
    fn = parse_function(expression)
    return SequentialMessageExpression(context, fn, argspec)



class FunctionType():
    """ @type [Function]
    1引数をとるメッセージ。
    ValueType:
        machaon.core.function.FunctionExpression
    Params:
        qualifier(Str): None|(seq)uential
    """
    def constructor(self, context, s, qualifier=None):
        """ @meta context
        Params:
            Str:
        """
        from machaon.core.function import  parse_function, parse_sequential_function
        if qualifier is None:
            f = parse_function(s)
        elif qualifier == "sequential" or qualifier == "seq":
            f = parse_sequential_function(s, context)
        return f

    def stringify(self, f):
        """ @meta """
        return f.get_expression()
    
    #
    #
    #
    def do(self, f, context, _app, subject=None):
        """ @task context
        関数を実行する。
        Params:
            subject(Object): *引数
        Returns:
            Any: 返り値
        """
        r = f.run(subject, context)
        return r
        
    def apply_clipboard(self, f, context, app):
        """ @task context
        クリップボードのテキストを引数として関数を実行する。
        """
        text = app.clipboard_paste()
        if text is None:
            app.root.post_stray_message("error", "クリップボードの内容を取り出せませんでした")
        else:
            newtext = f.run(context.new_object(text), context).value
            context.raise_if_failed(newtext)
            app.clipboard_copy(newtext, silent=True)
            app.root.post_stray_message("message", "クリップボード上で変換: {} -> {}".format(text, newtext))

    def copy_apply_paste(self, f, context, app):
        """ @task context
        コピーコマンドを入力に送り、関数を適用し、ペーストコマンドを送る。
        """
        import time
        app.root.push_key("<ctrl>+c")
        time.sleep(0.2)
        self.apply_clipboard(f, context, app)
        app.root.push_key("<ctrl>+v")

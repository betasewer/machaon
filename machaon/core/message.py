from asyncio import selector_events
from cmath import exp
from re import A
from typing import Any

import ast
from itertools import zip_longest

from machaon.core.symbol import (
    PythonBuiltinTypenames, normalize_method_name, BadTypename, display_bitflag,
    SIGIL_OBJECT_ID,
    SIGIL_OBJECT_LAMBDA_MEMBER,
    SIGIL_OBJECT_ROOT_MEMBER,
    SIGIL_SCOPE_RESOLUTION,
    SIGIL_DEFAULT_RESULT,
    SIGIL_TRAILING_ARGS,
    SIGIL_TRAILING_ARGS_END,
    SIGIL_DISCARD_MESSAGE,
    SIGIL_TYPE_INDICATOR,
    QUOTE_ENDPARENS
)
from machaon.core.object import Object
from machaon.core.method import MethodParameter, enum_methods_from_type_and_instance
from machaon.core.invocation import (
    INVOCATION_FLAG_PRINT_STEP,
    INVOCATION_FLAG_RAISE_ERROR,
    BasicInvocation,
    TypeMethodInvocation,
    InstanceMethodInvocation,
    ObjectMemberInvocation,
    TypeConstructorInvocation,
    Bind1stInvocation,
    INVOCATION_RETURN_RECIEVER,
    LOG_MESSAGE_BEGIN,
    LOG_MESSAGE_CODE,
    LOG_MESSAGE_END,
    LOG_RUN_FUNCTION
)
from machaon.core.importer import enum_attributes


#
# ----------------------------------------------------------------------------
#
#
#
# ----------------------------------------------------------------------------
#
class BadExpressionError(Exception):
    """ メッセージの構文のエラー """
    pass

class BadMessageError(Exception):
    """ メッセージが実行できない場合のエラー """
    pass

class InternalMessageError(Exception):
    """ メッセージの実行中に起きたエラー """
    def __init__(self, error, message):
        self.error = error
        self.message = message
        self.with_traceback(self.error.__traceback__) # トレース情報を引き継ぐ

    def __str__(self):
        lines = []
        lines.append("メッセージ[{}]の実行中にエラー:".format(self.message.get_expression()))
        lines.append(str(self.error))
        return "\n".join(lines)

#
#
#
class Message:
    def __init__(self, 
        reciever = None, 
        selector = None, 
        args = None
    ):
        self.reciever = None # Object
        self.selector = None # Invocation
        self.args = args or []   # List[Object]
        self._argtrailing = False
        if reciever:
            self.set_reciever(reciever)
        if selector:
            self.set_selector(selector)
    
    def __repr__(self):
        return "<Message {}>".format(self.sexpr())
    
    def set_reciever(self, reciever):
        if reciever is None:
            raise TypeError()
        self.reciever = reciever

    def set_selector(self, selector):
        if selector is None:
            raise TypeError()
        self.selector = selector
    
    def add_arg(self, arg):
        if arg is None:
            raise TypeError()
        self.args.append(arg)
    
    def start_trailing_args(self):
        self._argtrailing = True
    
    def is_reciever_specified(self):
        return self.reciever is not None
    
    def is_selector_specified(self):
        return self.selector is not None

    def is_max_arg_specified(self):
        if self.selector:
            return len(self.args) >= self.selector.get_max_arity()
        return False
    
    def is_min_arg_specified(self):        
        if self.selector:
            return len(self.args) >= self.selector.get_min_arity()
        return False
    
    def is_specified(self):
        return (
            self.is_reciever_specified() 
            and self.is_selector_specified() 
            and (self.is_max_arg_specified() if self._argtrailing else self.is_min_arg_specified())
        )
    
    def is_selector_parameter_consumer(self):
        if self.selector:
            return self.selector.is_parameter_consumer()
        return False

    def is_task(self):
        if self.selector:
            return self.selector.is_task()
        return False
    
    def get_next_parameter_spec(self):
        if self.selector is None:
            raise BadMessageError("セレクタがありません")
    
        index = len(self.args) # 次に入る引数
        spec = self.selector.get_parameter_spec(index)
        if spec:
            return spec
        else:
            return MethodParameter("param{}".format(index), None, "引数{}".format(index))

    def get_reciever_value(self):
        if isinstance(self.reciever, BasicRef):
            return self.reciever.get_lastvalue()
        else:
            return self.reciever
    
    def reset_ref(self):
        for elem in (self.reciever, self.selector, *self.args):
            if isinstance(elem, BasicRef):
                elem.reset()

    def conclude(self, context):
        """ メッセージを完成させる """
        if not self.is_reciever_specified():
            # レシーバが無い場合はエラー
            raise BadExpressionError("レシーバがありません：{}".format(self.sexpr()))
        
        if not self.is_selector_specified():
            # セレクタが無い場合はレシーバを返すセレクタを補う
            self.selector = select_method("=")
        
        if not self.is_min_arg_specified():
            # 引数が足りない場合
            if len(self.args) > 0:   
                # 引数がゼロ以上あり、足りない場合はエラー         
                spec = self.get_next_parameter_spec()
                raise BadExpressionError("引数'{}'が足りません：{} ".format(spec.get_name(), self.get_method_syntax(context)))
            else:
                # ゼロの場合はセレクタを返す
                self.reciever = self.selector
                self.selector = select_method("=")

        self._argtrailing = False
    
    def eval(self, evalcontext):
        """ 
        完成したメッセージを実行する。
        Params:
            evalcontext(EvalContext):
        Returns:
            Object: 返り値
        """
        if self.reciever is None or self.selector is None:
            raise BadMessageError("レシーバとセレクタがありません")

        args = []

        # コンテキスト引数を取り出す。スタックにあるかもしれないので、逆順に
        for argobj in [*reversed(self.args), self.reciever]:
            if isinstance(argobj, BasicRef):
                args.append(argobj.pick_object(evalcontext))
            else:
                args.append(argobj)
        args.reverse() # 元の順番に戻す

        # 実行する
        context = evalcontext.context
        invocation = self.selector.prepare_invoke(context, *args)
        invocation.set_message(self)
        context.begin_invocation(invocation)

        retobj = invocation.invoke(context)
        
        context.finish_invocation(invocation)

        if retobj is None:
            raise BadMessageError("No return value exists on the context stack")
        return retobj

    #
    # デバッグ用
    #
    def sexpr(self):
        # S式風に表示：不完全なメッセージであっても表示する
        exprs = []

        def put(item):
            if isinstance(item, Object):
                exprs.append("<{} {}>".format(item.get_typename(), item.value_debug_str()))
            elif isinstance(item, BasicRef):
                exprs.append("<#Ref: {}>".format(item.get_lastvalue()))
            else:
                exprs.append(str(item))

        if self.reciever is not None:
            put(self.reciever)
        else:
            put("<レシーバ欠落>")

        if self.selector is not None:
            put(self.selector)

            minarg = self.selector.get_min_arity()
            for elem, _ in zip_longest(self.args, range(minarg-1)):
                if elem is not None:
                    put(elem)
                else:
                    put("<引数欠落>")
        else:
            put("<セレクタ欠落>")
            put("<引数欠落（個数不明）>")

        return "({})".format(" ".join(exprs))
    
    def get_method_syntax(self, context):
        if self.reciever is None:
            raise ValueError("レシーバが指定されていません")
        if self.selector is None:
            raise ValueError("セレクタが指定されていません")
        
        reci = self.reciever
        if isinstance(reci, BasicRef):
            reci = reci.pick_object(context)
        
        if isinstance(self.selector, TypeMethodInvocation):
            sign = self.selector.get_method().get_signature()
            return "{}.{} = {}".format(reci.get_typename(), self.selector.get_method_name(), sign)

        args = [reci]
        inventry = self.selector.prepare_invoke(context, *args)
        
        from machaon.types.stacktrace import FunctionInfo
        fn = FunctionInfo(inventry.action)
        return "{}{}".format(self.selector.get_method_name(), fn.display_parameters())



#
#
#
class EvalContext:
    def __init__(self, context):
        self.context = context
        self.locals = LocalStack()

class LocalStack:
    """ 計算結果のスタック """
    def __init__(self):
        self.local_objects = [] 

    def push_local_object(self, obj):
        """
        Params:
            obj(Object):
        """
        self.local_objects.append(obj)
    
    def top_local_object(self):
        """
        Returns:
            Optional[Object]:
        """
        if not self.local_objects:
            return None
        return self.local_objects[-1]

    def pop_local_object(self):
        if not self.local_objects:
            return
        self.local_objects.pop()

    def clear_local_objects(self):
        """
        Returns:
            List[Object]:
        """
        objs = self.local_objects
        self.local_objects = []
        return objs

# --------------------------------------------------------------------
#
# メッセージの構成要素
#
# --------------------------------------------------------------------
#
# オブジェクトへの参照
#
class BasicRef:
    def __init__(self, lastvalue=None):
        self._lastvalue = lastvalue

    def pick_object(self, evalcontext):
        if self._lastvalue is None:
            self._lastvalue = self.do_pick(evalcontext)
        return self._lastvalue
    
    def do_pick(self, evalcontext):
        raise NotImplementedError()
    
    def get_lastvalue(self):
        return self._lastvalue
    
    def reset(self):
        self._lastvalue = None

class ResultStackRef(BasicRef):
    """ スタックにおかれた計算結果への参照 """
    def do_pick(self, evalcontext):
        value = evalcontext.locals.top_local_object()
        if value is None:
            raise BadExpressionError("ローカルスタックを参照しましたが、値がありません")
        evalcontext.locals.pop_local_object()
        return value
    
class SubjectRef(BasicRef):
    """ 引数オブジェクトへの参照 """
    def do_pick(self, evalcontext):
        subject = evalcontext.context.subject_object
        if subject is None:
            raise BadExpressionError("無名関数の引数を参照しましたが、与えられていません")
        return subject

class ObjectRef(BasicRef):
    """ 任意のオブジェクトへの参照 """
    def __init__(self, ident, lastvalue=None):
        super().__init__(lastvalue)
        self._ident = ident
    
    def do_pick(self, evalcontext):
        obj = evalcontext.context.get_object(self._ident)
        if obj is None:
            raise BadExpressionError("オブジェクト'{}'は存在しません".format(self._ident))
        return obj

class SelectorResolver():
    """ セレクタを解決する """
    def __init__(self, selector):
        self.selector = selector

    def resolve(self, evalcontext, reciever):
        if isinstance(reciever, BasicRef):
            reciever = reciever.pick_object(evalcontext)
        return select_method(self.selector, reciever.type, reciever=reciever.value)


#
# リテラル
#
def select_type(context, typeexpr):
    """ 型 
    Params:
        typeexpr(str):
    Returns:
        Optional[Object]:
    """
    tt = context.select_type(typeexpr)
    if tt is None:
        return None
    return context.get_type("Type").new_object(tt)

def select_literal(context, literal):
    """ 基本型の値 
    Params:
        literal(str):
    Returns:
        Object:
    """
    try:
        value = ast.literal_eval(literal)
    except Exception:
        value = literal
    return value_to_obj(context, value)

def select_reciever(context, expression):
    """ 型もしくは基本型の値 
    Params:
        expression(str):
    Returns:
        Object:
    """
    # 型名の可能性
    if expression and expression[0].isupper():
        ot = select_type(context, expression)
        if ot:
            if ot.value.is_none_type():
                return context.get_type("None").new_object(None) # Noneの型はレシーバの文脈ではNoneの値にする
            return ot

    # リテラルだった
    return select_literal(context, expression)

def value_to_obj(context, value):
    typename = type(value).__name__
    if typename not in PythonBuiltinTypenames.literals:
        raise BadExpressionError("Unsupported literal type: {}".format(typename))
    return Object(context.get_type(typename), value)

def is_arg_trailing_selector(selector):
    if selector.endswith(SIGIL_TRAILING_ARGS):
        return True
    return False

#
_sel_modifiers = (
    ("~", BasicInvocation.MOD_REVERSE_ARGS),
    ("!", BasicInvocation.MOD_NEGATE_RESULT),
    ("`", BasicInvocation.MOD_BASE_RECIEVER), 
    ("&", BasicInvocation.MOD_DEFAULT_RESULT), 
    ("?", BasicInvocation.MOD_SHOW_HELP), 
)
def extract_selector_modifiers(selector):
    if len(selector)<2:
        return selector, 0
    modbits = 0
    offset = 0
    buf = ""
    for ch in selector:
        buf += ch
        for token, value in _sel_modifiers:
            if token == buf:
                modbits |= value
                buf = ""
                break
        else:
            break
        offset += 1
    sel = selector[offset:]
    if not sel:
        return selector, modbits
    return sel, modbits

# メソッド
def select_method(name, typetraits=None, *, reciever=None, modbits=None) -> BasicInvocation:
    # モディファイアを分離する
    if modbits is None:
        name, modbits = extract_selector_modifiers(name)

    # 数字のみのメソッドは添え字アクセスメソッドにリダイレクト
    if name.isdigit():
        if not typetraits or not typetraits.is_object_collection_type(): # ObjectCollectionには対応しない
            inv = select_method("at", typetraits, reciever=reciever, modbits=modbits)
            return Bind1stInvocation(inv, int(name), "Int", modbits)

    # 大文字のメソッドは型変換コンストラクタ
    if name[0].isupper():
        return TypeConstructorInvocation(name, modbits)

    # 型メソッド
    using_type_method = typetraits is not None
    if using_type_method:
        # 型メソッドを参照
        meth = typetraits.select_method(name)
        if meth is not None:
            return meth.make_invocation(modbits, typetraits)
        
        # レシーバがオブジェクト集合の場合はメンバ参照に変換
        if typetraits.is_object_collection_type():
            inv = ObjectMemberInvocation(name, modbits)
            if reciever:
                inv.resolve(reciever)
            return inv
    
    # グローバル定義の関数
    from machaon.types.generic import resolve_generic_method_invocation
    inv = resolve_generic_method_invocation(name, modbits)
    if inv is not None:
        return inv 

    if using_type_method:
        if not typetraits.is_selectable_instance_method():
            raise BadExpressionError("メソッド '{}' は '{}' に定義されていません".format(name, typetraits.get_typename()))
    
    # インスタンスメソッド
    return InstanceMethodInvocation(name, modifier=modbits)

#
# 
#
def enum_selectable_method(typetraits, instance=None):
    """
    型で利用可能なセレクタを列挙する
    Params:
        typetraits(Type): 型オブジェクト
        *instance(Any): インスタンス
    Yields:
        Tuple[List[str], Method|Exception, bool]: 名前と全エイリアス, メソッド（または読み込み時に起きたエラー）
    """
    # 型メソッドの列挙
    for names, meth in typetraits.enum_methods():
        yield names, meth
        
    if not typetraits.is_selectable_instance_method():
        return
    
    # インスタンスメソッドの列挙
    if instance is not None:
        valtype = type(instance)
    else:
        valtype = typetraits.get_value_type()
        instance = valtype

    for name, meth in enum_methods_from_type_and_instance(valtype, instance):
        # TypeMethodと被りがある場合はスキップ
        if typetraits.is_selectable_method(name):
            continue        
        yield [name], meth


# --------------------------------------------------------------------
#
# 文字列からメッセージを組み立てつつ実行する
#
# --------------------------------------------------------------------

# 式の文字列をトークンへ変換
TOKEN_NOTHING = 0
TOKEN_TERM = 0x01
TOKEN_BLOCK_BEGIN = 0x02
TOKEN_BLOCK_END = 0x04
TOKEN_ALL_BLOCK_END = 0x08
TOKEN_STRING = 0x10
TOKEN_ARGUMENT = 0x20
TOKEN_FIRSTTERM = 0x40

#  - 要素の種類
TERM_TYPE_MASK     = 0xF0
TERM_TYPE_RECIEVER = 0x10
TERM_TYPE_SELECTOR = 0x20
TERM_TYPE_ARGUMENT = 0x40

EXPECT_NOTHING = 0
EXPECT_RECIEVER = TERM_TYPE_RECIEVER
EXPECT_SELECTOR = TERM_TYPE_SELECTOR
EXPECT_ARGUMENT = TERM_TYPE_ARGUMENT

# 内部コード関数に渡す引数の指定
_INTLCODE_AST_ADDER = 1
_INTLCODE_ARG = 2
_INTLCODE_WITH_CONTEXT = _INTLCODE_ARG
_INTLCODE_WITH_EVALCONTEXT = 4
_INTLCODE_WITH_CONTEXT_EVALCONTEXT = _INTLCODE_WITH_CONTEXT | _INTLCODE_WITH_EVALCONTEXT

#
#
#
class MessageTokenBuffer():
    def __init__(self):
        self.buffer = [] # type: list[str]
        self.firstterm = True
        self.quote_char_waiting = False
        self.quote_beg = None
        self.quote_end = None
        self.lastflush = ""
    
    def flush(self):
        string = "".join(self.buffer)
        self.lastflush = string
        self.buffer.clear()
        if not string: # 空であれば排出しない
            return False
        return True

    def token(self, tokentype):
        string = self.lastflush
        self.lastflush = ""
        
        if self.firstterm and (tokentype & TOKEN_TERM): 
            tokentype |= TOKEN_FIRSTTERM
            self.firstterm = False
        
        return (string, tokentype)
    
    def set_next_token_firstterm(self):
        self.firstterm = True
    
    def quoting(self):
        return self.quote_beg is not None
    
    def begin_quote(self, newch, endch):
        self.quote_beg = newch
        self.quote_end = endch
        self.buffer.clear()

    def add(self, ch):
        self.buffer.append(ch)
    
    def check_quote_end(self):
        if not self.quoting() or self.quote_end is None:
            return False
        
        if len(self.quote_end) > 1:
            endlen = len(self.quote_end)
            for i in range(2, endlen):
                if self.buffer[-i] != self.quote_end[-i]:
                    return False
        
        if len(self.buffer) == 0:
            return False
        
        newch = self.buffer[-1]
        if newch != self.quote_end[-1]:
            return False
        
        offset = len(self.quote_end)
        if offset>0:
            self.buffer = self.buffer[:-offset]

        self.quote_beg = None
        self.quote_end = None
        return True

#
#
#
class InternalEngineCode():
    def __init__(self):
        self.arg_code = None
        self.ast_codes = []

    def set_arg(self, c, *args):
        self.arg_code = (c, args, _INTLCODE_ARG|getattr(c, "argspec", 0))

    def set_ast(self, c, *args):
        self.ast_codes.insert(0, (c, args, _INTLCODE_AST_ADDER))

    def add_ast(self, c, *args):
        self.ast_codes.append((c, args, getattr(c, "argspec", 0)))

    def run(self, evalcontext):
        """ コードを実行する """
        argobjs = []
        def _callargs(args, aspec):
            if aspec == 0:
                return args
            elif aspec == _INTLCODE_AST_ADDER:
                return [*args, evalcontext, *argobjs]
            elif aspec == _INTLCODE_WITH_CONTEXT:
                return [evalcontext.context, *args]
            elif aspec == _INTLCODE_WITH_CONTEXT_EVALCONTEXT:
                return [evalcontext.context, evalcontext, *args]
            elif aspec == _INTLCODE_WITH_EVALCONTEXT:
                return [evalcontext, *args]

        # 引数オブジェクトを構築する
        if self.arg_code is not None:
            (c, a, aspec) = self.arg_code
            ret = c(*_callargs(a, aspec))
            if isinstance(ret, tuple):
                argobjs.extend(ret)
            else:
                argobjs.append(ret)

        # 構文を組み立てる
        for (c, a, aspec) in self.ast_codes:
            c(*_callargs(a, aspec))

    def instructions(self):
        """ 命令の内容を表示する """
        if self.arg_code is not None:
            (c, a, _aspec) = self.arg_code
            arginstr = c.__name__
            argvals = a
        else:
            arginstr = None
            argvals = None

        i = 0
        for c, options, _aspec in self.ast_codes:
            if i == 0: # ADDER
                if options:
                    a = options[0]
                    if a == TERM_TYPE_RECIEVER:
                        a = "reciever"
                    elif a == TERM_TYPE_SELECTOR:
                        a = "selector"
                    elif a == TERM_TYPE_ARGUMENT:
                        a = "argument"
                    options = (a, *options[1:])
                yield (c.__name__, options, arginstr, argvals)
            else:
                yield (c.__name__, options, None, None)
            i += 1

    def display_instructions(self):
        """ 文字列にまとめて返す """
        ls = []
        for instrname, options, arginstrname, argvals in self.instructions():
            if arginstrname is None:
                line = "{:18}({})".format(instrname, ",".join(options))
            else:
                line = "{:18}({}) | {:18} {}".format(instrname, ",".join(options), arginstrname, ",".join(argvals))
            ls.append(line)
        return "\n".join(ls)


#
#
#
class MessageEngine():
    def __init__(self, expression="", messages=None):
        self.source = expression
        self.buffer = None
        self._tokens = []    # type: list[tuple[str, int]]
        self._readings = []  # type: list[Message]
        self._curblockstack = [] # type: list[int]
        self._msgs = messages or []
        self._lastread = ""  # 最後に完成したメッセージの文字列
        self._lastevalcxt = None

    def __repr__(self) -> str:
        return "<MessageEngine ({})>".format(self.source)
    
    def get_expression(self) -> str:
        """ コード文字列を返す """
        return self.source
    
    def read_token(self, source):
        """ 
        入力文字列をトークンへと変換する 
        Params:
            source(str): 入力文字列
        Yields:
            Tuple[str, int]: 文字列, トークンの意味を示す整数値
        """
        self.buffer = MessageTokenBuffer() # バッファをリセット
        user_quote_prelude = ""
        paren_count = 0
        buffer = self.buffer
        for ch in source:
            self._lastread += ch

            if buffer.quoting():
                buffer.add(ch)
            else:
                if ch == "'" or ch == '"':
                    buffer.begin_quote(ch, ch)
                elif ch == "(":
                    if buffer.flush(): 
                        yield buffer.token(TOKEN_TERM)
                    yield ("", TOKEN_BLOCK_BEGIN)
                    paren_count += 1
                elif ch == ")":
                    if buffer.flush():
                        yield buffer.token(TOKEN_TERM|TOKEN_BLOCK_END)
                    else:
                        yield buffer.token(TOKEN_BLOCK_END)
                    paren_count -= 1
                    if paren_count < 0:
                        raise SyntaxError("始め括弧が足りません")
                elif len(user_quote_prelude) == 2:
                    # エスケープを開始する
                    if user_quote_prelude == "->":
                        buffer.begin_quote("->", None)
                        buffer.add(ch)
                    elif user_quote_prelude == "--":
                        if ch.isspace():
                            buffer.begin_quote(" ", " ")
                        else:
                            buffer.begin_quote(ch, QUOTE_ENDPARENS.get(ch,ch))
                    else:
                        raise ValueError("Unknown Quote Prelude:" + user_quote_prelude)
                    user_quote_prelude = ""
                elif ch == "-" and len(user_quote_prelude) < 2:
                    # エスケープ表現の途中
                    user_quote_prelude += ch
                elif ch == ">" and len(user_quote_prelude) == 1:
                    # エスケープ表現の途中
                    user_quote_prelude += ch
                else:
                    # その他すべての文字
                    if len(user_quote_prelude) > 0:
                        # エスケープ表現ではなかった -> バッファに追加
                        for cch in user_quote_prelude: buffer.add(cch)
                        user_quote_prelude = ""
                    
                    if ch.isspace():
                        # 空白ならバッファを書き出す
                        if buffer.flush(): 
                            yield buffer.token(TOKEN_TERM)
                    else:
                        # それ以外はバッファに追記する
                        buffer.add(ch)

            if buffer.check_quote_end():
                if buffer.flush(): 
                    yield buffer.token(TOKEN_TERM|TOKEN_STRING)
                continue
            
        if paren_count > 0:
            raise SyntaxError("終わり括弧が足りません")
        
        if buffer.flush():
            if buffer.quoting():
                yield buffer.token(TOKEN_TERM|TOKEN_ALL_BLOCK_END|TOKEN_STRING)
            else:
                yield buffer.token(TOKEN_TERM|TOKEN_ALL_BLOCK_END)
        else:
            yield buffer.token(TOKEN_ALL_BLOCK_END)
    
    # 現在評価している途中のメッセージ
    def current_reading_message(self):
        if self._curblockstack: 
            curblock = self._curblockstack[-1]
            if len(self._readings)-1 < curblock:
                return None
            return self._readings[-1]
        else:
            if not self._readings:
                return None
            return self._readings[-1]

    # 
    def compile_code(self, reading, token: str, tokentype: int):
        """
        トークンから内部コードを生成する
        Params:
            reading(Optional[Message]): 読んでいる途中のメッセージオブジェクト
            token(str): 文字列
            tokentype(int): 文字列の意味(TOKEN_XXX)
        Returns:
            InternalEngineCode: 還元された命令コードと引数のセット
        """
        #
        # 直前のトークンから次に来るべきトークンの意味を決定する
        #
        expect = EXPECT_NOTHING
        if reading is None:
            pass
        elif not reading.is_reciever_specified():
            expect = EXPECT_RECIEVER
        elif not reading.is_selector_specified():
            expect = EXPECT_SELECTOR
        elif not reading.is_max_arg_specified():
            expect = EXPECT_ARGUMENT

        #
        code = InternalEngineCode()

        # ブロック終了指示
        if tokentype & TOKEN_BLOCK_END:
            code.add_ast(self.ast_POP_BLOCK)
        elif tokentype & TOKEN_ALL_BLOCK_END:
            code.add_ast(self.ast_POP_ALL_BLOCKS)

        # エスケープされた文字列
        isstringtoken = tokentype & TOKEN_STRING > 0

        # 明示的ブロック開始指示
        if tokentype & TOKEN_BLOCK_BEGIN:
            code.set_ast(self.ast_ADD_ELEMENT_AS_NEW_BLOCK, expect)
            code.add_ast(self.ast_PUSH_BLOCK)
            # セレクタの場合はメッセージ完成後に即座に評価する必要がある
            return code

        # 特殊な記号
        if not isstringtoken:
            # 引数リストの終わり
            if token == SIGIL_TRAILING_ARGS_END:
                if expect == EXPECT_ARGUMENT:
                    code.add_ast(self.ast_POP_BLOCK)
                    return code
            # メッセージの連鎖をリセットする
            if token == SIGIL_DISCARD_MESSAGE:
                if expect == EXPECT_NOTHING:
                    code.add_ast(self.ast_DISCARD_LAST_BLOCK_MESSAGE)
                    return code
                raise BadExpressionError("メッセージの要素が足りません")

        # メッセージの要素ではない
        if (tokentype & TOKEN_TERM) == 0:
            return code

        #
        # 以下、メッセージの要素として解析
        # 

        # オブジェクト参照
        if not isstringtoken and token.startswith(SIGIL_OBJECT_ID):
            if expect == EXPECT_SELECTOR:
                raise BadExpressionError("セレクタが必要です") 

            def new_block_bits(c):
                if expect == EXPECT_NOTHING:
                    c.set_ast(self.ast_ADD_ISOLATE_ELEMENT, TERM_TYPE_RECIEVER)
                else:
                    c.set_ast(self.ast_ADD_ELEMENT_AS_NEW_BLOCK, expect)
                return c

            objid = token[1:]
            if not objid: 
                # 無名関数の引数オブジェクト
                code.set_arg(self.arg_LAMBDA_ARG_MEMBER, "")
            
            elif SIGIL_OBJECT_LAMBDA_MEMBER in objid:
                # 引数オブジェクトのメンバ参照
                objid, _, memberid = token.partition(SIGIL_OBJECT_LAMBDA_MEMBER)
                if not memberid:
                    raise BadExpressionError("'{}'のあとにセレクタが必要です".format(SIGIL_OBJECT_LAMBDA_MEMBER))
                code.set_arg(self.arg_LAMBDA_ARG_MEMBER, memberid)

                return new_block_bits(code)
                
            elif objid[0] == SIGIL_OBJECT_ROOT_MEMBER:
                # ルートオブジェクトの参照
                memberid = token[2:]
                if memberid:
                    # メンバ参照
                    code.set_arg(self.arg_ROOT_MEMBER, memberid)
                else:
                    # ルートオブジェクト自体を参照
                    code.set_arg(self.arg_ROOT_MEMBER, "")
                return new_block_bits(code)
                
            elif objid.isdigit():
                # 数値名称のオブジェクト
                objid = str(int(objid)) # 数値表現を正規化
                code.set_arg(self.arg_REF_NAME, objid)
            
            else:
                # 通常の名称のオブジェクト
                code.set_arg(self.arg_REF_NAME, objid)

            if expect == EXPECT_NOTHING:
                code.set_ast(self.ast_ADD_ISOLATE_ELEMENT, TERM_TYPE_RECIEVER) # 新しいメッセージのレシーバになる
            else:
                code.set_ast(self.ast_ADD_LAST_BLOCK_ELEMENT, expect) # 前のメッセージの要素になる
            return code

        # 何も印のない文字列
        #  => メソッドかリテラルか、文脈で判断
        if expect == EXPECT_SELECTOR and reading:
            if is_arg_trailing_selector(token):
                code.add_ast(self.ast_START_TRAILING_ARGS)
                token = token[:-1]
            code.set_arg(self.arg_SELECTOR_VALUE, token)
            code.set_ast(self.ast_ADD_LAST_BLOCK_ELEMENT, expect) # 前のメッセージのセレクタになる
            return code

        if expect == EXPECT_ARGUMENT:           
            # メソッドの型要求に従って解釈する 
            spec = reading.get_next_parameter_spec()
            typename = spec.typename if spec else None
            if typename == "Type":
                code.set_arg(self.arg_TYPE, token)
            elif typename == "Tuple":
                code.set_arg(self.arg_TUPLE, token)
            elif spec.is_type_unspecified():
                if isstringtoken:
                    code.set_arg(self.arg_STRING, token)
                else:
                    code.set_arg(self.arg_LITERAL, token)
            else:
                code.set_arg(self.arg_TYPED_VALUE, token, spec)            
            # 前のメッセージの引数になる
            code.set_ast(self.ast_ADD_LAST_BLOCK_ELEMENT, expect) 
            return code

        if expect == EXPECT_RECIEVER:
            if isstringtoken:
                code.set_arg(self.arg_STRING, token)
            else:
                code.set_arg(self.arg_RECIEVER_VALUE, token)
            code.set_ast(self.ast_ADD_LAST_BLOCK_ELEMENT, expect)
            return code

        if expect == EXPECT_NOTHING:
            if tokentype & TOKEN_FIRSTTERM:
                # メッセージの先頭のみ、レシーバオブジェクトのリテラルとする token
                if isstringtoken:
                    code.set_arg(self.arg_STRING, token)
                else:
                    code.set_arg(self.arg_RECIEVER_VALUE, token)
                code.set_ast(self.ast_ADD_ISOLATE_ELEMENT, TERM_TYPE_RECIEVER)
                return code
            else:
                # 先行するメッセージの返り値をレシーバとするセレクタとする
                if is_arg_trailing_selector(token):
                    code.add_ast(self.ast_START_TRAILING_ARGS)
                    token = token[:-1]
                code.set_arg(self.arg_SELECTOR_VALUE, token)
                code.set_ast(self.ast_ADD_ISOLATE_ELEMENT, TERM_TYPE_SELECTOR)
                return code
        
        raise BadExpressionError("Could not parse")


    def complete_messages(self):
        """
        完成した構文木を返す
        Yields:
            Message:
        """
        # 完成したメッセージをキューから取り出す
        completed = 0
        index = len(self._readings)-1
        for msg in reversed(self._readings):
            if not msg.is_specified(): # レシーバ、引数が指定されていない
                break
            if self._curblockstack and self._curblockstack[-1] > index: # ブロック外の評価を遅延する
                break

            # メッセージが完成したので評価する
            yield msg
            completed += 1

            index -= 1

        if completed>0:
            del self._readings[-completed:]


    #
    #  メッセージを構築する
    #
    def ast_ADD_LAST_BLOCK_ELEMENT(self, ttpcode, evalcontext, obj, *a):
        """ """
        if ttpcode == TERM_TYPE_RECIEVER:
            self._readings[-1].set_reciever(obj)

        elif ttpcode == TERM_TYPE_SELECTOR:
            reciever = self._readings[-1].reciever
            selector = obj.resolve(evalcontext, reciever)
            self._readings[-1].set_selector(selector)

        elif ttpcode == TERM_TYPE_ARGUMENT:
            self._readings[-1].add_arg(obj)

    def ast_ADD_ELEMENT_AS_NEW_BLOCK(self, ttpcode, _evalcontext, *objs):
        """ """
        if ttpcode == TERM_TYPE_RECIEVER:
            self._readings[-1].set_reciever(ResultStackRef())

        elif ttpcode == TERM_TYPE_SELECTOR:
            self._readings[-1].set_selector(ResultStackRef()) # TODO
        
        elif ttpcode == TERM_TYPE_ARGUMENT:
            self._readings[-1].add_arg(ResultStackRef())
        
        new_msg = Message(*objs)
        self._readings.append(new_msg)

    def ast_ADD_ISOLATE_ELEMENT(self, ttpcode, evalcontext, *objs):
        """ """
        if ttpcode == TERM_TYPE_RECIEVER:
            new_msg = Message(*objs)
            self._readings.append(new_msg)

        elif ttpcode == TERM_TYPE_SELECTOR:
            reciever = ResultStackRef()
            selector = objs[0].resolve(evalcontext, reciever)
            new_msg = Message(reciever, selector)
            self._readings.append(new_msg)

        else:
            raise ValueError("???")
            
    ast_ADD_LAST_BLOCK_ELEMENT.argspec = _INTLCODE_AST_ADDER
    ast_ADD_ELEMENT_AS_NEW_BLOCK.argspec = _INTLCODE_AST_ADDER
    ast_ADD_ISOLATE_ELEMENT.argspec = _INTLCODE_AST_ADDER
        
    def ast_START_TRAILING_ARGS(self): 
        """  """
        self._readings[-1].start_trailing_args()

    def ast_PUSH_BLOCK(self):
        """  """
        newpos = len(self._readings)-1 # 上でメッセージを追加済み
        self._curblockstack.append(newpos) # 新しいブロックの番号を記録する

    def ast_POP_BLOCK(self, context):
        """  """
        if self._curblockstack:
            top = self._curblockstack[-1]
        else:
            top = 0
        for i, msg in enumerate(reversed(self._readings)):
            j = len(self._readings) - i - 1
            if j < top:
                break 
            msg.conclude(context)
        if self._curblockstack:
            self._curblockstack.pop()

    def ast_POP_ALL_BLOCKS(self, context):
        """ """
        for msg in self._readings:
            msg.conclude(context)
        self._curblockstack.clear()
        
    ast_POP_BLOCK.argspec = _INTLCODE_WITH_CONTEXT
    ast_POP_ALL_BLOCKS.argspec = _INTLCODE_WITH_CONTEXT

    def ast_DISCARD_LAST_BLOCK_MESSAGE(self):
        """ """
        self.buffer.set_next_token_firstterm() # 次にバッファから読みだすトークンはfirsttermになる

    #
    #  引数を構築する
    #
    def arg_REF_NAME(self, context, name):
        """ """
        return ObjectRef(name)

    def arg_STRING(self, context, value):
        """ """
        return context.new_object(value, type="Str")

    def arg_TYPE(self, context, typeexpr):
        """ """
        return select_type(context, typeexpr)

    def arg_TUPLE(self, context, value):
        """ """
        elems = value.split() # 文字列を空白で区切る
        return context.get_type("Tuple").construct_obj(context, elems)

    def arg_LITERAL(self, context, value):
        """ """
        return select_literal(context, value)

    def arg_TYPED_VALUE(self, context, value, spec):
        """ """
        type = spec.get_typedecl().instance(context)
        return type.construct_obj(context, value)

    def arg_RECIEVER_VALUE(self, context, value):
        """ """
        return select_reciever(context, value)

    def arg_SELECTOR_VALUE(self, context, selector):
        """ """
        return SelectorResolver(selector)

    def arg_LAMBDA_ARG_MEMBER(self, context, evalcontext, name):
        """ """
        reciever = SubjectRef()
        if name:
            value = reciever.pick_object(evalcontext)
            selector = select_method(name, value.type, reciever=value.value)
            return (reciever, selector)
        else:
            return (reciever, )
        
    arg_LAMBDA_ARG_MEMBER.argspec = _INTLCODE_WITH_EVALCONTEXT

    def arg_ROOT_MEMBER(self, context, member_id):
        """ """
        rt = context.get_type("RootObject")
        rv = rt.value_type(context)
        root = rt.new_object(rv)
        if member_id:
            selector = select_method(member_id, root.type, reciever=root.value)
            return (root, selector)
        else:
            return (root, )
    
    #
    #
    #
    def produce_message_1st(self, evalcontext):
        """ コードから構文を組み立てつつ随時実行 """
        self._msgs = []
        for token, tokentype in self.read_token(self.source):
            reading = self.current_reading_message()
            intlcode = self.compile_code(reading, token, tokentype)
            if intlcode is None:
                break
            evalcontext.context.log(LOG_MESSAGE_CODE, intlcode)

            # これから評価するメッセージ式の文字列を排出
            yield self._lastread.strip()
            self._lastread = ""

            # 内部コードを実行する 
            intlcode.run(evalcontext)

            # メッセージを組み立てる
            for msg in self.complete_messages():
                yield msg # 組み立てたメッセージを排出
                self._msgs.append(msg)
    
    def produce_message_cached(self, _evalcontext):
        """ キャッシュされたメッセージをクリアして返す """
        for msg in self._msgs:
            msg.reset_ref()
            yield msg

    def runner(self, context, cache=False):
        """
        メッセージをコンパイルしつつ実行するジェネレータ。
        Yields:
            Message: 実行直前のメッセージ
        """                    
        if cache and self._msgs:
            produce_message = self.produce_message_cached
        else:
            produce_message = self.produce_message_1st

        context.log(LOG_MESSAGE_BEGIN, self.source)

        evalcxt = EvalContext(context)
        self._lastevalcxt = evalcxt
        try:
            for msg in produce_message(evalcxt):
                if isinstance(msg, str):
                    yield msg
                    continue
                else:
                    yield msg
                    result = msg.eval(evalcxt)

                    # 返り値をスタックに乗せる
                    evalcxt.locals.push_local_object(result)
                    if context.is_failed(): # エラーが発生したら実行を中断する
                        return

        except Exception as e:
            # メッセージ実行以外の場所でエラーが起きた
            err = InternalMessageError(e,self) # コード情報を付加し、トレース情報を引き継ぐ
            evalcxt.locals.push_local_object(context.new_invocation_error_object(err)) # スタックに乗せる
            context.push_extra_exception(err)
            return

        context.log(LOG_MESSAGE_END)
    
    def finish(self, locals, *, raiseerror=False) -> Object:
        """ 結果を取得し、スタックをクリアする """
        returns = self._lastevalcxt.locals.clear_local_objects() # 返り値はローカルスタックに置かれている
        if not returns:
            raise BadExpressionError("At least 1 result must be returned, but none on stack")
        ret = returns[-1]

        self._readings.clear()
    
        if raiseerror and ret.is_error(): # エラーを伝播する
            raise ret.value.error

        return ret
    
    def start_subcontext(self, subject, context):
        """ 入れ子のコンテキストを開始する """
        subcontext = context.inherit(subject) # コンテキストが入れ子になる
        context.log(LOG_RUN_FUNCTION, subcontext)
        return subcontext
    
    #
    #
    #
    def run(self, subject, context, *, cache=False):
        """ コンテキストを継承してメッセージを実行 """
        if subject is not None:
            # 主題オブジェクトを更新した派生コンテキスト
            subcontext = self.start_subcontext(subject, context)
        else:
            # コンテキストを引き継ぐ
            subcontext = context 
        for _ in self.runner(subcontext, cache=cache):
            pass
        return self.finish(subcontext, raiseerror=context.is_set_raise_error())

    def run_here(self, context, *, cache=False) -> Object:
        """ 現在のコンテキストでメッセージを実行 """
        for _ in self.runner(context, cache=cache):
            pass
        return self.finish(context, raiseerror=context.is_set_raise_error())

    def run_step(self, subject, context, *, cache=False):
        """ 実行するたびにメッセージを返す """
        subcontext = self.start_subcontext(subject, context)
        for step in self.runner(subcontext, cache=cache):
            yield step
        yield self.finish(subcontext, raiseerror=context.is_set_raise_error()) # Objectを返す
    
    def run_print_step(self, subject, context, *, cache=False):
        """ 実行過程を表示する """
        app = context.spirit
        indent = "  " * (context.get_depth()-1)
        for msg in self.run_step(subject, context, cache=cache):
            app.interruption_point()
            if isinstance(msg, Object):
                return msg
            elif isinstance(msg, str):
                app.post("message", indent + msg)
    
    def run_function(self, subject, context, *, cache=False) -> Object:
        """ 通常の実行方法：コンテキストのフラグによって実行方法を分岐する """
        if context.is_set_print_step():
            return self.run_print_step(subject, context, cache=cache)
        else:
            return self.run(subject, context, cache=cache)


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
        context.set_flags(INVOCATION_FLAG_RAISE_ERROR, inherit_set=True)

    f = MessageEngine(expression)
    return f.run_function(subject, context)
    
def run_function_print_step(expression: str, subject, context, *, raiseerror=False):
    """
    経過を表示しつつメッセージを実行する。
    """
    context.set_flags(INVOCATION_FLAG_PRINT_STEP)
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


class MemberGetExpression(FunctionExpression):
    """
    主題オブジェクトのメンバ（引数0のメソッド）を取得する
    Functionの機能制限版だが、キャッシュを利用する
    """
    def __init__(self, name, typeconv):
        self.name = name
        self.typeconv = typeconv

    def get_expression(self) -> str:
        return self.name
    
    def get_type_conversion(self):
        return self.typeconv
    
    def run(self, subject, context, **kwargs):
        """ その場でメッセージを構築し実行 """
        subcontext = context.inherit(subject)
        
        inv = select_method(self.name, subject.type, reciever=subject.value)
        message = Message(subject, inv)
        subcontext.log(LOG_MESSAGE_BEGIN, "@ {}".format(self.name))
        
        evalcontext = EvalContext(subcontext)
        result = message.eval(evalcontext)
        context.log(LOG_RUN_FUNCTION, subcontext)
        
        return result
    
    def run_here(self, context, **kwargs):
        """ コンテクストそのままで実行 """
        subject = context.subject_object
        inv = select_method(self.name, subject.type, reciever=subject.value)
        message = Message(subject, inv)
        
        evalcontext = EvalContext(context)
        result = message.eval(evalcontext)
        return result


def parse_function(expression):
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
    
    parts = body.split()
    if len(parts) > 1:
        return MessageExpression(body, typeconv)
    
    elif len(parts) == 1:
        return MemberGetExpression(body, typeconv)
    
    else:
        raise ValueError("Invalid expression")


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

    def set_subject_type(self, conversion):
        self._subjecttype = self.context.instantiate_type(conversion)
    
    def run(self, subject, _context=None, **kwargs) -> Object:
        """ 共通メンバの実装 オブジェクトを返す """
        self.context.set_subject(subject) # subjecttypeは無視する
        return self.f.run_here(self.context, cache=self.cached)
        
    def run_here(self, _context=None, **kwargs) -> Object:
        """ 共通メンバの実装  """
        return self.f.run_here(self.context, cache=self.cached)

    def __call__(self, arg) -> Any:
        """ コード内で実行する（複数の引数に対応） 値を返す"""
        argvalue = self._argforge(arg)
        subject = self.context.new_object(argvalue, type=self._subjecttype)
        self.context.set_subject(subject)
        o = self.f.run_here(self.context, cache=self.cached) # 同じコンテキストで実行
        return o.value
    
    def nousecache(self):
        """ メッセージのキャッシュを使用しない """
        self.cached = False
    
    @classmethod
    def instant(cls, expression):
        # 文字列を受け取り、即席のコンテキストでインスタンスを作る
        from machaon.core.invocation import instant_context
        cxt = instant_context()
        return parse_sequential_function(expression, cxt)


def parse_sequential_function(expression, context, argspec=None):
    fn = parse_function(expression)
    return SequentialMessageExpression(context, fn, argspec)

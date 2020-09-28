import ast
import sys
from itertools import zip_longest
from typing import Dict, Any, List, Sequence, Optional, Generator, Tuple, Union

from machaon.object.symbol import python_builtin_typenames
from machaon.object.type import Type, TypeModule
from machaon.object.object import Object
from machaon.object.method import Method
from machaon.object.invocation import (
    INVOCATION_NEGATE_RESULT, INVOCATION_REVERSE_ARGS,
    BasicInvocation,
    TypeMethodInvocation,
    InstanceMethodInvocation,
    FunctionInvocation
)


# imported from...
# desktop
# object
#
#

#
# ----------------------------------------------------------------------------
#
#
#
# ----------------------------------------------------------------------------

#
class BadExpressionError(Exception):
    pass

class MessageError(Exception):
    def __init__(self, error, message):
        self.error = error
        self.message = message

#
#
#
class Message:
    def __init__(self, 
        reciever = None, 
        selector = None, 
        args = None
    ):
        self.reciever = reciever # type: Union[Object, LeafResultRef, None]
        self.selector = selector # type: Union[BasicInvocation, None]
        self.args = args or []   # type: List[Union[Object, LeafResultRef]]
        self._argsend = False
    
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
    
    def end_arg(self):
        self._argsend = True
    
    def is_reciever_specified(self):
        return self.reciever is not None
    
    def is_selector_specified(self):
        return self.selector is not None

    def is_max_arg_specified(self):
        if self.selector:
            return len(self.args) >= self.selector.get_max_arity()-1
        return False
    
    def is_min_arg_specified(self):        
        if self.selector:
            return len(self.args) >= self.selector.get_min_arity()-1
        return False
    
    def is_specified(self):
        return (
            self.is_reciever_specified() 
            and self.is_selector_specified() 
            and (self._argsend or self.is_max_arg_specified())
        )

    def is_selector_parameter_consumer(self):
        if self.selector:
            return self.selector.is_parameter_consumer()
        return False
    
    def is_task(self):
        if self.selector:
            return self.selector.is_task()
        return False
    
    #
    def eval(self, context) -> Optional[Object]:
        if self.reciever is None or self.selector is None:
            raise ValueError()

        args = []

        # コンテキスト引数を取り出す。スタックにあるかもしれないので、逆順に
        revargs = [*reversed(self.args), self.reciever]
        for argobj in revargs:
            if isinstance(argobj, ResultStackTopRef):
                args.append(argobj.pick_object(context))
            else:
                args.append(argobj)

        # 実行する
        args.reverse() # 元の順番に戻す
        self.selector.invoke(context, *args)

        # 返り値（一つだけ）
        ret = context.get_last_result()
        if ret is not None:
            rettype = context.select_type(ret.typecode)
            return Object(rettype, ret.value)

        return None
        
    def get_result_typename(self) -> str:
        if self.selector is None:
            raise ValueError("")
        typenames = self.selector.get_result_typenames()
        if not typenames:
            raise ValueError("返り値の型を導出できません")
        return typenames[0]

    #
    # デバッグ用
    #
    def sexprs(self):
        # S式風に表示：不完全なメッセージであっても表示する
        exprs = []

        def put(item):
            if isinstance(item, Object):
                exprs.append("<{} {}>".format(item.get_typename(), item.value))
            elif isinstance(item, ResultStackTopRef):
                exprs.append("<#ResultStackTopRef>")
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

    # コピーを返す
    def snapshot(self):
        return Message(self.reciever, self.selector, self.args[:])


# スタックにおかれた計算結果を取り出す
class ResultStackTopRef:
    def __init__(self):
        self._lastvalue = None
    
    def pick_object(self, context):
        if self._lastvalue is None:
            value = context.top_local_object()
            if value is None:
                raise BadExpressionError("ローカルスタックを参照しましたが、値がありません")
            self._lastvalue = value
            context.pop_local_object()
        return self._lastvalue

# --------------------------------------------------------------------
#
# メッセージの構成要素
#
# --------------------------------------------------------------------
# 外部オブジェクト参照
def select_object(context, *, name=None, typename=None) -> Object:
    if name == "app":
        return Object(context.get_type("ThisContext"), context)
    elif typename:
        obj = context.get_object_by_type(typename)
        if obj is None:
            raise BadExpressionError("オブジェクト（型='{}'）は存在しません".format(typename))
    else:
        obj = context.get_object(name)
        if obj is None:
            raise BadExpressionError("オブジェクト'{}'は存在しません".format(name))
    return obj

# リテラル
def select_literal(context, literal) -> Object:
    try:
        value = ast.literal_eval(literal)
    except Exception:
        value = literal
    return value_to_obj(context, value)

def value_to_obj(context, value):
    typename = type(value).__name__
    if typename not in python_builtin_typenames:
        raise BadExpressionError("Unsupported literal type: {}".format(typename))
    return Object(context.get_type(typename), value)

# 無名関数の引数オブジェクト
def select_lambda_subject(context):
    subject = context.subject_object
    if subject is None:
        raise BadExpressionError("無名関数の引数を参照しましたが、与えられていません")
    return subject

# 型名かリテラルか
def select_reciever(context, expression) -> Object:
    # 型名の可能性
    tt = context.get_type(expression)
    if tt is not None:
        return Object(context.get_type("Type"), tt)
    
    # リテラルだった
    return select_literal(context, expression)

# if Fun ->{ @ name == Str -> Qlifo }
# if Fun -> 「@ name == Str -> 『Qlifo』」 

# メソッド
def select_method(name, typetraits=None, *, modbits=None) -> BasicInvocation:
    # モディファイアを分離する
    if modbits is None:
        def startsmod(sigil, value, expr, bits):
            if expr.startswith(sigil):
                return (expr[len(sigil):], value|bits)
            else:
                return (expr, bits)
        
        modbits = 0
        name, modbits = startsmod("~", INVOCATION_REVERSE_ARGS, name, modbits)
        name, modbits = startsmod("!", INVOCATION_NEGATE_RESULT, name, modbits)
        name, modbits = startsmod("not-", INVOCATION_NEGATE_RESULT, name, modbits)

    # 外部関数
    if name.startswith(SIGIL_IMPORT_TARGET):
        from machaon.object.importer import attribute_loader
        loader = attribute_loader(name[1:].strip())
        if loader:
            modfn = loader(fallback=True)
            if modfn:
                return FunctionInvocation(modfn, modbits)

    # 型メソッド
    if typetraits is not None:
        meth = typetraits.select_method(name)
        if meth is not None:
            return TypeMethodInvocation(meth, modbits)
    
    # グローバル定義の関数
    from machaon.object.generic_method import resolve_generic_method
    genfn = resolve_generic_method(name)
    if genfn is not None:
        return FunctionInvocation(genfn, modbits)

    if typetraits is not None and typetraits.has_no_instance_method():
        raise BadExpressionError("Method '{}' is not found in '{}' (instance method is excluded)".format(name, typetraits.typename))
    
    # インスタンスメソッド
    return InstanceMethodInvocation(name, modbits)

#
# 型で利用可能なセレクタを列挙する
#
def enum_selectable_method(typetraits) -> Generator[Tuple[BasicInvocation, Method], None, None]:
    # 型メソッドの列挙
    for meth in typetraits.enum_methods():
        tinv = TypeMethodInvocation(meth)
        yield tinv, tinv.query_method(typetraits)
    
    if typetraits.has_no_instance_method():
        return
    
    # インスタンスメソッド
    valtype = typetraits.get_value_type()
    for name in dir(valtype):
        if name.startswith("__"):
            continue
        inv = InstanceMethodInvocation(name)
        meth = inv.query_method(typetraits)
        if meth is None:
            continue
        yield inv, meth

#
def select_constant(context, expr) -> Object:
    from machaon.object.importer import attribute_loader
    loader = attribute_loader(expr)
    if not loader:
        raise BadExpressionError("bad import expression")
    attr = loader()
    if(callable(attr)):
        value = attr()
    else:
        value = attr
    return value_to_obj(context, value)

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

EXPECT_NOTHING = 0
EXPECT_RECIEVER = 0x10
EXPECT_SELECTOR = 0x20
EXPECT_ARGUMENT = 0x40

TERM_NOTHING = 0
TERM_LAST_BLOCK_RECIEVER = 3
TERM_LAST_BLOCK_SELECTOR = 4
TERM_LAST_BLOCK_ARG = 5
TERM_NEW_BLOCK_AS_LAST_RECIEVER = 6
TERM_NEW_BLOCK_AS_LAST_ARG = 7
TERM_NEW_BLOCK_ISOLATED = 8
TERM_NEW_BLOCK_RECIEVER = 9
TERM_NEW_BLOCK_SELECTOR = 10

TERM_END_LAST_BLOCK = 0x20
TERM_END_ALL_BLOCK = 0x40

TERM_OBJ_REF_NAME = 0x0100
TERM_OBJ_REF_TYPENAME = 0x0200
TERM_OBJ_STRING = 0x0300
TERM_OBJ_RECIEVER = 0x0400
TERM_OBJ_SELECTOR = 0x0500
TERM_OBJ_LAMBDA_ARG = 0x0600
TERM_OBJ_LAMBDA_ARG_MEMBER = 0x0700
TERM_OBJ_LITERAL = 0x0800
TERM_OBJ_CONSTANT = 0x0900
TERM_OBJ_NOTHING = 0x0A00

SIGIL_RIGHTFIRST_EVALUATION = "$"
SIGIL_OBJECT_ID = "$"
SIGIL_LAMBDA_SUBJECT = "@"
SIGIL_IMPORT_TARGET = "."

#
#
#
class MessageTokenBuffer():
    def __init__(self):
        self.buffer = [] # type: List[str]
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

        if not self.quoting():
            if string == "->":
                self.quote_char_waiting = True
                self.begin_quote(string, None)
            elif string == "-->":
                self.begin_quote(string, None)
        
        if self.firstterm and (tokentype & TOKEN_TERM): 
            tokentype |= TOKEN_FIRSTTERM
            self.firstterm = False
        
        return (string, tokentype)
    
    def quoting(self):
        return self.quote_beg is not None
    
    def begin_quote(self, newch, endch):
        self.quote_beg = newch
        self.quote_end = endch
        self.buffer.clear()
    
    def wait_quote_begin_char(self, newch):
        if self.quote_char_waiting:
            if not newch.isspace():
                self.quote_char_waiting = False
                self.quote_beg = newch
                self.quote_end = newch
                return True
        return False

    def wait_quote_end(self, newch):
        if not self.quoting() or self.quote_end is None:
            return False
        
        if len(self.quote_end) > 1:
            endlen = len(self.quote_end)
            for i in range(1, endlen):
                if self.buffer[-i] != self.quote_end[-i-1]:
                    return False
        
        if newch != self.quote_end[-1]:
            return False
        
        offset = len(self.quote_end)-1
        if offset>0:
            self.buffer = self.buffer[:-offset]
        
        self.quote_beg = None
        self.quote_end = None
        return True

    def add(self, ch):
        self.buffer.append(ch)

#
#
#
class MessageEngine():
    def __init__(self, expression=""):
        self.source = expression

        self._tokens = []    # type: List[Tuple[str, int]]
        self._readings = []  # type: List[Message]
        self._codes = []     # type: List[Tuple[int, Tuple[Any,...]]]

        self._temp_result_stack = []
        self.log = []

    # 入力文字列をトークンに
    def read_token(self, source) -> Generator[Tuple[str, int], None, None]:
        buffer = MessageTokenBuffer()
        paren_count = 0
        for ch in source:
            if buffer.wait_quote_begin_char(ch):
                continue

            if buffer.wait_quote_end(ch):
                if buffer.flush(): 
                    yield buffer.token(TOKEN_TERM|TOKEN_STRING)
                continue
            
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
                elif ch.isspace():
                    if buffer.flush(): 
                        yield buffer.token(TOKEN_TERM)
                else:
                    buffer.add(ch)
        
        if paren_count > 0:
            raise SyntaxError("終わり括弧が足りません")
        
        if buffer.flush():
            if buffer.quoting():
                yield buffer.token(TOKEN_TERM|TOKEN_ALL_BLOCK_END|TOKEN_STRING)
            else:
                yield buffer.token(TOKEN_TERM|TOKEN_ALL_BLOCK_END)
        else:
            yield buffer.token(TOKEN_ALL_BLOCK_END)

    # 構文を組み立てる
    def build_message(self, reading, token: str, tokentype: int) -> Tuple: # (int, Any...)
        tokenbits = 0

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

        # ブロック終了指示
        if tokentype & TOKEN_BLOCK_END:
            tokenbits |= TERM_END_LAST_BLOCK
        elif tokentype & TOKEN_ALL_BLOCK_END:
            tokenbits |= TERM_END_ALL_BLOCK

        # 意味を無視して全体を文字列引数とみなす
        if tokentype & TOKEN_STRING:
            if expect == EXPECT_SELECTOR:
                raise BadExpressionError("文字列はセレクタになりません")

            tokenbits |= TERM_OBJ_STRING
            if expect == EXPECT_ARGUMENT:
                return (tokenbits | TERM_LAST_BLOCK_ARG, token) 
                
            if expect == EXPECT_RECIEVER:
                return (tokenbits | TERM_LAST_BLOCK_RECIEVER, token) 

            if expect == EXPECT_NOTHING:
                return (tokenbits | TERM_NEW_BLOCK_RECIEVER, token) 

        # ブロック開始指示
        if tokentype & TOKEN_BLOCK_BEGIN:
            if expect == EXPECT_SELECTOR:
                raise BadExpressionError("メッセージはセレクタになりません")

            tokenbits |= TERM_OBJ_NOTHING
            if expect == EXPECT_RECIEVER:
                return (tokenbits | TERM_NEW_BLOCK_AS_LAST_RECIEVER, )

            if expect == EXPECT_ARGUMENT:
                return (tokenbits | TERM_NEW_BLOCK_AS_LAST_ARG, )

            if expect == EXPECT_NOTHING: 
                return (tokenbits | TERM_NEW_BLOCK_ISOLATED, )
        
        # 引数リストの終わり
        if token == SIGIL_RIGHTFIRST_EVALUATION:
            if expect == EXPECT_SELECTOR or expect == EXPECT_NOTHING:
                raise BadExpressionError("'{}'演算子は、レシーバまたは引数リストの文脈でのみ使えます".format(SIGIL_RIGHTFIRST_EVALUATION))
            
            tokenbits |= TERM_OBJ_NOTHING
            if expect == EXPECT_RECIEVER:
                return (tokenbits | TERM_NEW_BLOCK_AS_LAST_RECIEVER, )

            if expect == EXPECT_ARGUMENT:
                return (tokenbits | TERM_NEW_BLOCK_AS_LAST_ARG, )

        # メッセージの要素ではない
        if (tokentype & TOKEN_TERM) == 0:
            return (tokenbits | TERM_OBJ_NOTHING, )

        #
        # 以下、メッセージの要素として解析
        #

        # オブジェクト参照
        if token.startswith(SIGIL_OBJECT_ID):
            if expect == EXPECT_SELECTOR:
                raise BadExpressionError("セレクタが必要です") 

            objid = token[1:]
            if objid and objid[0].isupper(): # 大文字なら型とみなす
                tokenbits |= TERM_OBJ_REF_TYPENAME
            else:
                tokenbits |= TERM_OBJ_REF_NAME

            if expect == EXPECT_ARGUMENT:
                return (tokenbits | TERM_LAST_BLOCK_ARG, objid) # 前のメッセージの引数になる
            
            if expect == EXPECT_RECIEVER:
                return (tokenbits | TERM_LAST_BLOCK_RECIEVER, objid) # 新しいメッセージのレシーバになる
            
            if expect == EXPECT_NOTHING:
                return (tokenbits | TERM_NEW_BLOCK_RECIEVER, objid) # 新しいメッセージのレシーバになる

        # 無名関数の引数
        if token.startswith(SIGIL_LAMBDA_SUBJECT):
            key = token[1:]
            if key:
                tokenbits |= TERM_OBJ_LAMBDA_ARG_MEMBER
                if expect == EXPECT_ARGUMENT:
                    return (tokenbits | TERM_NEW_BLOCK_AS_LAST_ARG, key) # 前のメッセージの引数になる

                if expect == EXPECT_RECIEVER:
                    return (tokenbits | TERM_NEW_BLOCK_AS_LAST_RECIEVER, key) # 前のメッセージのレシーバになる
                
                if expect == EXPECT_NOTHING:
                    return (tokenbits | TERM_NEW_BLOCK_RECIEVER, key) # 新しいメッセージのレシーバになる

            else:
                tokenbits |= TERM_OBJ_LAMBDA_ARG
                if expect == EXPECT_ARGUMENT:
                    return (tokenbits | TERM_LAST_BLOCK_ARG, ) # 前のメッセージの引数になる

                if expect == EXPECT_RECIEVER:
                    return (tokenbits | TERM_LAST_BLOCK_RECIEVER, ) # 前のメッセージのレシーバになる
                
                if expect == EXPECT_NOTHING:
                    return (tokenbits | TERM_NEW_BLOCK_RECIEVER, ) # 新しいメッセージのレシーバになる

        # 外部関数呼び出し
        if token.startswith(SIGIL_IMPORT_TARGET):
            if expect == EXPECT_SELECTOR:
                tokenbits |= TERM_OBJ_SELECTOR
                return (tokenbits | TERM_LAST_BLOCK_SELECTOR, token) # SIGILはselect_methodで取り除く（モディファイアに対応）
                
            # 定数表現として扱い、引数なしで呼び出される
            path = token[1:]
            tokenbits |= TERM_OBJ_CONSTANT
            if expect == EXPECT_ARGUMENT:
                return (tokenbits | TERM_LAST_BLOCK_ARG, path) # 前のメッセージの引数になる
            
            if expect == EXPECT_RECIEVER:
                return (tokenbits | TERM_LAST_BLOCK_RECIEVER, path) # 新しいメッセージのレシーバになる
            
            if expect == EXPECT_NOTHING:
                return (tokenbits | TERM_NEW_BLOCK_RECIEVER, path) # 新しいメッセージのレシーバになる

        # 何も印のない文字列
        #  => メソッドかリテラルか、文脈で判断
        if expect == EXPECT_SELECTOR and reading:
            tokenbits |= TERM_OBJ_SELECTOR
            return (tokenbits | TERM_LAST_BLOCK_SELECTOR, token) # 前のメッセージのセレクタになる

        if expect == EXPECT_ARGUMENT:
            tokenbits |= TERM_OBJ_LITERAL
            return (tokenbits | TERM_LAST_BLOCK_ARG, token) # 前のメッセージの引数になる

        if expect == EXPECT_RECIEVER:
            tokenbits |= TERM_OBJ_RECIEVER
            return (tokenbits | TERM_LAST_BLOCK_RECIEVER, token) 

        if expect == EXPECT_NOTHING:
            if tokentype & TOKEN_FIRSTTERM:
                # メッセージの先頭のみ、レシーバオブジェクトのリテラルとする
                tokenbits |= TERM_OBJ_RECIEVER
                return (tokenbits | TERM_NEW_BLOCK_RECIEVER, token) 
            else:
                # 先行するメッセージをレシーバとするセレクタとする
                tokenbits |= TERM_OBJ_SELECTOR
                return (tokenbits | TERM_NEW_BLOCK_SELECTOR, token)
        
        raise BadExpressionError("Could not parse")

    # 構文木を組みたてつつ、完成したところからどんどん実行
    def reduce_step(self, code, values, context) -> Generator[Message, None, None]:
        astcode = code & 0x000F
        astinstr = code & 0x00F0
        objcode = code & 0xFF00

        # 文字列や値をオブジェクトに変換
        objs: Tuple[Any,...] = () #

        obj = None
        if objcode == TERM_OBJ_REF_NAME:
            obj = select_object(context, name=values[0])

        elif objcode == TERM_OBJ_REF_TYPENAME:
            obj = select_object(context, typename=values[0])

        elif objcode == TERM_OBJ_STRING:
            obj = Object(context.get_type("Str"), values[0])

        elif objcode == TERM_OBJ_LITERAL:
            obj = select_literal(context, values[0])

        elif objcode == TERM_OBJ_RECIEVER:
            obj = select_reciever(context, values[0])

        elif objcode == TERM_OBJ_SELECTOR:
            obj = values[0]
            
        elif objcode == TERM_OBJ_LAMBDA_ARG:
            obj = select_lambda_subject(context)
        
        elif objcode == TERM_OBJ_LAMBDA_ARG_MEMBER:
            subject = select_lambda_subject(context)
            method = select_method(values[0], subject.type)
            objs = (subject, method)
            
        elif objcode == TERM_OBJ_CONSTANT:
            obj = select_constant(context, values[0])
        
        elif objcode == TERM_OBJ_NOTHING:
            pass

        else:
            raise BadExpressionError("不明な生成コードに遭遇：{}".format(objcode))
            
        if obj is not None: objs = (obj,)

        # メッセージを構築する
        if astcode == TERM_LAST_BLOCK_RECIEVER:
            self._readings[-1].set_reciever(objs[0])

        elif astcode == TERM_LAST_BLOCK_SELECTOR:
            reciever = self._readings[-1].reciever
            if isinstance(reciever, ResultStackTopRef):
                reciever = reciever.pick_object(context)
            selector = select_method(objs[0], reciever.type)
            self._readings[-1].set_selector(selector)

        elif astcode == TERM_LAST_BLOCK_ARG:
            self._readings[-1].add_arg(objs[0])

        elif astcode == TERM_NEW_BLOCK_AS_LAST_RECIEVER:
            self._readings[-1].set_reciever(ResultStackTopRef())
            new_msg = Message(*objs)
            self._readings.append(new_msg)

        elif astcode == TERM_NEW_BLOCK_AS_LAST_ARG:
            self._readings[-1].add_arg(ResultStackTopRef())
            new_msg = Message(*objs)
            self._readings.append(new_msg)
        
        elif astcode == TERM_NEW_BLOCK_ISOLATED:
            new_msg = Message()
            self._readings.append(new_msg)
            
        elif astcode == TERM_NEW_BLOCK_RECIEVER:
            new_msg = Message(*objs)
            self._readings.append(new_msg)
        
        elif astcode == TERM_NEW_BLOCK_SELECTOR:
            resultref = ResultStackTopRef()
            reciever = resultref.pick_object(context) # ローカルオブジェクトを一つ消費
            selector = select_method(objs[0], reciever.type)
            new_msg = Message(reciever, selector)
            self._readings.append(new_msg)

        if astinstr & TERM_END_LAST_BLOCK:
            msg = self._readings[-1]
            if not msg.is_min_arg_specified():
                raise BadExpressionError("引数が足りません：{}".format(msg.sexprs()))
            msg.end_arg()
            
        if astinstr & TERM_END_ALL_BLOCK:
            for msg in self._readings:
                if not msg.is_min_arg_specified():
                    raise BadExpressionError("引数が足りません：{}".format(msg.sexprs()))
                msg.end_arg()

        # 完成したメッセージをキューから取り出す
        completed = 0
        for msg in reversed(self._readings):
            if msg.is_specified():
                yield msg
                result = self._temp_result_stack.pop()
                context.push_local_object(result) # スタックに乗せる
                completed += 1
            else:
                break

        if completed>0:
            del self._readings[-completed:]
    
    # トークン解析のキャッシュを参照する
    def tokenize(self, source) -> Generator[Tuple[str, int], None, None]:
        tokens = []
        if not self._tokens:
            for token, tokentype in self.read_token(source):
                tokens.append((token, tokentype))
                yield token, tokentype
            self._tokens = tokens
        else:
            yield from self._tokens

    # メッセージを実行するジェネレータ。実行前にメッセージを返す
    def runner(self, context, *, log) -> Generator[Message, None, None]:
        logger = self._begin_logger()
        
        # コードから構文を組み立てつつ随時実行
        if not self._codes:
            def build_run_codes():
                for token, tokentype in self.tokenize(self.source):
                    logger(0, token, tokentype)
                    reading = self._readings[-1] if self._readings else None
                    code, *values = self.build_message(reading, token, tokentype)
                    yield (code, values)
        else:
            # キャッシュを利用する
            def build_run_codes():
                for code, values in self._codes:
                    logger(0, "", TOKEN_NOTHING)
                    yield (code, values)

        coderuniter = build_run_codes()
        codes = []
        while True:
            completemsgs = []
            try:
                code, values = next(coderuniter, (None, None))
                if code is None:
                    break

                logger(1, code, values)

                for msg in self.reduce_step(code, values, context):
                    yield msg
                    result = msg.eval(context)
                    if result is None:
                        return # エラー発生

                    self._temp_result_stack.append(result) # reduce_stepのジェネレータへの受け渡しにのみ使用するスタック
                    completemsgs.append(msg)
            
            except Exception as e:
                err = MessageError(e, self) # コード情報を付加する
                err.with_traceback(e.__traceback__) # 引き継ぐ
                context.set_pre_invoke_error(err)
                logger(-1, e)
                break

            if completemsgs is None:
                logger(-1, context.get_last_exception())
                return
            else:
                logger(2, completemsgs, self._readings)
            
            codes.append((code, values))

        if not context.is_failed():
            self._codes = codes
    
    # 実行
    def run(self, context, *, log=False, runner=None) -> Tuple[Any,...]:
        if runner is None:
            # タスク含め全てを同期で実行する
            runner = self.runner(context, log=log)
        for _ in runner: pass

        # 返り値はローカルスタックに置かれている
        returns = context.clear_local_objects()
        return tuple(returns)

    # ログを追記する
    def _logger(self, state, *values):
        if state == 0:
            self.log.append([])
            token, tokentype = values
            values = (token, tokentype)
        elif state == 1:
            code, vals = values
            values = (code, vals)
        elif state == 2:
            completes, readings = values
            values = (completes, [x.snapshot() for x in readings])
        elif state == -1:
            self.log.append([])
            err = values[0]
            msg = ["!!! Error occurred on evaluation:", "{} {}".format(type(err).__name__, err)]
            import traceback
            _, _, tb = sys.exc_info()
            for line in traceback.format_tb(tb):
                msg.append(line.rstrip())
            
            values = ("\n".join(msg), )

        self.log[-1].extend(values)
    
    def _begin_logger(self, *, dummy=False):
        self.log = []
        if dummy:
            def logger(state, *values):
                pass
        else:
            logger = self._logger
        return logger

    # 蓄積されたログを出力する
    def pprint_log(self, printer=None, *, logs=None, columns=None):
        if printer is None: printer = print
        if logs is None: logs = self.log
        if columns is None: 
            columns = range(6)
        else:
            columns = range(columns[0], columns[1])

        printer("Message: {}".format(self.source))
        if not logs:
            printer(" --- no log ---")
            return
        
        for i, logrow in enumerate(logs):
            printer("[{}]-----------------".format(i))
            for i, value in zip(columns, logrow):
                if i == 0:
                    title = "token"
                    s = value
                elif i == 1:
                    title = "token-type"
                    s = view_tokentypes(value)
                elif i == 2:
                    title = "meaning"
                    s = view_term_constant(value)
                elif i == 3:
                    title = "yielded"
                    s = ", ".join([str(x) for x in value])
                elif i == 4:
                    title = "done-branch"
                    s = "".join([x.sexprs() for x in value])
                elif i == 5:
                    title = "reading-branch"
                    s = "".join([x.sexprs() for x in value])

                pad = 16-len(title)
                printer(" {}:{}{}".format(title, pad*" ", s))

# ログ表示用に定数名を得る
def _view_constant(prefix, code):
    for k, v in globals().items():
        if k.startswith(prefix) and v==code:
            return k
    else:
        return "<定数=0x{:0X}（{}***）の名前は不明です>".format(code, prefix)

# TERM_XXX 
def view_term_constant(code):
    astcode = code & 0x000F
    astinstr = code & 0x00F0
    objcode = code & 0xFF00
    codename = _view_constant("TERM_", astcode)
    codename += "+" + _view_constant("TERM_", objcode)
    if astinstr:
        codename += "+" + _view_bitflag("TERM_", astinstr)
    return codename

# ビットフラグ
def _view_bitflag(prefix, code):
    c = code
    n = []
    for k, v in globals().items():
        if k.startswith(prefix) and v & c:
            n.append(k)
            c = (c & ~v)
    if c!=0:
        n.append("0x{0X}".format(c))
    return "+".join(n)
    
def view_tokentypes(flags):
    return _view_bitflag("TOKEN_", flags)

#
# 引数を一つとりメッセージを実行する
#
class Function():
    def __init__(self, expr: str):
        self.message = MessageEngine(expr)
    
    def get_expr(self):
        return self.message.source
    
    def compile(self, context):
        for _ in self.message.tokenize(context): pass

    def run(self, subject, context, log=False) -> Tuple[Any,...]:
        context.set_subject(subject)
        returns = self.message.run(context, log=log)
        context.clear_subject() # 主題をクリアする
        return returns

#
# 主題オブジェクトのメンバ（引数0のメソッド）を取得する
# Functionの機能制限版だが、キャッシュを利用する
#
class MemberGetter():
    def __init__(self, name, method):
        self.name = name
        self.method = method
        
    def get_expr(self):
        return self.name
    
    def run(self, subject, context, log=False):
        # 直にメッセージを記述
        message = Message(subject, self.method)
        result = message.eval(context)
        return (result,)


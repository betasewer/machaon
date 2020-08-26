import ast
from itertools import zip_longest
from typing import Dict, Any, List, Sequence, Optional, Generator, Tuple, Union

from machaon.object.type import TypeTraits, TypeModule
from machaon.object.object import Object
from machaon.object.invocation import (
    INVOCATION_NEGATE_RESULT, INVOCATION_REVERSE_ARGS,
    BasicInvocation,
    TypeMethodInvocation,
    InstanceMethodInvocation,
    StaticMethodInvocation
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
    
    def is_specified(self, *, minarg=False):
        return (
            self.is_reciever_specified() 
            and self.is_selector_specified() 
            and (self.is_min_arg_specified() if minarg else self.is_max_arg_specified())
        )
    
    def is_child_element(self, msg):
        for elem in (self.reciever, self.selector, *self.args):
            if isinstance(elem, Message) and elem is msg:
                return True
        return False
    
    #
    def eval(self, context) -> Optional[Object]:
        if self.reciever is None or self.selector is None:
            raise ValueError()

        args = []

        # コンテキスト引数を取り出す。スタックにあるかもしれないので、逆順に
        revargs = [*reversed(self.args), self.reciever]
        for argobj in revargs:
            if isinstance(argobj, LeafResultRef):
                args.append(argobj.get_object(context))
            else:
                args.append(argobj)

        # 実行する
        args.reverse() # 元の順番に戻す
        self.selector.invoke(context, *args)

        # 返り値（一つだけ）
        ret = context.get_last_result()
        if ret is not None:
            rettype = context.get_type(ret.typecode)
            return Object(rettype, ret.value)

        return None

    # レシーバオブジェクトの型特性を得る
    def get_reciever_object_type(self, context=None):
        if isinstance(self.reciever, LeafResultRef):
            if context is None:
                raise ValueError("スタック上にあるレシーバの型を導出できません")
            return self.reciever.get_object(context).type
        else:
            return self.reciever.type

    #
    # デバッグ用
    #
    def sexprs(self):
        # S式風に表示：不完全なメッセージであっても表示する
        exprs = []

        def put(item):
            if isinstance(item, Object):
                exprs.append("(object {} {})".format(item.get_typename(), item.value))
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

# スタックにおかれた計算結果を取り出す
class LeafResultRef:
    def __init__(self):
        self._lastvalue = None
    
    def get_object(self, context):
        if self._lastvalue is None:
            self._lastvalue = context.top_local_object()
            context.pop_local_object()
        return self._lastvalue


# --------------------------------------------------------------------
#
# メッセージの構成要素
#
# --------------------------------------------------------------------

# オブジェクト参照
def select_object_ref(context, *, name=None, typename=None):
    if typename:
        return context.get_object_by_type(typename)
    else:
        return context.get_object(name)

# 型名
def select_type_ref(context, name):
    tt = context.get_type(name)
    if tt is None:
        return None
    return Object(context.get_type("Type"), tt)

# リテラル
def select_literal(context, string, tokentype):
    if tokentype & TOKEN_STRING:
        value = string
    else:
        try:
            value = ast.literal_eval(string)
        except Exception:
            value = string
    return Object(context.get_type(type(value)), value)

# メソッド
def select_method(name, typetraits=None, *, modbits=None):
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
    from machaon.object.importer import get_importer
    importer = get_importer(name, no_implicit=True)
    if importer:
        modfn = importer(fallback=True)
        return StaticMethodInvocation(modfn, modbits)

    # 型メソッド
    if typetraits is not None:
        meth = typetraits.get_method(name)
        if meth is not None:
            return TypeMethodInvocation(meth, modbits)
    
    # 演算子の記号を関数に
    if name in operator_selectors:
        name = operator_selectors[name]
    
    # グローバル定義の関数
    from machaon.object.generic import resolve_generic_method
    genfn = resolve_generic_method(name)
    if genfn is not None:
        return StaticMethodInvocation(genfn, modbits)
    
    # インスタンスメソッド
    return InstanceMethodInvocation(name, modbits)

#
# 演算子とセレクタの対応
#
operator_selectors = {
    # operator methods
    "==" : "equal",
    "!=" : "not-equal",
    "<=" : "less-equal",
    "<" : "less",
    ">=" : "greater-equal",
    ">" : "greater",
    "+" : "add",
    "-" : "sub",
    "neg" : "negative",
    "*" : "mul",
    "**" : "pow",
    "/" : "div",
    "//" : "floordiv",
    "%" : "mod",
    "&" : "bitand",
    "^" : "bitxor",
    "|" : "bitor",
    "~" : "bitinv",
    ">>" : "rshift",
    "<<" : "lshift",
    # generic methods
    "&&" : "and", 
    "||" : "or",  
}


# --------------------------------------------------------------------
#
# 文字列からメッセージを組み立てつつ実行する
#
# --------------------------------------------------------------------

# 式の文字列をトークンへ変換
TOKEN_TERM = 0x01
TOKEN_BLOCK_BEGIN = 0x02
TOKEN_BLOCK_END = 0x04
TOKEN_STRING = 0x10

EXPECT_NOTHING = 0
EXPECT_RECIEVER = 0x10
EXPECT_SELECTOR = 0x20
EXPECT_ARGUMENT = 0x40

TERM_NEW_BLOCK_RECIEVER = 1
TERM_NEW_BLOCK_SELECTOR = 2
TERM_LAST_BLOCK_RECIEVER = 3
TERM_LAST_BLOCK_SELECTOR = 4
TERM_LAST_BLOCK_ARG = 5
TERM_NEW_BLOCK_AS_LAST_RECIEVER = 6
TERM_NEW_BLOCK_AS_LAST_ARG = 7
TERM_EXPLICIT_BLOCK_BEGIN = 0x20
TERM_EXPLICIT_BLOCK_END = 0x40

SIGIL_OBJECT_ID = "@"
SIGILS_OBJECT_TYPENAME = "[]"

#
#
#
class MessageEngine():
    def __init__(self, expression):
        self.source = expression
        self._readings = []
        self.log = []

    # 入力文字列をトークンに
    def read_token(self) -> Generator[Tuple[str, int], None, None]:
        buffer = [""]

        def flush_buffer(back=None):
            # 空白要素を落とす
            for s in buffer[back:]:
                if s: yield s
            # バッファは初期化
            del buffer[back:]
            if not buffer:
                buffer.append("")

        def yield_token(strings, endbit):
            terms = [x for x in strings if x] 
            # トークンを排出
            if not terms: return
            for term in terms[:-1]:
                yield (term, TOKEN_TERM)
            yield (terms[-1], endbit)
        
        quotedby = None
        parens = 0
        for ch in self.source:
            if not quotedby and ch == "'" or ch == '"':
                quotedby = ch
            elif quotedby and quotedby == ch:
                quotedby = None
                yield from yield_token(flush_buffer(-1), TOKEN_TERM|TOKEN_STRING)
            elif not quotedby and ch == "(":
                yield from yield_token(flush_buffer(), TOKEN_TERM)
                yield ("", TOKEN_BLOCK_BEGIN)
                parens += 1
            elif not quotedby and ch == ")":
                yield from yield_token(flush_buffer(), TOKEN_BLOCK_END)
                parens -= 1
                if parens < 0:
                    raise SyntaxError("始め括弧が足りません")
            elif not quotedby and ch.isspace():
                buffer.append("")
            else:
                buffer[-1] += ch

        yield from yield_token(flush_buffer(), TOKEN_BLOCK_END)
        if parens > 0:
            raise SyntaxError("終わり括弧が足りません")

    # 構文を組み立てる
    def build_message(self, token: str, tokentype: int, context: Any) -> Tuple: # (int, Any...)
        reading: Optional[Message] = None
        if self._readings:
            reading = self._readings[-1]
        
        tokenbits = 0

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
            tokenbits |= TERM_EXPLICIT_BLOCK_END

        # ブロック開始指示
        if tokentype & TOKEN_BLOCK_BEGIN:
            tokenbits |= TERM_EXPLICIT_BLOCK_BEGIN

            if expect == EXPECT_SELECTOR:
                raise SyntaxError("メッセージはセレクタになりません")

            if expect == EXPECT_RECIEVER:
                return (tokenbits | TERM_NEW_BLOCK_AS_LAST_RECIEVER, reading)

            if expect == EXPECT_ARGUMENT:
                return (tokenbits | TERM_NEW_BLOCK_AS_LAST_ARG, reading)

            if expect == EXPECT_NOTHING: 
                return (tokenbits | TERM_NEW_BLOCK_RECIEVER, None)

        # オブジェクト参照
        if token.startswith(SIGIL_OBJECT_ID):
            if expect == EXPECT_SELECTOR:
                raise SyntaxError("セレクタが必要です")

            if token[1:].startswith(SIGILS_OBJECT_TYPENAME[0]) and token.endswith(SIGILS_OBJECT_TYPENAME[1]):
                obj = select_object_ref(context, typename=token[2:-1].strip())
            else:
                obj = select_object_ref(context, name=token[1:])
            
            if obj is None:
                raise SyntaxError("オブジェクト'{}'は存在しません".format(token))

            if expect == EXPECT_ARGUMENT:
                return (tokenbits | TERM_LAST_BLOCK_ARG, obj) # 前のメッセージの引数になる
            
            if expect == EXPECT_RECIEVER:
                return (tokenbits | TERM_LAST_BLOCK_RECIEVER, obj) # 新しいメッセージのレシーバになる
            
            if expect == EXPECT_NOTHING:
                return (tokenbits | TERM_NEW_BLOCK_RECIEVER, obj) # 新しいメッセージのレシーバになる

        # 型名
        tt = select_type_ref(context, token)
        if tt is not None:
            if expect == EXPECT_SELECTOR:
                raise SyntaxError("セレクタが必要です")

            if expect == EXPECT_ARGUMENT:
                raise SyntaxError("型は引数にとれません")

            if expect == EXPECT_RECIEVER:
                return (tokenbits | TERM_LAST_BLOCK_RECIEVER, tt)
            
            if expect == EXPECT_NOTHING:
                return (tokenbits | TERM_NEW_BLOCK_RECIEVER, tt) # 新しいメッセージのレシーバになる
        
        # メソッドかリテラルか、文脈で判断
        if expect == EXPECT_SELECTOR and reading:
            calling = select_method(token, reading.get_reciever_object_type(context))
            if calling is None:
                raise SyntaxError("不明なセレクタです：{}".format(token))
            return (tokenbits | TERM_LAST_BLOCK_SELECTOR, calling) # 前のメッセージのセレクタになる
        
        if expect == EXPECT_ARGUMENT:
            arg = select_literal(context, token, tokentype)
            return (tokenbits | TERM_LAST_BLOCK_ARG, arg) # 前のメッセージの引数になる

        if expect == EXPECT_RECIEVER:
            arg = select_literal(context, token, tokentype)
            return (tokenbits | TERM_LAST_BLOCK_RECIEVER, arg) 

        if expect == EXPECT_NOTHING:
            lastret = context.top_local_object()
            if lastret:
                # 先行するメッセージをレシーバとするセレクタ名か
                calling = select_method(token, lastret.type)
                if calling:
                    context.pop_local_object()
                    return (tokenbits | TERM_NEW_BLOCK_SELECTOR, lastret, calling)
            
            # 新しいブロックの開始。レシーバオブジェクトのリテラルとする
            arg = select_literal(context, token, tokentype)
            return (tokenbits | TERM_NEW_BLOCK_RECIEVER, arg) 
        
        raise SyntaxError("cannot parse")

    # 構文木を組みたてつつ、完成したところからどんどん実行
    def send_message_step(self, code, values, context):
        tokenbits = code & 0xF0
        code = code & 0x0F

        if code == TERM_NEW_BLOCK_RECIEVER:
            new_msg = Message(values[0])
            self._readings.append(new_msg)

        elif code == TERM_NEW_BLOCK_SELECTOR:
            new_msg = Message(values[0], values[1])
            self._readings.append(new_msg)
        
        elif code == TERM_LAST_BLOCK_RECIEVER:
            self._readings[-1].set_reciever(values[0])

        elif code == TERM_LAST_BLOCK_SELECTOR:
            self._readings[-1].set_selector(values[0])

        elif code == TERM_LAST_BLOCK_ARG:
            self._readings[-1].add_arg(values[0])

        elif code == TERM_NEW_BLOCK_AS_LAST_RECIEVER:
            new_msg = Message()
            values[0].set_reciever(LeafResultRef())
            self._readings.append(new_msg)
        
        elif code == TERM_NEW_BLOCK_AS_LAST_ARG:
            new_msg = Message()
            values[0].add_arg(LeafResultRef())
            self._readings.append(new_msg)
        
        # 完成したメッセージをキューから取り出す
        completes = []
        for msg in reversed(self._readings):
            if not completes and tokenbits & TERM_EXPLICIT_BLOCK_END:
                if not msg.is_specified(minarg=True):
                    raise SyntaxError("不完全なメッセージ式です：{}".format(msg.sexprs()))
                completed=True
            else:
                completed=msg.is_specified()

            if completed:
                # 実行する
                result = msg.eval(context)
                if result is None:
                    return None # エラー発生
                context.push_local_object(result) # スタックに乗せる
                completes.append(msg)
            else:
                break

        if completes:
            del self._readings[-len(completes):]
        return completes
    
    #
    def run(self, context, *, log=False):
        self.log = []
        if log:
            logger = self._logger
        else:
            def logger(state, *values):
                pass

        for i, (token, tokentype) in enumerate(self.read_token()):
            logger(0, i, token)
            
            code, *values = self.build_message(token, tokentype, context)
            logger(1, code, values)
            
            completes = self.send_message_step(code, values, context)
            if completes is None:
                logger(-1, context.get_last_exception())
                break
            else:
                logger(2, completes)

    #
    def _logger(self, state, *values):
        if state == 0:
            self.log.append([])
        elif state == 1:
            code, vals = values
            tokenbits = code & 0xF0
            code = code & 0x0F
            for k, v in globals().items():
                if k.startswith("TERM_") and v==code:
                    codename = k
                    break
            else:
                raise ValueError("")

            if tokenbits & TERM_EXPLICIT_BLOCK_END:
                codename = codename + "*"
            if tokenbits & TERM_EXPLICIT_BLOCK_BEGIN:
                codename = "*" + codename
            values = (codename, vals)
        elif state == 2:
            completes = values[0]
            values = ("".join([x.sexprs() for x in completes]),)
        elif state == -1:
            err = values[0]
            values = ("<An error occurred on evaluation: {}>".format(err),)

        self.log[-1].extend(values)

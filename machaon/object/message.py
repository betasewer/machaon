import ast
from itertools import zip_longest
from typing import Dict, Any, List, Sequence, Optional, Generator, Tuple

from machaon.object.type import TypeTraits, TypeModule
from machaon.object.object import Object

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
SIGIL_OBJECT_ID = "@"

#
#
#
class Message:
    def __init__(self, reciever=None, selector=None, args=None):
        self.reciever = reciever
        self.selector = selector
        self.args = args or []
    
    def set_reciever(self, reciever):
        self.reciever = reciever

    def set_selector(self, selector):
        self.selector = selector
    
    def add_arg(self, arg):
        self.args.append(arg)
    
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

    def get_reciever_type(self):
        pass
    
    def get_return_type(self):
        pass

    def sexprs(self):
        # S式風に表示：不完全なメッセージであっても表示する
        exprs = []

        def put(item):
            if isinstance(item, Message):
                exprs.append(item.sexprs())
            else:
                exprs.append(str(item))

        if self.reciever is not None:
            put(self.reciever)
        else:
            put("<レシーバ欠落>")

        if self.selector is not None:
            put(self.selector)

            minarg = self.selector.get_min_arity()
            for elem, _ in zip_longest(self.args, range(minarg)):
                if elem is not None:
                    put(elem)
                else:
                    put("<引数欠落>")
        else:
            put("<セレクタ欠落>")
            put("<引数欠落（個数不明）>")

        return "({})".format(" ".join(exprs))

#
# 式の文字列をトークンへ変換
#
TOKEN_TERM = 0x01
TOKEN_BLOCK_BEGIN = 0x02
TOKEN_BLOCK_END = 0x04

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

#
#
#
class MessageParser():
    def __init__(self, expression):
        self.source = expression
        self._readings = []
        self._sequence = []
        self._log = []

    # 1.0
    def read_token(self) -> Generator[Tuple[str, int], None, None]:
        buffer = [""]

        def flush_token(buf, endbit):
            # 空白要素を落としコピー
            terms = [x for x in buf if x] 
            # バッファは初期化
            buf.clear()
            buf.append("")
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
            elif not quotedby and ch == "(":
                yield from flush_token(buffer, TOKEN_TERM)
                yield ("", TOKEN_BLOCK_BEGIN)
                parens += 1
            elif not quotedby and ch == ")":
                yield from flush_token(buffer, TOKEN_BLOCK_END)
                parens -= 1
                if parens < 0:
                    raise SyntaxError("始め括弧が足りません")
            elif not quotedby and ch.isspace():
                buffer.append("")
            else:
                buffer[-1] += ch

        yield from flush_token(buffer, TOKEN_BLOCK_END)
        if parens > 0:
            raise SyntaxError("終わり括弧が足りません")

    #
    def parse_syntax(self, token: str, tokentype: int) -> Tuple: # (int, Any...)
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
        if tokentype == TOKEN_BLOCK_END:
            tokenbits |= TERM_EXPLICIT_BLOCK_END

        # ブロック開始指示
        if tokentype == TOKEN_BLOCK_BEGIN:
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

            obj = parse_object_specifier(token[1:])
            if expect == EXPECT_ARGUMENT:
                return (tokenbits | TERM_LAST_BLOCK_ARG, obj) # 前のメッセージの引数になる
            
            if expect == EXPECT_RECIEVER:
                return (tokenbits | TERM_LAST_BLOCK_RECIEVER, obj) # 新しいメッセージのレシーバになる
            
            if expect == EXPECT_NOTHING:
                return (tokenbits | TERM_NEW_BLOCK_RECIEVER, obj) # 新しいメッセージのレシーバになる

        # 型名
        tt = select_type(token)
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
            meth = select_method(token, reading.get_reciever_type())
            if meth is not None:
                return (tokenbits | TERM_LAST_BLOCK_SELECTOR, meth) # 前のメッセージのセレクタになる
            raise SyntaxError("不明なセレクタです：{}".format(token))
        
        if expect == EXPECT_ARGUMENT:
            arg = parse_arg_literal(token)
            return (tokenbits | TERM_LAST_BLOCK_ARG, arg) # 前のメッセージの引数になる

        if expect == EXPECT_RECIEVER:
            arg = parse_arg_literal(token)
            return (tokenbits | TERM_LAST_BLOCK_RECIEVER, arg) 

        if expect == EXPECT_NOTHING:
            if self._sequence:
                # セレクタになるかまず試す
                seqlast = self._sequence[-1]
                meth = select_method(token, seqlast.get_return_type())
                if meth is not None:
                    seqlast = self._sequence.pop(-1)
                    return (tokenbits | TERM_NEW_BLOCK_SELECTOR, seqlast, meth)

            # レシーバオブジェクトのリテラルとする
            arg = parse_arg_literal(token)
            return (tokenbits | TERM_NEW_BLOCK_RECIEVER, arg) 
        
        raise SyntaxError("cannot parse")

    # 3 メッセージの樹を構築する
    def build_ast_step(self, code, *values):
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
            values[0].set_reciever(new_msg)
            self._readings.append(new_msg)
        
        elif code == TERM_NEW_BLOCK_AS_LAST_ARG:
            new_msg = Message()
            values[0].add_arg(new_msg)
            self._readings.append(new_msg)
        
        # 新しく完成したメッセージをキューから取り出す
        tail = 0
        for msg in reversed(self._readings):
            if tail == 0 and tokenbits & TERM_EXPLICIT_BLOCK_END:
                if not msg.is_specified(minarg=True):
                    raise SyntaxError("不完全なメッセージ式です：{}".format(msg.sexprs()))
                complete=True
            else:
                complete=msg.is_specified()

            if complete:
                # 親子関係がある場合は親にまとめる
                if self._sequence and msg.is_child_element(self._sequence[-1]):
                    self._sequence[-1] = msg
                else:
                    self._sequence.append(msg)
                tail += 1
            else:
                break

        if tail:
            del self._readings[-tail:]

    
    #
    def get_sequence(self):
        return self._sequence
    
    def sequence_sexprs(self):
        return "".join([x.sexprs() for x in self._sequence])
    
    #
    def parse(self, log=False):
        self._log = []
        if log:
            logger = self._logger
        else:
            def logger(state, *values):
                pass

        for i, (token, tokentype) in enumerate(self.read_token()):
            logger(0, i, token)
            
            code, *values = self.parse_syntax(token, tokentype)
            logger(1, code, values)
            
            self.build_ast_step(code, *values)
            logger(2)

        return self._sequence
    
    #
    def _logger(self, state, *values):
        if state == 0:
            self._log.append([])
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
            values = (self.sequence_sexprs(),)
        self._log[-1].extend(values)

#
#
#
# 3. Pythonのリテラルとみなす
def parse_arg_literal(s):
    try:
        return ast.literal_eval(s)
    except Exception:
        pass
    return s # 文字列

    
# ---------------------------------------------------------------
# スタブ
#
#
def parse_object_specifier(s):
    return s
    
def select_type(s):
    return None

def select_method(s, type):
    if s == "stub-binary":
        return StubSelector(1,1)
    elif s == "stub-unary":
        return StubSelector(0,0)

class StubSelector:
    def __init__(self, min=1, max=1):
        self.min = min
        self.max = max

    def get_min_arity(self):
        return self.min

    def get_max_arity(self):
        return self.max
    
    def __str__(self):
        return "stub-method-{}-{}".format(self.min, self.max)
        

# ---------------------------------------------------------------

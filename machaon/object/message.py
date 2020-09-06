import ast
from itertools import zip_longest
from typing import Dict, Any, List, Sequence, Optional, Generator, Tuple, Union

from machaon.object.typename import python_builtin_typenames
from machaon.object.type import Type, TypeModule
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
# 外部オブジェクト参照
def select_object_ref(context, *, name=None, typename=None) -> Optional[Object]:
    if typename:
        return context.get_object_by_type(typename)
    else:
        return context.get_object(name)

# 型名
def select_type_ref(context, name) -> Optional[Object]:
    tt = context.get_type(name)
    if tt is None:
        return None
    return Object(context.get_type("Type"), tt)

# リテラル
def select_literal(context, string, tokentype) -> Object:
    if tokentype & TOKEN_STRING:
        value = string
    else:
        try:
            value = ast.literal_eval(string)
        except Exception:
            value = string
    
    typename = type(value).__name__
    if typename not in python_builtin_typenames:
        raise BadExpressionError("Unsupported literal type: {}".format(typename))
    return Object(context.get_type(typename), value)

# 無名関数の引数参照
def select_la_subject_value(context, key=None) -> Optional[Object]:
    if key is None:
        obj = context.get_subject_object()
        if obj is None:
            raise BadExpressionError("No object specified to lambda")
        return obj
    else:
        vs = context.get_subject_values()
        if vs is not None:
            if key not in vs:
                raise BadExpressionError("Object value '{}' does not exist".format(key))
            return vs[key]
    return None

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
    from machaon.object.importer import attribute_loader
    loader = attribute_loader(name)
    if loader:
        modfn = loader(fallback=True)
        if modfn:
            return StaticMethodInvocation(modfn, modbits)

    # 型メソッド
    if typetraits is not None:
        meth = typetraits.select_method(name)
        if meth is not None:
            return TypeMethodInvocation(meth, modbits)
    
    # グローバル定義の関数
    from machaon.object.generic import resolve_generic_method
    genfn = resolve_generic_method(name)
    if genfn is not None:
        return StaticMethodInvocation(genfn, modbits)
    
    # インスタンスメソッド
    return InstanceMethodInvocation(name, modbits)


# --------------------------------------------------------------------
#
# 文字列からメッセージを組み立てつつ実行する
#
# --------------------------------------------------------------------

# 式の文字列をトークンへ変換
TOKEN_NOTHING = 0
TOKEN_TERM = 0x01
TOKEN_BLOCK_BEGIN = 0x02
TOKEN_ENDING = 0x04
TOKEN_STRING = 0x10
TOKEN_ARGUMENT = 0x20

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
TERM_END_LAST_BLOCK = 0x10
TERM_POP_LOCAL = 0x20

SIGIL_OBJECT_ID = "$"
SIGIL_LAMBDA_SUBJECT = "@"

#
#
#
class MessageEngine():
    def __init__(self, expression):
        self.source = expression
        self._readings = []
        self._trailing_as_parameter = False
        self._codes = []
        self.log = []

    # 入力文字列をトークンに
    def read_token(self, source) -> Generator[Tuple[str, int], None, None]:
        def flush(buf, tokentype):
            string = "".join(buf)
            if string:
                # 空であれば排出しない
                yield (string, tokentype)
                buf.clear()
        
        buffer = [] # type: List[str]
        quoted_by = None
        paren_count = 0
        for ch in source:
            if self._trailing_as_parameter:
                buffer += ch
            elif not quoted_by and (ch == "'" or ch == '"'):
                quoted_by = ch
            elif quoted_by and quoted_by == ch:
                quoted_by = None
                yield from flush(buffer, TOKEN_TERM|TOKEN_STRING)
            elif quoted_by is None:
                if ch == "(":
                    yield from flush(buffer, TOKEN_TERM)
                    yield ("", TOKEN_BLOCK_BEGIN)
                    paren_count += 1
                elif ch == ")":
                    yield from flush(buffer, TOKEN_TERM|TOKEN_ENDING)
                    paren_count -= 1
                    if paren_count < 0:
                        raise SyntaxError("始め括弧が足りません")
                elif ch.isspace():
                    yield from flush(buffer, TOKEN_TERM)
                else:
                    buffer += ch
            else:
                buffer += ch

        if self._trailing_as_parameter:
            yield from flush(buffer, TOKEN_TERM|TOKEN_ENDING|TOKEN_STRING|TOKEN_ARGUMENT)
        else:
            yield from flush(buffer, TOKEN_TERM|TOKEN_ENDING)
            if paren_count > 0:
                raise SyntaxError("終わり括弧が足りません")

    # 構文を組み立てる
    def build_message(self, token: str, tokentype: int, context: Any) -> Tuple: # (int, Any...)
        reading = None # type: Optional[Message]
        if self._readings:
            reading = self._readings[-1]
        
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
        
        # 意味を無視して全体を文字列引数とみなす
        if tokentype & TOKEN_ARGUMENT:
            if expect != EXPECT_ARGUMENT:
                raise BadExpressionError("引数を受け入れるセレクタが直前にありません")
            
            arg = select_literal(context, token, tokentype)
            return (tokenbits | TERM_LAST_BLOCK_ARG, arg) # 前のメッセージの引数になる

        # ブロック終了指示
        if tokentype & TOKEN_ENDING:
            tokenbits |= TERM_END_LAST_BLOCK

        # ブロック開始指示
        if tokentype & TOKEN_BLOCK_BEGIN:
            if expect == EXPECT_SELECTOR:
                raise BadExpressionError("メッセージはセレクタになりません")

            if expect == EXPECT_RECIEVER:
                return (tokenbits | TERM_NEW_BLOCK_AS_LAST_RECIEVER, )

            if expect == EXPECT_ARGUMENT:
                return (tokenbits | TERM_NEW_BLOCK_AS_LAST_ARG, )

            if expect == EXPECT_NOTHING: 
                return (tokenbits | TERM_NEW_BLOCK_ISOLATED, )

        # オブジェクト参照
        if token.startswith(SIGIL_OBJECT_ID):
            if expect == EXPECT_SELECTOR:
                raise SyntaxError("セレクタが必要です") 

            key = token[1:]
            if key and key[0].isupper(): # 大文字なら型とみなす
                obj = select_object_ref(context, typename=key)
            else:
                obj = select_object_ref(context, name=key)
            
            if obj is None:
                raise BadExpressionError("オブジェクト'{}'は存在しません".format(token))

            if expect == EXPECT_ARGUMENT:
                return (tokenbits | TERM_LAST_BLOCK_ARG, obj) # 前のメッセージの引数になる
            
            if expect == EXPECT_RECIEVER:
                return (tokenbits | TERM_LAST_BLOCK_RECIEVER, obj) # 新しいメッセージのレシーバになる
            
            if expect == EXPECT_NOTHING:
                return (tokenbits | TERM_NEW_BLOCK_ISOLATED, obj) # 新しいメッセージのレシーバになる

        # 引数
        if token.startswith(SIGIL_LAMBDA_SUBJECT):
            key = token[1:]
            obj = None
            if len(key) == 0:
                token = "Function"
                # 型名として扱う
            else:
                valobj = select_la_subject_value(context, key)
                if valobj is not None:
                    if expect == EXPECT_ARGUMENT:
                        return (tokenbits | TERM_LAST_BLOCK_ARG, valobj) # 前のメッセージの引数になる

                    if expect == EXPECT_RECIEVER:
                        return (tokenbits | TERM_LAST_BLOCK_RECIEVER, valobj) # 前のメッセージのレシーバになる
                    
                    if expect == EXPECT_NOTHING:
                        return (tokenbits | TERM_NEW_BLOCK_ISOLATED, valobj) # 新しいメッセージのレシーバになる

                else:
                    subj = context.get_subject_object()
                    if subj is None:
                        raise BadExpressionError("無名関数の引数を参照しようとしましたが、与えられていません")

                    meth = select_method(key, subj.type)
                    
                    if expect == EXPECT_ARGUMENT:
                        return (tokenbits | TERM_NEW_BLOCK_AS_LAST_ARG, subj, meth) # 前のメッセージの引数になる

                    if expect == EXPECT_RECIEVER:
                        return (tokenbits | TERM_NEW_BLOCK_AS_LAST_RECIEVER, subj, meth) # 前のメッセージのレシーバになる
                    
                    if expect == EXPECT_NOTHING:
                        return (tokenbits | TERM_NEW_BLOCK_ISOLATED, subj, meth) # 新しいメッセージのレシーバになる

        # 型名
        tt = select_type_ref(context, token)
        if tt is not None:
            if expect == EXPECT_SELECTOR:
                raise BadExpressionError("セレクタが必要です")

            if expect == EXPECT_ARGUMENT:
                raise BadExpressionError("型は引数にとれません")

            if expect == EXPECT_RECIEVER:
                return (tokenbits | TERM_LAST_BLOCK_RECIEVER, tt)
            
            if expect == EXPECT_NOTHING:
                return (tokenbits | TERM_NEW_BLOCK_ISOLATED, tt) # 新しいメッセージのレシーバになる
        
        # メソッドかリテラルか、文脈で判断
        if expect == EXPECT_SELECTOR and reading:
            calling = select_method(token, reading.get_reciever_object_type(context))
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
                    return (tokenbits | TERM_NEW_BLOCK_ISOLATED|TERM_POP_LOCAL, lastret, calling)
            
            # 新しいブロックの開始。レシーバオブジェクトのリテラルとする
            arg = select_literal(context, token, tokentype)
            return (tokenbits | TERM_NEW_BLOCK_ISOLATED, arg) 
        
        raise BadExpressionError("Could not parse")

    # 構文木を組みたてつつ、完成したところからどんどん実行
    def send_message_step(self, code, values, context):
        code1 = code & 0x0F
        if code1 == TERM_LAST_BLOCK_RECIEVER:
            self._readings[-1].set_reciever(values[0])

        elif code1 == TERM_LAST_BLOCK_SELECTOR:
            self._readings[-1].set_selector(values[0])

        elif code1 == TERM_LAST_BLOCK_ARG:
            self._readings[-1].add_arg(values[0])

        elif code1 == TERM_NEW_BLOCK_AS_LAST_RECIEVER:
            new_msg = Message(*values)
            self._readings[-1].set_reciever(LeafResultRef())
            self._readings.append(new_msg)
        
        elif code1 == TERM_NEW_BLOCK_AS_LAST_ARG:
            new_msg = Message(*values)
            self._readings[-1].add_arg(LeafResultRef())
            self._readings.append(new_msg)
        
        elif code1 == TERM_NEW_BLOCK_ISOLATED:
            new_msg = Message(*values)
            self._readings.append(new_msg)
        
        code2 = code & 0xF0
        if code2 & TERM_END_LAST_BLOCK:
            msg = self._readings[-1]
            if not msg.is_min_arg_specified():
                raise BadExpressionError("引数が足りません：{}".format(msg.sexprs()))
            msg.end_arg()

        if code2 & TERM_POP_LOCAL:
            context.pop_local_object() # ローカルオブジェクトを一つ消費した
        
        # 以降の文字列は区切らずに一つのリテラルとみなす
        if self._readings and self._readings[-1].is_selector_parameter_consumer():
            self._trailing_as_parameter = True

        # 完成したメッセージをキューから取り出す
        completes = []
        for msg in reversed(self._readings):
            if msg.is_specified():
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
    def tokenizer(self, context, *, logger=None):
        if logger is None:
            logger = self._begin_logger(dummy=True)
        
        if not self._codes:
            # トークン文字列をコードに変換
            for token, tokentype in self.read_token(self.source):
                logger(0, token, tokentype)

                try:
                    code, *values = self.build_message(token, tokentype, context)
                    logger(1, code, values)
                    yield (code, values)
                except Exception as e:
                    logger(-1, e)
                    break
        else:
            # キャッシュを利用する
            for code, *values in self._codes:
                logger(0, "", TOKEN_NOTHING)
                logger(1, code, values)
                yield (code, values)

    #
    def run(self, context, *, log=False):
        self._trailing_as_parameter = False # リセット
        logger = self._begin_logger(dummy=not log)
        
        # コードから構文を組み立てつつ随時実行
        codes = []
        for code, values in self.tokenizer(context, logger=logger):
            try:
                completes = self.send_message_step(code, values, context)
            except Exception as e:
                logger(-1, e)
                return

            if completes is None:
                logger(-1, context.get_last_exception())
                return
            else:
                logger(2, completes)
            
            codes.append((code, *values))

        self._codes = codes

    #
    def tokenize(self, context, *, logger=None):
        self._codes = []
        self._codes.extend(self.tokenizer(context, logger=logger))
        return self._codes

    #
    def _logger(self, state, *values):
        if state == 0:
            self.log.append([])
            token, tokentype = values
            typeflags = _view_bitflag("TOKEN_", tokentype)
            values = (token, typeflags)
        elif state == 1:
            code, vals = values
            code1 = code & 0x0F
            code2 = code & 0xF0
            codename = _view_constant("TERM_", code1)
            if code2:
                codename += "+" + _view_constant("TERM_", code2)
            values = (codename, ", ".join([str(x) for x in vals]))
        elif state == 2:
            completes = values[0]
            values = ("".join([x.sexprs() for x in completes]),)
        elif state == -1:
            self.log.append([])
            err = values[0]
            values = ("!!! Error occurred on evaluation: {} {}".format(type(err).__name__, err), )

        self.log[-1].extend(values)
    
    def _begin_logger(self, *, dummy):
        self.log = []
        if dummy:
            def logger(state, *values):
                pass
        else:
            logger = self._logger
        return logger

    def pprint_log(self):
        rowtitles = ("token", "token-type", "meaning", "yielded", "done-branch")
        for i, logrow in enumerate(self.log):
            print("[{}]-----------------".format(i))
            for title, value in zip(rowtitles, logrow):
                pad = 16-len(title)
                print(" {}:{}{}".format(title, pad*" ", value))


# ログ表示用に定数名を得る
def _view_constant(prefix, code):
    for k, v in globals().items():
        if k.startswith(prefix) and v==code:
            return k
    else:
        return "<定数=0x{0X}（{}***）の名前は不明です>".format(code, prefix)

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

#
# 引数を一つとりメッセージを実行する
#
class Function():
    def __init__(self, expr: str):
        self.message = MessageEngine(expr)
    
    def get_expr(self):
        return self.message.source
    
    def compile(self, context):
        self.message.tokenize(context)

    def run(self, subject, context, log=False):
        context.set_subject(subject)
        self.message.run(context, log=True)
        returns = context.clear_local_objects()
        context.set_subject(None) # クリアする
        return tuple(returns)

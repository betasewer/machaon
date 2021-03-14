import ast
import sys
from itertools import zip_longest
from typing import Dict, Any, List, Sequence, Optional, Generator, Tuple, Union

from machaon.core.symbol import PythonBuiltinTypenames, normalize_method_name
from machaon.core.type import Type, TypeModule
from machaon.core.object import Object
from machaon.core.method import Method, MethodParameter
from machaon.core.invocation import (
    BasicInvocation,
    TypeMethodInvocation,
    InstanceMethodInvocation,
    FunctionInvocation,
    ObjectRefInvocation,
    INVOCATION_RETURN_RECIEVER,
    LOG_MESSAGE_BEGIN,
    LOG_MESSAGE_CODE,
    LOG_MESSAGE_EVAL,
    LOG_MESSAGE_EVALRET,
    LOG_MESSAGE_END,
    LOG_RUN_FUNCTION
)


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
        self._argwaiting = False
    
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
    
    def start_keyword_args(self):
        self._argwaiting = True
    
    def end_keyword_args(self):
        self._argwaiting = False
    
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
            and (self.is_max_arg_specified() if self._argwaiting else self.is_min_arg_specified())
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
            return MethodParameter("param{}".format(index), "Any", "")
    
    #
    def eval(self, context) -> Object:
        if self.reciever is None or self.selector is None:
            raise BadMessageError("レシーバとセレクタがありません")

        args = []

        # コンテキスト引数を取り出す。スタックにあるかもしれないので、逆順に
        revargs = [*reversed(self.args), self.reciever]
        for argobj in revargs:
            if isinstance(argobj, ResultStackTopRef):
                args.append(argobj.pick_object(context))
            else:
                args.append(argobj)
        args.reverse() # 元の順番に戻す

        # 実行する
        self.selector.invoke(context, *args)

        # 返り値
        if context.is_failed(): # 実行エラー発生
            return context.new_invocation_error_object() # エラーオブジェクトを返す

        # 最初の一つだけを採用
        retobj = next(context.last_result_objects(), None)
        if retobj is None:
            raise BadMessageError("返り値がありません")
    
        if retobj.value is INVOCATION_RETURN_RECIEVER:
            return self.reciever
        else:
            return retobj

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

#
def select_type(context, typeexpr) -> Type:
    if SIGIL_SCOPE_RESOLUTION in typeexpr:
        typename, _, scope = typeexpr.partition(SIGIL_SCOPE_RESOLUTION) # パッケージ名を指定する
        return context.select_type(typename, scope=scope)
    else:
        # 型名のみ
        return context.select_type(typeexpr)

# リテラル
def select_literal(context, literal) -> Object:
    try:
        value = ast.literal_eval(literal)
    except Exception:
        value = literal
    return value_to_obj(context, value)

def value_to_obj(context, value):
    typename = type(value).__name__
    if typename not in PythonBuiltinTypenames.literals:
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
    if expression and expression[0].isupper():
        tt = select_type(context, expression)
        if tt and not tt.is_any():
            return context.get_type("Type").new_object(tt)
    
    # リテラルだった
    return select_literal(context, expression)

# メソッド
def select_method(name, typetraits=None, *, reciever=None, modbits=None) -> BasicInvocation:
    # モディファイアを分離する
    if modbits is None:
        def startsmod(sigil, value, expr, bits):
            if expr.startswith(sigil):
                return (expr[len(sigil):], value|bits)
            else:
                return (expr, bits)
        
        modbits = 0
        name, modbits = startsmod("~", BasicInvocation.MOD_REVERSE_ARGS, name, modbits)
        name, modbits = startsmod("!", BasicInvocation.MOD_NEGATE_RESULT, name, modbits)

    name = normalize_method_name(name)

    # レシーバがオブジェクト集合の場合はメンバ参照に変換
    if reciever is not None and typetraits.is_object_collection():
        collection = reciever
        item = collection.get(name)
        if item is not None:
            return ObjectRefInvocation(name, item.object, modbits)
        else:
            delegate = collection.get("#delegate")
            if delegate is not None:
                # 移譲先オブジェクトからメソッドを探し直す
                delg = delegate.object
                return select_method(name, delg.type, reciever=delg.value)
            raise BadExpressionError("Member '{}' is not found in reciever (ObjectCollection)".format(name))

    # 型メソッド
    using_type_method = typetraits and not typetraits.is_any()
    if using_type_method:
        meth = typetraits.select_method(name)
        if meth is not None:
            return TypeMethodInvocation(typetraits, meth, modbits)
    
    # グローバル定義の関数
    from machaon.types.generic import resolve_generic_method_invocation
    inv = resolve_generic_method_invocation(name, modbits)
    if inv is not None:
        return inv 

    if using_type_method and not typetraits.is_using_instance_method():
        raise BadExpressionError("Method '{}' is not found in '{}' (instance method is excluded)".format(name, typetraits.typename))
    
    # インスタンスメソッド
    return InstanceMethodInvocation(name, modbits)

#
# 型で利用可能なセレクタを列挙する
#
def enum_selectable_method(typetraits) -> Generator[Method, None, None]:
    # 型メソッドの列挙
    for meth in typetraits.enum_methods():
        tinv = TypeMethodInvocation(typetraits, meth)
        yield tinv.query_method(typetraits)
    
    if not typetraits.is_using_instance_method():
        return
    
    # インスタンスメソッド
    valtype = typetraits.get_value_type()
    for name in dir(valtype):
        if name.startswith("__"):
            continue
        if typetraits.select_method(name) is not None:
            # TypeMethodと被りがある場合はスキップ
            continue
        inv = InstanceMethodInvocation(name)
        meth = inv.query_method(typetraits)
        if meth is None:
            continue
        yield meth

#
def select_constant(context, expr) -> Object:
    from machaon.core.importer import attribute_loader
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
TOKEN_IMPLICIT_SELECTOR = 0x80

EXPECT_NOTHING = 0
EXPECT_RECIEVER = 0x10
EXPECT_SELECTOR = 0x20
EXPECT_ARGUMENT = 0x40

# 組み立てられたコード
#  - 文の構造
TERM_AST_MASK = 0xFF
TERM_NOTHING = 0
TERM_LAST_BLOCK_RECIEVER = 3
TERM_LAST_BLOCK_SELECTOR = 4
TERM_LAST_BLOCK_ARG = 5
TERM_NEW_BLOCK_AS_LAST_RECIEVER = 6
TERM_NEW_BLOCK_AS_LAST_ARG = 7
TERM_NEW_BLOCK_ISOLATED = 8
TERM_NEW_BLOCK_RECIEVER = 9
TERM_NEW_BLOCK_SELECTOR = 10
#  - 生成される値の種類
TERM_OBJ_MASK = 0xFF00
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
TERM_OBJ_TYPE = 0x0B00
TERM_OBJ_SPECIFIED_TYPE = 0x0C00
TERM_OBJ_REF_ROOT_MEMBER = 0x0D00
TERM_OBJ_TUPLE = 0x0E00
#  - アクションの指示
TERM_INSTR_MASK = 0xFF0000
TERM_START_KEYWORD_ARGS = 0x010000
TERM_END_LAST_BLOCK = 0x020000
TERM_END_ALL_BLOCK = 0x040000

# メッセージで用いる記号
SIGIL_OBJECT_ID = "@"
SIGIL_OBJECT_LAMBDA_MEMBER = "/"
SIGIL_OBJECT_SPEC_NAME = "#"
SIGIL_SCOPE_RESOLUTION = "::"
SIGIL_END_OF_KEYWORDS = ";"
SIGIL_RIGHTFIRST_EVALUATION = "$"
QUOTE_ENDPARENS = {
    "[" : "]",
    "{" : "}",
    "<" : ">",
    "(" : ")",
    "（" : "）",
    "【" : "】",
    "《" : "》",
}

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
        
        if (tokentype & TOKEN_IMPLICIT_SELECTOR) > 0:
            tokentype = (tokentype & ~TOKEN_IMPLICIT_SELECTOR)
            string = "new_from_string"
        
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
class MessageEngine():
    def __init__(self, expression=""):
        self.source = expression

        self._tokens = []    # type: List[Tuple[str, int]]
        self._readings = []  # type: List[Message]
        self._codes = []     # type: List[Tuple[int, Tuple[Any,...]]]

        self._temp_result_stack = []
        
    def get_expression(self) -> str:
        """ コード文字列を返す """
        return self.source

    def read_token(self, source) -> Generator[Tuple[str, int], None, None]:
        """ 
        入力文字列をトークンへと変換する 
        Params:
            source(str): 入力文字列
        Yields:
            Tuple[str, int]: 文字列, トークンの意味を示す整数値
        """
        buffer = MessageTokenBuffer()
        user_quote_prelude = ""
        paren_count = 0
        for ch in source:
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

        # エスケープされた文字列
        isstringtoken = tokentype & TOKEN_STRING > 0

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
        if not isstringtoken and token == SIGIL_END_OF_KEYWORDS:
            if expect == EXPECT_ARGUMENT:
                return (tokenbits | TERM_OBJ_NOTHING | TERM_END_LAST_BLOCK, )

        # 評価順序変更
        if not isstringtoken and token == SIGIL_RIGHTFIRST_EVALUATION:
            if expect == EXPECT_RECIEVER:
                tokenbits |= TERM_OBJ_NOTHING
                return (tokenbits | TERM_NEW_BLOCK_AS_LAST_RECIEVER, )

            if expect == EXPECT_ARGUMENT:
                tokenbits |= TERM_OBJ_NOTHING
                return (tokenbits | TERM_NEW_BLOCK_AS_LAST_ARG, )
                
            # if expect == EXPECT_SELECTOR or expect == EXPECT_NOTHING: -> through

        # メッセージの要素ではない
        if (tokentype & TOKEN_TERM) == 0:
            return (tokenbits | TERM_OBJ_NOTHING, )

        #
        # 以下、メッセージの要素として解析
        # 

        # オブジェクト参照
        if not isstringtoken and token.startswith(SIGIL_OBJECT_ID):
            if expect == EXPECT_SELECTOR:
                raise BadExpressionError("セレクタが必要です") 

            def new_block_bits(selector_id):
                if expect == EXPECT_ARGUMENT:
                    return (tokenbits | TERM_NEW_BLOCK_AS_LAST_ARG, memberid)
                elif expect == EXPECT_RECIEVER:
                    return (tokenbits | TERM_NEW_BLOCK_AS_LAST_RECIEVER, memberid)                
                elif expect == EXPECT_NOTHING:
                    return (tokenbits | TERM_NEW_BLOCK_RECIEVER, memberid)
                else:
                    raise ValueError("")

            objid = token[1:]
            if not objid: 
                # 無名関数の引数オブジェクト
                tokenbits |= TERM_OBJ_LAMBDA_ARG
            
            elif SIGIL_OBJECT_LAMBDA_MEMBER in objid:
                # 引数オブジェクトのメンバ参照
                tokenbits |= TERM_OBJ_LAMBDA_ARG_MEMBER
                objid, _, memberid = token.partition(SIGIL_OBJECT_LAMBDA_MEMBER)
                if not memberid:
                    raise BadExpressionError("'{}'のあとにセレクタが必要です".format(SIGIL_OBJECT_LAMBDA_MEMBER))

                return new_block_bits(memberid)
                
            elif objid[0] == SIGIL_OBJECT_SPEC_NAME:
                # ルートオブジェクトのメンバ参照
                tokenbits |= TERM_OBJ_REF_ROOT_MEMBER
                memberid = token[2:]
                if not memberid:
                    raise BadExpressionError("'{}'のあとにセレクタが必要です".format(SIGIL_OBJECT_SPEC_NAME))

                return new_block_bits(memberid)
                
            elif objid[0].isupper(): 
                # 大文字なら型とみなす
                tokenbits |= TERM_OBJ_REF_TYPENAME
            
            elif objid.isdigit():
                # 数値名称のオブジェクト
                objid = str(int(objid)) # 数値表現を正規化
                tokenbits |= TERM_OBJ_REF_NAME
            
            else:
                # 通常の名称のオブジェクト
                tokenbits |= TERM_OBJ_REF_NAME

            if expect == EXPECT_ARGUMENT:
                return (tokenbits | TERM_LAST_BLOCK_ARG, objid) # 前のメッセージの引数になる
            
            if expect == EXPECT_RECIEVER:
                return (tokenbits | TERM_LAST_BLOCK_RECIEVER, objid) # 新しいメッセージのレシーバになる
            
            if expect == EXPECT_NOTHING:
                return (tokenbits | TERM_NEW_BLOCK_RECIEVER, objid) # 新しいメッセージのレシーバになる

        # 何も印のない文字列
        #  => メソッドかリテラルか、文脈で判断
        if expect == EXPECT_SELECTOR and reading:
            tokenbits |= TERM_OBJ_SELECTOR
            return (tokenbits | TERM_LAST_BLOCK_SELECTOR, token) # 前のメッセージのセレクタになる

        if expect == EXPECT_ARGUMENT:           
            # メソッドの型要求に従って解釈する 
            spec = reading.get_next_parameter_spec()
            typename = spec.typename if spec else None
            if typename == "Type":
                tokenbits |= TERM_OBJ_TYPE
            elif typename == "Tuple":
                tokenbits |= TERM_OBJ_TUPLE                
            elif spec.is_any():                
                if isstringtoken:
                    tokenbits |= TERM_OBJ_STRING
                else:
                    tokenbits |= TERM_OBJ_LITERAL
            else:
                tokenbits |= TERM_OBJ_SPECIFIED_TYPE
            return (tokenbits | TERM_LAST_BLOCK_ARG, token, spec) # 前のメッセージの引数になる

        if expect == EXPECT_RECIEVER:
            if isstringtoken:
                tokenbits |= TERM_OBJ_STRING
            else:
                tokenbits |= TERM_OBJ_RECIEVER
            return (tokenbits | TERM_LAST_BLOCK_RECIEVER, token) 

        if expect == EXPECT_NOTHING:
            if tokentype & TOKEN_FIRSTTERM:
                # メッセージの先頭のみ、レシーバオブジェクトのリテラルとする
                if isstringtoken:
                    tokenbits |= TERM_OBJ_STRING
                else:
                    tokenbits |= TERM_OBJ_RECIEVER
                return (tokenbits | TERM_NEW_BLOCK_RECIEVER, token) 
            else:
                # 先行するメッセージをレシーバとするセレクタとする
                tokenbits |= TERM_OBJ_SELECTOR
                return (tokenbits | TERM_NEW_BLOCK_SELECTOR, token)
        
        raise BadExpressionError("Could not parse")

    # 構文木を組みたてつつ、完成したところからどんどん実行
    def reduce_step(self, code, values, context) -> Generator[Message, None, None]:
        astcode = code & TERM_AST_MASK
        astinstr = code & TERM_INSTR_MASK
        objcode = code & TERM_OBJ_MASK

        # 文字列や値をオブジェクトに変換
        objs: Tuple[Any,...] = () #

        obj = None
        if objcode == TERM_OBJ_REF_NAME:
            obj = select_object(context, name=values[0])

        elif objcode == TERM_OBJ_REF_TYPENAME:
            obj = select_object(context, typename=values[0])

        elif objcode == TERM_OBJ_STRING:
            obj = context.new_object("Str", values[0])

        elif objcode == TERM_OBJ_TYPE:
            typeexpr = values[0]
            tt = select_type(context, typeexpr)
            obj = context.get_type("Type").new_object(tt)

        elif objcode == TERM_OBJ_SPECIFIED_TYPE:
            val = values[0]
            spec = values[1]
            paramtype = context.get_type(spec.get_typename())
            convval = paramtype.construct_from_value(context, val, *spec.get_typeparams())
            obj = paramtype.new_object(convval)
        
        elif objcode == TERM_OBJ_TUPLE:
            from machaon.types.tuple import ObjectTuple
            elems = values[0].split() # 文字列を空白で区切る
            tpl = ObjectTuple.conversion_construct(None, context, elems)
            obj = context.new_object("Tuple", tpl)

        elif objcode == TERM_OBJ_LITERAL:
            obj = select_literal(context, values[0])

        elif objcode == TERM_OBJ_RECIEVER:
            obj = select_reciever(context, values[0])

        elif objcode == TERM_OBJ_SELECTOR:
            selector = values[0]
            if selector.endswith(":"):
                astinstr |= TERM_START_KEYWORD_ARGS
                obj = selector[:-1]
            else:
                obj = selector

        elif objcode == TERM_OBJ_LAMBDA_ARG:
            obj = select_lambda_subject(context)

        elif objcode == TERM_OBJ_LAMBDA_ARG_MEMBER:
            reciever = select_lambda_subject(context)
            selector = select_method(values[0], reciever.type, reciever=reciever.value)
            objs = (reciever, selector)
        
        elif objcode == TERM_OBJ_REF_ROOT_MEMBER:
            rt = context.get_type("RootObject")
            reciever = rt.new_object(rt.value_type(context))
            selector = select_method(values[0], reciever.type, reciever=reciever.value)
            objs = (reciever, selector)

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
            selector = select_method(objs[0], reciever.type, reciever=reciever.value)
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
            selector = select_method(objs[0], reciever.type, reciever=reciever.value)
            new_msg = Message(reciever, selector)
            self._readings.append(new_msg)
        
        #
        if astinstr & TERM_START_KEYWORD_ARGS:            
            self._readings[-1].start_keyword_args()

        if astinstr & TERM_END_LAST_BLOCK:
            if self._readings:
                msg = self._readings[-1]
                if not msg.is_reciever_specified():
                    raise BadExpressionError("レシーバがありません：{}".format(msg.sexprs()))
                if not msg.is_selector_specified():
                    raise BadExpressionError("セレクタがありません：{}".format(msg.sexprs()))
                if not msg.is_min_arg_specified():
                    raise BadExpressionError("引数が足りません：{}".format(msg.sexprs()))
                msg.end_keyword_args()

        if astinstr & TERM_END_ALL_BLOCK:
            for msg in self._readings:
                if not msg.is_reciever_specified():
                    raise BadExpressionError("レシーバがありません：{}".format(msg.sexprs()))
                if not msg.is_selector_specified():
                    raise BadExpressionError("セレクタがありません：{}".format(msg.sexprs()))
                if not msg.is_min_arg_specified():
                    raise BadExpressionError("引数が足りません：{}".format(msg.sexprs()))
                msg.end_keyword_args()

        # 完成したメッセージをキューから取り出す
        completed = 0
        for msg in reversed(self._readings):
            if not msg.is_specified(): # 最低限のレシーバ、引数が指定されているか
                break

            # メッセージが完成した
            yield msg
            result = self._temp_result_stack.pop()
            context.push_local_object(result) # スタックに乗せる
            completed += 1

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
    def runner(self, context) -> Generator[Message, None, None]:        
        # コードから構文を組み立てつつ随時実行
        if not self._codes:
            def build_run_codes():
                for token, tokentype in self.tokenize(self.source):
                    reading = self._readings[-1] if self._readings else None
                    code, *values = self.build_message(reading, token, tokentype)
                    yield (code, values)
        else:
            # キャッシュを利用する
            def build_run_codes():
                for code, values in self._codes:
                    yield (code, values)
                    
        context.add_log(LOG_MESSAGE_BEGIN, self.source)

        coderuniter = build_run_codes()
        codes = []
        while True:
            completemsgs = []
            try:
                code, values = next(coderuniter, (None, None))
                if code is None:
                    break

                context.add_log(LOG_MESSAGE_CODE, ConstantLog(code), *values)

                for msg in self.reduce_step(code, values, context):
                    yield msg

                    context.add_log(LOG_MESSAGE_EVAL, msg)

                    result = msg.eval(context)
                    
                    context.add_log(LOG_MESSAGE_EVALRET, result)

                    if result.is_error(): # エラーオブジェクトが返った
                        context.push_local_object(result)
                        return

                    self._temp_result_stack.append(result) # reduce_stepのジェネレータへの受け渡しにのみ使用するスタック
                    completemsgs.append(msg)

            except Exception as e:
                # メッセージ実行以外の場所でエラーが起きた
                err = InternalMessageError(e,self) # コード情報を付加し、トレース情報を引き継ぐ
                context.push_local_object(context.new_invocation_error_object(err)) # スタックに乗せる
                context.push_extra_exception(err)
                return

            codes.append((code, values))

        context.add_log(LOG_MESSAGE_END)

        self._codes = codes # type: ignore
    
    def finish(self, context) -> Object:
        """ 結果を取得し、スタックをクリアする """
        returns = context.clear_local_objects() # 返り値はローカルスタックに置かれている
        if not returns:
            raise BadExpressionError("At least 1 result must be returned, but none on stack")
        ret = returns[-1]

        self._readings.clear()
        self._temp_result_stack.clear()
        return ret
    
    def run(self, context) -> Object:
        """ このコンテキストでメッセージを実行し、返り値を一つ返す """
        runner = self.runner(context)
        for _ in runner: pass

        ret = self.finish(context)
        
        context.add_log(LOG_RUN_FUNCTION, context)
        return ret # Objectを返す
    
    def run_function(self, subject, context) -> Object:
        """ 主題オブジェクトを更新した派生コンテキストでメッセージを実行 """
        subcontext = context.inherit(subject) # ここでコンテキストが入れ子になる
        return self.run(subcontext)

#
# ログ表示用に定数名を出力する
#
class ConstantLog():
    def __init__(self, code):
        self._code = code

    @property    
    def code(self):
        return self._code
    
    def as_tokentype_flags(self) -> str:
        return _view_bitflag("TOKEN_", self._code)
    
    def as_term_flags(self) -> str:
        astcode = self._code & TERM_AST_MASK
        instrcode = self._code & TERM_INSTR_MASK
        objcode = self._code & TERM_OBJ_MASK
        codename = _view_constant("TERM_", astcode)
        codename += "+" + _view_constant("TERM_", objcode)
        if instrcode:
            codename += "+" + _view_bitflag("TERM_", instrcode)
        return codename

def _view_constant(prefix, code):
    """ 定数 """
    for k, v in globals().items():
        if k.startswith(prefix) and v==code:
            return k
    else:
        return "<定数=0x{:0X}（{}***）の名前は不明です>".format(code, prefix)

def _view_bitflag(prefix, code):
    """ 重なったビットフラグ """
    c = code
    n = []
    for k, v in globals().items():
        if k.startswith(prefix) and v & c and v != TERM_INSTR_MASK:
            n.append(k)
            c = (c & ~v)
    if c!=0:
        n.append("0x{0X}".format(c))
    return "+".join(n)


#
# 主題オブジェクトのメンバ（引数0のメソッド）を取得する
# Functionの機能制限版だが、キャッシュを利用する
#
class MemberGetter():
    def __init__(self, name, method):
        self.name = name
        self.method = method
        
    def get_expression(self) -> str:
        return self.name
    
    def run_function(self, subject, context):
        """ その場でメッセージを構築し実行 """
        subcontext = context.inherit(subject)
        message = Message(subject, self.method)
        result = message.eval(subcontext)

        context.add_log(LOG_RUN_FUNCTION, subcontext)
        return result
    
def run_function(expression: str, subject, context) -> Object:
    """
    文字列をメッセージとして実行する。
    Params:
        expression(str): メッセージ
        subject(Object): *引数
        context(InvocationContext): コンテキスト
    Returns:
        Object: 実行の戻り値
    """
    f = MessageEngine(expression)
    return f.run_function(subject, context)
    


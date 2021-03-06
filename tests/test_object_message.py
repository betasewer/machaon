import pytest
import re

from machaon.core.type import Type
from machaon.core.object import ObjectValue
from machaon.core.message import MessageEngine, MessageTokenBuffer, run_function
from machaon.types.fundamental import fundamental_type
from machaon.process import TempSpirit

#-----------------------------------------------------------------------
# スタブ
#

"""
fundamental types -- 

  primitives:
Int
Float
Str
Bool
Complex
List
Dataset

  system:
Object
Window
Invocation

Window data add-column Range new 5 start: 2 step: 2
Window last-invocation what

Constants search 闇

Ygodev.Api search class Card

Ygodev.Cards search where 

Window last-invocation 

Indexer new add-pattern Indexer get-pattern 漢数字
@[Indexer] add-pattern Indexer get-pattern カタカナ
@[Indexer] add-pattern Indexer get-pattern 「」囲み
@[file] foreach -> @[Indexer] make-index @_ ラムダ式の実装；これがフィルタ・ソート関数にもなる
@[Indexer] create-report out.txt encoding: utf-8

Window data filter -> @filename == bad and @modtime between 2018/09/05 2019/04/05
Window data sortby !datetime name nani
Window data column long

"""
#-----------------------------------------------------------------------
def parse_test(parser, context, lhs, rhs):
    if lhs != rhs:
        print("Assertion Failed: '{}' => {} is not equal to {}".format(parser.source, lhs, rhs))
        print("")
        if context.is_failed():
            error = context.new_invocation_error_object()
            spi = TempSpirit()
            error.pprint(spi)
            spi.printout()
        return False
    return True

def test_context():
    from machaon.core.object import ObjectCollection
    from machaon.core.invocation import InvocationContext
    from machaon.types.fundamental import fundamental_type
    
    inputs = ObjectCollection()
    inputs.new("this-year", fundamental_type.get("Int"), 2020)    
    inputs.new("this-month", fundamental_type.get("Int"), 8) 
    inputs.new("customer-name", fundamental_type.get("Str"), "Yokomizo")
    context = InvocationContext(input_objects=inputs, type_module=fundamental_type)
    return context
                
def ptest(s, *rhs):
    context = test_context()
    parser = MessageEngine(s)
    returns = parser.run(context)
    lhs = [x.value for x in returns]
    assert parse_test(parser, context, tuple(lhs), tuple(rhs))

def run(f):
    f()

#-----------------------------------------------------------------------

def test_tokenbuffer():
    from machaon.core.message import TOKEN_TERM, TOKEN_FIRSTTERM
    buf = MessageTokenBuffer()
    buf.add("a")
    buf.add("b")
    buf.add("c")
    assert buf.flush()
    assert buf.token(TOKEN_TERM) == ("abc", TOKEN_TERM|TOKEN_FIRSTTERM)
    assert len(buf.buffer) == 0


def test_tokenize_quote():
    def push(buf, s):
        for ch in s:
            buf.add(ch)

    buf = MessageTokenBuffer()
    push(buf, "12345")
    buf.flush()
    buf.token(0)
    assert not buf.quoting()

    buf.begin_quote("[", "]")
    assert buf.quoting()
    assert not buf.check_quote_end()

    push(buf, " NUWA TSUKA MOUUUUN YAME TARA? ")
    assert not buf.check_quote_end()
    
    buf.add("]")
    assert buf.check_quote_end()

    buf.flush()
    buf.token(0) == " NUWA TSUKA MOUUUUN YAME TARA? "

#
def test_message_engine():
    from machaon.core.message import (
        TOKEN_TERM, TOKEN_FIRSTTERM, TOKEN_ALL_BLOCK_END, 
        TOKEN_BLOCK_BEGIN, TOKEN_BLOCK_END, TOKEN_STRING
    )

    engine = MessageEngine()

    def reads(s):
        v = []
        for x in engine.read_token(s):
            v.extend(x)
        return tuple(v)

    assert reads("1 add 2") == (
        "1", TOKEN_TERM|TOKEN_FIRSTTERM, 
        "add", TOKEN_TERM, 
        "2", TOKEN_TERM|TOKEN_ALL_BLOCK_END
    )

    assert reads("3 - 4") == (
        "3", TOKEN_TERM|TOKEN_FIRSTTERM, 
        "-", TOKEN_TERM, 
        "4", TOKEN_TERM|TOKEN_ALL_BLOCK_END
    )

    # かっこ
    assert reads("1 add (2 mul 3)") == (
        "1", TOKEN_TERM|TOKEN_FIRSTTERM, 
        "add", TOKEN_TERM, 
        "", TOKEN_BLOCK_BEGIN,
        "2", TOKEN_TERM,
        "mul", TOKEN_TERM, 
        "3", TOKEN_TERM|TOKEN_BLOCK_END,
        "", TOKEN_ALL_BLOCK_END
    )

    # エスケープ表現
    assert reads("'A string' endswith g") == (
        "A string", TOKEN_TERM|TOKEN_FIRSTTERM|TOKEN_STRING, 
        "endswith", TOKEN_TERM, 
        "g", TOKEN_TERM|TOKEN_ALL_BLOCK_END,
    )
    assert reads("A concat ->You got wrong book.") == (
        "A", TOKEN_TERM|TOKEN_FIRSTTERM, 
        "concat", TOKEN_TERM, 
        "You got wrong book.", TOKEN_TERM|TOKEN_ALL_BLOCK_END|TOKEN_STRING,
    )
    assert reads("he says --[ This is not joke ]") == (
        "he", TOKEN_TERM|TOKEN_FIRSTTERM, 
        "says", TOKEN_TERM, 
        " This is not joke ", TOKEN_TERM|TOKEN_STRING,
        "", TOKEN_ALL_BLOCK_END
    )

#
def test_generic_methods():
    # static method
    ptest("1 add 2", 3)
    ptest("1 add 2 add 3", 6)
    ptest("4 neg", -4)
    ptest("(5 add 6) neg", -11)
    ptest("(7 mul 8) add (9 mul 10) ", 7*8+9*10)
    ptest("(7 mul 8) add ((9 sub 10) mul 11) ", 7*8+(9-10)*11)
    ptest("7 mul 8 add $ $ 9 sub 10 mul 11 ", 7*8+(9-10)*11) # 同じ結果に
    ptest("7 mul 8 add 9 sub 10", (((7*8)+9)-10))
    ptest("'573' length", 3)
    ptest("42 in-format x", "2a")
    ptest("GODZILLA slice (9 sub 8) -1", "ODZILL")

#
def test_generic_methods_operators():
    ptest("1 + 2", 3)
    ptest("77 - 44", 33)
    ptest("3 * -4", -12)
    
def test_dynamic_methods():
    # dynamic method
    ptest("ABC startswith: A", True)
    ptest("ABC ljust: 5 '_'", "ABC__")
    ptest("ABC ljust: (2 mul 2) '_'", "ABC_")

def test_string_literals():
    # type method & string literal
    ptest("'9786' reg-match [0-9]+", True)
    ptest("'ABCD{:04}HIJK{:02}OP' format: 20 1", "ABCD0020HIJK01OP")

    # construct from string (Type.forge)
    ptest("Str parse -> 1) 'Beck' & 'Johny' Store ", " 1) 'Beck' & 'Johny' Store ")
    ptest("Int parse '0x32'", 0x32)

    # escaped literal
    ptest("--/ madman / =", " madman ")
    ptest("--^madman (28)^ startswith: mad", True)
    ptest("--| 'madman' (41) | endswith: --|) |", True)
    
    # construct from string (Str.as)
    ptest("--/0x7F/ as Int", 0x7F)
    ptest("--/3+5j/ as Complex", 3+5j)

def test_object_ref():
    # object ref
    ptest("@this-year add 1", 2021)
    ptest("@customer-name upper", "YOKOMIZO")
    ptest("'Dr. ' + (@customer-name capitalize)", "Dr. Yokomizo")
    ptest("@customer-name reg-match [a-zA-Z]+", True)

@pytest.mark.xfail
def test_double_block_is_denied():    
    # ((7 mul 8) <no-selector> <no-argument>)　と解釈しエラー
    ptest("((7 mul 8)) add ((9 mul 10)) ", 7*8+9*10)

def test_parse_function():
    def ltest(s, subject, *rhs):
        from machaon.core.object import ObjectCollection, Object
        from machaon.core.invocation import InvocationContext
        from machaon.types.fundamental import fundamental_type

        context = InvocationContext(input_objects=ObjectCollection(), type_module=fundamental_type)
        
        engine = MessageEngine(s)
        returns = engine.run(context)
        assert parse_test(engine, context, returns[0].get_typename() if returns else None, "Function")

        fundamental_type.define({
            "Typename" : "Dog",
            "name" : ("Returns: Str", lambda x: "lucky"),
            "type" : ("Returns: Str", lambda x: "Golden Retriever"),
            "sex" : ("Returns: Str", lambda x: "female"),
            "age" : ("Returns: Int", lambda x: 3),
        })

        subcontext = context.inherit()
        subj = Object(fundamental_type.get("Dog"), subject)
        fn = returns[0].value

        lhso = fn.run_function(subj, subcontext)
        lhs = lhso.value
        assert parse_test(fn, subcontext, lhs, rhs[0])
        
        # 再入
        lhso = fn.run_function(subj, subcontext)
        lhs = lhso.value
        assert parse_test(fn, subcontext, lhs, rhs[0])

    lucky = {}
    ltest("Function new: -> @ name == lucky", lucky, True)
    ltest("Function new: -> @ type startswith: Golden", lucky, True)
    ltest("Function new: -> @ age * 10", lucky, 30)
    ltest("Function new: -> (@ age * 5) == 25 || $ $ @ name == lucky", lucky, True)
    ltest("Function new: -> 32 * 45 ", lucky, 32 * 45)


#
def test_message_failure():
    # エラーが起きた時点で実行は中止される
    context = test_context()
    r = run_function("2 / 0 + 5 non-exisitent-method 0", None, context)
    assert r.is_error() # zero division error
    assert r.value.get_error_typename() == "ZeroDivisionError"

    context = test_context()
    r = run_function("2 * 3 + 5 non-exisitent-method 0", None, context)
    assert r.is_error() # bad method
    assert r.value.get_error_typename() == "BadInstanceMethodInvocation"

    # 関数の実行中のエラー
    context = test_context()
    r = run_function("2 * 3 + 5 - (--[10 / 0] eval) + 9 non-existent-method", None, context)
    assert r.is_error() # bad method
    assert r.value.get_error_typename() == "ZeroDivisionError"



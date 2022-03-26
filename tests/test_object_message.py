from machaon.core.invocation import INVOCATION_FLAG_RAISE_ERROR, InvocationContext, _new_process_error_object
import pytest
import re

from .macatester import parse_test, put_instructions

from machaon.core.message import MessageEngine, MessageExpression, MemberGetExpression, MessageTokenBuffer, SequentialMessageExpression, parse_function, parse_sequential_function, run_function, MessageEngine
from machaon.types.fundamental import fundamental_types
fundamental_type = fundamental_types()

def test_context(*, silent=False):
    from machaon.core.invocation import InvocationContext, instant_context
    
    cxt = instant_context()
    inputs = cxt.input_objects
    inputs.new("this-year", 2020, fundamental_type.get("Int"))    
    inputs.new("this-month", 8, fundamental_type.get("Int")) 
    inputs.new("customer-name", "Yokomizo", fundamental_type.get("Str"))
    if not silent:
        cxt.set_flags(INVOCATION_FLAG_RAISE_ERROR)
    return cxt

def ptest(s, rhs, *, q=None):
    context = test_context()
    parser = MessageEngine(s)
    lhso = parser.run_here(context)
    assert parse_test(parser, context, lhso.value, rhs, q)

def pinstr(s):
    context = test_context(silent=True)
    parser = MessageEngine(s)
    parser.run_here(context)
    return put_instructions(context, "; ")


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
    assert reads("he says --[ This is not a joke ]") == (
        "he", TOKEN_TERM|TOKEN_FIRSTTERM, 
        "says", TOKEN_TERM, 
        " This is not a joke ", TOKEN_TERM|TOKEN_STRING,
        "", TOKEN_ALL_BLOCK_END
    )

    # 丸括弧の区別
    """
    assert reads("this a sacrifi(1991,Mito)es what he called (his soul)") == (
        "this", TOKEN_TERM|TOKEN_FIRSTTERM, 
        "sacrifi(1991,Mito)es", TOKEN_TERM, 
        "what", TOKEN_TERM,
        "he", TOKEN_TERM,
        "called", TOKEN_TERM,
        "", TOKEN_BLOCK_BEGIN,
        "his", TOKEN_TERM,
        "soul", TOKEN_TERM|TOKEN_BLOCK_END,
        "", TOKEN_ALL_BLOCK_END
    )
    """

#
def test_minimum():
    p = pinstr("11 add 22")
    ptest("11 add 22", 33)

#
def test_generic_methods():
    # static method
    ptest("1 add 2", 3)
    ptest("1 add 2 add 3", 6)
    ptest("4 negative", -4)
    ptest("(5 add 6) negative", -11)
    ptest("(7 mul 8) add (9 mul 10) ", 7*8+9*10)
    ptest("(7 mul 8) add ((9 sub 10) mul 11) ", 7*8+(9-10)*11)
    ptest("7 mul 8 add 9 sub 10", (((7*8)+9)-10))
    ptest("'573' length", 3)
    ptest("GODZILLA slice: (9 sub 8) -1", "ODZILL")

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

    # escaped literal
    ptest("--/ madman / =", " madman ")
    ptest("--^madman (28)^ startswith: mad", True)
    ptest("--| 'madman' (41) | endswith: --|) |", True)
    
    # construct from string (Str.as)
    ptest("--/ 1) 'Beck' & 'Johny' Store/ as Str", " 1) 'Beck' & 'Johny' Store")
    ptest("--/0x32/ as Int", 0x32)
    ptest("--/0x7F/ as Int", 0x7F)
    ptest("--/3+5j/ as Complex", 3+5j)

def test_constructor():
    ptest("1 Int", 1)
    ptest("1 Int + (2 Int)", 3)
    ptest("10 Int + ((20 Int) Float)", 30.0)

def test_object_ref():
    # object ref
    ptest("@this-year add 1", 2021)
    ptest("@customer-name upper", "YOKOMIZO")
    ptest("'Dr. ' + (@customer-name capitalize)", "Dr. Yokomizo")
    ptest("@customer-name reg-match [a-zA-Z]+", True)

def test_unfinished_block_is_ok():    
    ptest("1", 1) # identity メッセージをおぎなう
    ptest("((7 mul 8)) add ((9 mul 10)) ", 7*8+9*10) # 二重括弧は不完全なメッセージ式として補完される

#
def test_paren_block():
    ptest("1 + (2 * 3)", 1+(2*3))
    ptest("1 + (2 * (3 - 4))", 1+(2*(3-4)))

#
def test_root_message():
    def type_equals(l, r):
        return type(l) is r
    from machaon.types.app import RootObject
    ptest("@@ =", RootObject, q=type_equals)
    ptest("@@context", InvocationContext, q=type_equals)   


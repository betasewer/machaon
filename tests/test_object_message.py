from machaon.core.invocation import _new_process_error_object
import pytest
import re

from machaon.core.type import Type
from machaon.core.object import Object
from machaon.core.message import MessageEngine, MessageTokenBuffer, run_function, MessageEngine
from machaon.types.fundamental import fundamental_type
from machaon.process import TempSpirit

#-----------------------------------------------------------------------
# スタブ
#-----------------------------------------------------------------------
def parse_test(parser, context, lhs, rhs):
    if isinstance(lhs, Object):
        if lhs.is_error():
            print("Error occurred on the left side:")
            print("")
            spi = TempSpirit()
            lhs.pprint(spi)
            spi.printout()
            return False
        lhs = lhs.value

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
                
def ptest(s, rhs):
    context = test_context()
    parser = MessageEngine(s)
    lhso = parser.run(context)
    assert parse_test(parser, context, lhso.value, rhs)

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
    assert reads("he says --[ This is not a joke ]") == (
        "he", TOKEN_TERM|TOKEN_FIRSTTERM, 
        "says", TOKEN_TERM, 
        " This is not a joke ", TOKEN_TERM|TOKEN_STRING,
        "", TOKEN_ALL_BLOCK_END
    )

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

    # escaped literal
    ptest("--/ madman / =", " madman ")
    ptest("--^madman (28)^ startswith: mad", True)
    ptest("--| 'madman' (41) | endswith: --|) |", True)
    
    # construct from string (Str.as)
    ptest("--/ 1) 'Beck' & 'Johny' Store/ as Str", " 1) 'Beck' & 'Johny' Store")
    ptest("--/0x32/ as Int", 0x32)
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

#
def test_paren_block():
    ptest("1 + (2 * 3)", 1+(2*3))
    ptest("1 + (2 * (3 - 4))", 1+(2*(3-4)))

def test_parse_function():
    def ltest(s, subject, *rhs):
        from machaon.core.object import ObjectCollection, Object
        from machaon.core.invocation import InvocationContext
        from machaon.types.fundamental import fundamental_type

        context = InvocationContext(input_objects=ObjectCollection(), type_module=fundamental_type)
        
        engine = MessageEngine(s)
        returned = engine.run(context)
        if returned.is_error():
            spi = TempSpirit()
            returned.pprint(spi)
            spi.printout()
        assert parse_test(engine, context, returned.get_typename(), "Function")

        fundamental_type.define({
            "Typename" : "Dog",
            "name" : ("Returns: Str", lambda x: "lucky"),
            "type" : ("Returns: Str", lambda x: "Golden Retriever"),
            "sex" : ("Returns: Str", lambda x: "female"),
            "age" : ("Returns: Int", lambda x: 3),
        })

        subcontext = context.inherit()
        subj = Object(fundamental_type.get("Dog"), subject)
        fn = returned.value

        lhso = fn.run_function(subj, subcontext)
        assert parse_test(fn, subcontext, lhso, rhs[0])
        
        # 再入
        lhso = fn.run_function(subj, subcontext)
        assert parse_test(fn, subcontext, lhso, rhs[0])

    lucky = {}
    ltest("Function ctor -> @ name == lucky", lucky, True)
    ltest("Function ctor -> @ type startswith: Golden", lucky, True)
    ltest("Function ctor -> @ age * 10", lucky, 30)
    ltest("Function ctor -> (@ age * 5 == 25) || (@ name == lucky)", lucky, True)
    ltest("Function ctor -> 32 * 45 ", lucky, 32 * 45)


#
def test_message_failure():
    # エラーが起きた時点で実行は中止され、エラーオブジェクトが返される
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
    r = run_function("--[10 / 0] eval non-existent-method", None, context)
    assert r.is_error() # bad method
    assert r.value.get_error_typename() == "BadExpressionError" # 中断されない
    
    context = test_context()
    r = run_function("--[10 / 0] do non-existent-method", None, context)
    assert r.is_error() # bad method
    assert r.value.get_error_typename() == "ZeroDivisionError" # 中断される

#
def test_message_reenter():
    context = test_context()
    func = MessageEngine("210 / @")

    # 1.
    r = func.run_function(context.new_object(7), context)
    assert r.value == 30
    # 2.
    r = func.run_function(context.new_object(5), context)
    assert r.value == 42
    # 3. (error)
    r = func.run_function(context.new_object(0), context)
    assert r.is_error()
    # 4. 
    r = func.run_function(context.new_object(2), context)
    assert r.value == 105


#
def test_message_block():
    context = test_context()

    # 二つ以上のメッセージを含むブロック
    r = run_function("10 * (1 + 2 + 3)", None, context)
    assert r.value == 10 * 6

    r = run_function("'1-2-3' startswith: (1 Str + '-')", None, context)
    assert r.value is True
    
    r = run_function("('1 2 3' + ' ' + '4 5') split as Int reduce '@.0 + @.1'", None, context)
    assert r.value == (1 + 2 + 3 + 4 + 5)

    # ネスト
    r = run_function("100 / ((1 + 2 + 3) * (4 + 5 + 6))", None, context)
    assert r.value == 100 / ((1 + 2 + 3) * (4 + 5 + 6))

#
def test_message_discard():
    context = test_context()

    r = run_function("10 + 20 . 2 * 4", None, context)
    assert r.value == 2 * 4

    r = run_function(". 10 + 20 . 3 * 5 .", None, context)
    assert r.value == 3 * 5

    r = run_function("100 * (1 + 2 + 3 . 8 =)", None, context)
    assert r.value == 100 * 8



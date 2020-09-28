import pytest
import re

from machaon.object.type import Type
from machaon.object.object import ObjectValue
from machaon.object.message import MessageEngine, MessageTokenBuffer
from machaon.object.fundamental import fundamental_type

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
def parse_test(parser, lhs, rhs):
    if lhs != rhs:
        print("Assertion Failed: '{}' => {} is not equal to {}".format(parser.source, lhs, rhs))
        print("")
        print("Parser log: ")
        parser.pprint_log()
        return False
    return True
                
def ptest(s, *rhs):
    from machaon.object.object import ObjectCollection
    from machaon.object.invocation import InvocationContext
    from machaon.object.fundamental import fundamental_type
    
    inputs = ObjectCollection()
    inputs.new("this-year", fundamental_type.Int, 2020)    
    inputs.new("this-month", fundamental_type.Int, 8) 
    inputs.new("customer-name", fundamental_type.Str, "Yokomizo")
    context = InvocationContext(input_objects=inputs, type_module=fundamental_type)
    
    parser = MessageEngine(s)
    returns = parser.run(context, log=True)
    lhs = [x.value for x in returns]
    assert parse_test(parser, tuple(lhs), tuple(rhs))

def run(f):
    f()

def test_tokenize_quote():
    # -->
    buf = MessageTokenBuffer()
    [buf.add(x) for x in "-->"]
    buf.flush() and buf.token(0)
    assert buf.quote_beg == "-->"
    assert buf.quote_end is None
    [buf.add(x) for x in " NUWA TSUKA MOUUUUN"]
    assert buf.quoting()
    [buf.add(x) for x in " YAME TARA? "]
    buf.flush()
    assert buf.token(0)[0] == " NUWA TSUKA MOUUUUN YAME TARA? "

    # ->
    buf = MessageTokenBuffer()
    [buf.add(x) for x in "->"]
    buf.flush() and buf.token(0)
    assert buf.quote_beg == "->"
    assert buf.quote_end is None
    assert buf.quote_char_waiting
    buf.wait_quote_begin_char(" ")
    buf.wait_quote_begin_char("/")
    assert buf.quote_beg == "/"
    assert buf.quote_end == "/"
    assert not buf.quote_char_waiting
    [buf.add(x) for x in " ----- ===== <---->"]
    assert buf.quoting()
    [buf.add(x) for x in " xxxx 'Hey, your name is nana too, right?' (sinister smile) "]
    assert buf.quoting()
    assert buf.wait_quote_end("/")
    assert not buf.quoting()

#
@run
def test_parse_literals():
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
    
    # dynamic method
    ptest("ABC startswith A", True)
    ptest("ABC ljust 5 _", "ABC__")
    ptest("ABC ljust (2 mul 2) _", "ABC_")

    # type method & string literal
    ptest("'9786' regmatch [0-9]+", True)
    ptest("'ABCD{:04}HIJK{:02}OP' format 20 1", "ABCD0020HIJK01OP")

    # object ref
    ptest("$this-year add 1", 2021)
    ptest("$customer-name upper", "YOKOMIZO")
    ptest("'Dr. ' + ($customer-name capitalize)", "Dr. Yokomizo")
    ptest("$customer-name regmatch [a-zA-Z]+", True)

    # constructor
    ptest("Str --> 1) 'Beck' & 'Johny' Store ", "1) 'Beck' & 'Johny' Store ")
    ptest("Int --> 0x98", 0x98)

    ptest("Str -> / madman /", " madman ")
    ptest("Str -> ^madman (28)^ startswith mad", True)
    ptest("Str -> ^ 'madman' (41) ^ endswith $ Str --> ) ", True)

@pytest.mark.xfail
def test_double_block_is_denied():    
    # ((7 mul 8) <no-selector> <no-argument>)　と解釈しエラー
    ptest("((7 mul 8)) add ((9 mul 10)) ", 7*8+9*10)

def test_parse_function():
    def ltest(s, subject, *rhs):
        from machaon.object.object import ObjectCollection, Object
        from machaon.object.invocation import InvocationContext
        from machaon.object.fundamental import fundamental_type

        context = InvocationContext(input_objects=ObjectCollection(), type_module=fundamental_type)
        
        engine = MessageEngine(s)
        returns = engine.run(context, log=True)
        assert parse_test(engine, returns[0].get_typename() if returns else None, "Function")

        fundamental_type.define(memberdefs={
            "name" : "Str",
            "type" : "Str",
            "sex" : "Str",
            "age" : "Int",
        }, typename="Dog")

        subcontext = context.inherit()
        subj = Object(fundamental_type.Dog, subject)
        fn = returns[0].value

        lhs = fn.run(subj, subcontext, log=True)
        assert parse_test(fn.message, tuple(x.value for x in lhs), rhs)
        
        # 再入
        lhs = fn.run(subj, subcontext, log=True)
        assert parse_test(fn.message, tuple(x.value for x in lhs), rhs)


    lucky = {
        "name" : "lucky",
        "type" : "Golden retriever",
        "sex" : "female",
        "age" : 3,
    }
    ltest("Function --> @name == lucky", lucky, True)
    ltest("Function --> @type startswith Golden", lucky, True)
    ltest("Function --> @age * 10", lucky, 30)
    ltest("Function --> (@age * 5) == 25 || @name == lucky", lucky, True)
    ltest("Function --> 32 * 45 ", lucky, 32 * 45)

    # $Sheet filter -> @name startswith -> Qliphort Genius [->] 直前のセレクタの要求する型を暗黙のレシーバとし、newを実行する




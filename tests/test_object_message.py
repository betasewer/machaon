import re

from machaon.object.type import TypeTraits
from machaon.object.object import ObjectValue
from machaon.object.message import MessageEngine

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
    parser.run(context, log=True)

    assert [x.value for x in context.get_local_objects()] == list(rhs)

def run(f):
    f()

#
@run
def test_parse_literals():
    # static method
    ptest("1 add 2", 3)
    ptest("1 add 2 add 3", 6)
    ptest("4 neg", -4)
    ptest("(5 add 6) neg", -11)
    ptest("(7 mul 8) add (9 mul 10) ", 7*8+9*10)
    ptest("(7 mul 8) add ((9 add (10 neg)) mul 11) ", 7*8+(9-10)*11)
    ptest("42 format x", "2a")
    
    # dynamic method
    ptest("ABC startswith A", True)
    ptest("ABC ljust 5 _", "ABC__")
    ptest("ABC ljust (2 mul 2) _", "ABC_")
    ptest("'ABCD{:04}HIJK{:02}OP' format 20 1", "ABCD0020HIJK01OP")

    # type method & string literal
    ptest("'9786' regmatch [0-9]+", True)
    ptest("'9786' length", 4)

    # object explicit ref
    ptest("@this-year add 1", 2021)
    ptest("@customer-name upper", "YOKOMIZO")
    ptest("'Dr. ' + (@customer-name capitalize)", "Dr. Yokomizo")

    # object implicit ref


    """
    assert p("0 add 2") == "(0 add 2)"
    assert p("0 minus") == "(0 minus)"
    assert p("0 add 1 minus") == "((0 add 1) minus)"
    assert p("0 add 1 add 2 add 3") == "(((0 add 1) add 2) add 3)"
    assert p("(0 add 1) add (2 add 3)") == "((0 add 1) add (2 add 3))"
    assert p("((0 add 1) minus) add (2 add 3)") == "(((0 add 1) minus) add (2 add 3))"
    #
    assert p("0 add '1)skip'") == "(0 add 1)skip)"
    assert p('''0 add "1) 'Beck' & 'Johny' Store "''') == '''(0 add 1) 'Beck' & 'Johny' Store )'''
    """
    






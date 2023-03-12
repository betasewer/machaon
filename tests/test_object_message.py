from machaon.core.context import (
    INVOCATION_FLAG_RAISE_ERROR, InvocationContext, instant_context
)
import pytest
import re
from machaon.core.type.decl import TypeProxy

from machaon.macatest import parse_test, put_instructions, run, parse_instr

from machaon.core.message import (
    MessageCharBuffer, MessageEngine, MessageTokenizer
)
from machaon.types.fundamental import fundamental_types

fundamental_type = fundamental_types()

def test_context(*, silent=False):    
    cxt = instant_context()
    inputs = cxt.input_objects
    inputs.new("this-year", 2020, fundamental_type.get("Int"))    
    inputs.new("this-month", 8, fundamental_type.get("Int")) 
    inputs.new("customer-name", "Yokomizo", fundamental_type.get("Str"))
    if not silent:
        cxt.set_flags(INVOCATION_FLAG_RAISE_ERROR)
    return cxt

def ptest(s, rhs, *, q=None):
    context = test_context(silent=False)
    return parse_test(context, s, rhs, q=q)

def pinstr(s):
    context = test_context(silent=True)
    return parse_instr(context, s)


#-----------------------------------------------------------------------

def test_charbuffer():
    from machaon.core.message import CHAR_SPACE, CHAR_BEGIN_BLOCK, CHAR_END_BLOCK

    buf = MessageCharBuffer()
    buf.add("a")
    buf.add("b")
    buf.add("c")
    assert buf.flush()
    assert buf.last() == "abc"

    def chars(s):
        tks = MessageCharBuffer()
        return list(tks.read_char(s))
    assert chars("abc") == ["a","b","c"]
    assert chars("012 == 345") == ["0", "1", "2", CHAR_SPACE, "=", "=", CHAR_SPACE, "3", "4", "5"]

    assert chars("( a )") == [
        CHAR_BEGIN_BLOCK, CHAR_SPACE, "a", CHAR_SPACE, CHAR_END_BLOCK
    ]
    assert chars("(( b ))") == [
        CHAR_BEGIN_BLOCK, CHAR_BEGIN_BLOCK, CHAR_SPACE, "b", CHAR_SPACE, CHAR_END_BLOCK, CHAR_END_BLOCK
    ]

    #assert tokens("str") == ("a, b, c, #10, =, =, #10, d, e, f")
    #assert tokens("(32 ('Int' sub Hex): 8) help)") == (
    #    "#3, 3, 2, #10, #3, #1, I, n, t, #2, #10, s, u, b, #10, H, e, x, #5, #10, 8, #4, #10, h, e, l, p, #4"
    #)

#@run
def test_tokenize():
    from machaon.core.message import (
        TOKEN_TERM, TOKEN_FIRSTTERM, 
        TOKEN_ALL_BLOCK_END, TOKEN_BLOCK_BEGIN, TOKEN_BLOCK_END,
        TOKEN_STRING, TOKEN_BLOCK_SELECTOR_MOD
    )
    def tokens(s):
        tks = MessageTokenizer()
        itr = tks.read_token(s)
        li = []
        while True:
            try:
                li.append(next(itr))
            except StopIteration:
                break
            except Exception as e:
                li.append(str(e))
        return li

    tks = MessageTokenizer()
    assert tks.new_token("abc") == ("abc", TOKEN_TERM|TOKEN_FIRSTTERM)
    
    #
    #　基本構文
    #
    assert tokens("abc") == [
        ("abc", TOKEN_TERM|TOKEN_FIRSTTERM|TOKEN_ALL_BLOCK_END),
    ]
    assert tokens("abc == def") == [
        ("abc", TOKEN_TERM|TOKEN_FIRSTTERM),
        ("==", TOKEN_TERM),
        ("def", TOKEN_TERM|TOKEN_ALL_BLOCK_END)
    ]

    #
    # かっこ
    #
    assert tokens("(32 + 50)") == [
        ("", TOKEN_BLOCK_BEGIN|TOKEN_FIRSTTERM),
        ("32", TOKEN_TERM|TOKEN_FIRSTTERM),
        ("+", TOKEN_TERM),
        ("50", TOKEN_TERM|TOKEN_BLOCK_END),
        ("", TOKEN_ALL_BLOCK_END)
    ]
    assert tokens("1 add (2 mul 3)") == [
        ("1", TOKEN_TERM|TOKEN_FIRSTTERM), 
        ("add", TOKEN_TERM), 
        ("", TOKEN_BLOCK_BEGIN),
        ("2", TOKEN_TERM),
        ("mul", TOKEN_TERM), 
        ("3", TOKEN_TERM|TOKEN_BLOCK_END),
        ("", TOKEN_ALL_BLOCK_END)
    ]
    assert tokens("(1 sub 2) mul 3") == [
        ("", TOKEN_BLOCK_BEGIN|TOKEN_FIRSTTERM),
        ("1", TOKEN_TERM|TOKEN_FIRSTTERM), 
        ("sub", TOKEN_TERM), 
        ("2", TOKEN_TERM|TOKEN_BLOCK_END),
        ("mul", TOKEN_TERM), 
        ("3", TOKEN_TERM|TOKEN_ALL_BLOCK_END),
    ]
    # ネスト・2連続の括弧
    assert tokens("((32 ('Int' sub Hex) 8) help)") == [
        ("", TOKEN_BLOCK_BEGIN|TOKEN_FIRSTTERM),
        ("", TOKEN_BLOCK_BEGIN|TOKEN_FIRSTTERM),
        ("32", TOKEN_TERM|TOKEN_FIRSTTERM),
        ("", TOKEN_BLOCK_BEGIN),
        ("Int", TOKEN_TERM|TOKEN_STRING), 
        ("sub", TOKEN_TERM),
        ("Hex", TOKEN_TERM|TOKEN_BLOCK_END),
        ("8", TOKEN_TERM|TOKEN_BLOCK_END),
        ("help", TOKEN_TERM|TOKEN_BLOCK_END),
        ("", TOKEN_ALL_BLOCK_END)
    ]
    # モディファイア付き
    assert tokens("7FFF (Int sub Hex): 8 Int") == [
        ("7FFF", TOKEN_TERM|TOKEN_FIRSTTERM),
        ("", TOKEN_BLOCK_BEGIN),
        ("Int", TOKEN_TERM),
        ("sub", TOKEN_TERM),
        (":", TOKEN_BLOCK_SELECTOR_MOD),
        ("Hex", TOKEN_TERM|TOKEN_BLOCK_END),
        ("8", TOKEN_TERM),
        ("Int", TOKEN_TERM|TOKEN_ALL_BLOCK_END),
    ]
    assert tokens("7FFF !(= add =) 9FFF") == [
        ("7FFF", TOKEN_TERM|TOKEN_FIRSTTERM),
        ("", TOKEN_BLOCK_BEGIN),
        ("!", TOKEN_BLOCK_SELECTOR_MOD),
        ("=", TOKEN_TERM),
        ("add", TOKEN_TERM),
        ("=", TOKEN_TERM|TOKEN_BLOCK_END),
        ("9FFF", TOKEN_TERM|TOKEN_ALL_BLOCK_END),
    ]

    #
    # 文字リテラル
    #
    assert tokens("'A string' endswith g") == [
        ("A string", TOKEN_TERM|TOKEN_FIRSTTERM|TOKEN_STRING), 
        ("endswith", TOKEN_TERM), 
        ("g", TOKEN_TERM|TOKEN_ALL_BLOCK_END),
    ]
    # 一行
    assert tokens("and concat ->    You got wrong book.") == [
        ("and", TOKEN_TERM|TOKEN_FIRSTTERM), 
        ("concat", TOKEN_TERM), 
        ("    You got wrong book.", TOKEN_TERM|TOKEN_ALL_BLOCK_END|TOKEN_STRING),
    ]
    # ユーザー定義文字で
    assert tokens("he says --/ What are you doing? /") == [
        ("he", TOKEN_TERM|TOKEN_FIRSTTERM), 
        ("says", TOKEN_TERM), 
        (" What are you doing? ", TOKEN_TERM|TOKEN_STRING),
        ("", TOKEN_ALL_BLOCK_END)
    ]
    assert tokens("he says --[ This is not a joke. ]") == [
        ("he", TOKEN_TERM|TOKEN_FIRSTTERM), 
        ("says", TOKEN_TERM), 
        (" This is not a joke. ", TOKEN_TERM|TOKEN_STRING),
        ("", TOKEN_ALL_BLOCK_END)
    ]

    
    #
    # 丸括弧の区別
    #
    assert tokens("this is the research(1991,Honda), he needs to read") == [
        ("this", TOKEN_TERM|TOKEN_FIRSTTERM), 
        ("is", TOKEN_TERM), 
        ("the", TOKEN_TERM), 
        ("research(1991,Honda),", TOKEN_TERM), 
        ("he", TOKEN_TERM), 
        ("needs", TOKEN_TERM), 
        ("to", TOKEN_TERM), 
        ("read", TOKEN_TERM|TOKEN_ALL_BLOCK_END)
    ]
    # 片側に終わり括弧のあるリテラル
    assert tokens("abc Str:Enclosed(【,】) reverse") == [
        ("abc", TOKEN_TERM|TOKEN_FIRSTTERM), 
        ("Str:Enclosed(【,】)", TOKEN_TERM), 
        ("reverse", TOKEN_TERM|TOKEN_ALL_BLOCK_END),
    ]
    # 片側に始まり括弧のあるリテラルには対応できない


def test_tokenize_quote():
    def push(buf, s):
        for ch in s:
            if buf.check_quote_end(ch):
                pass
            else:
                buf.add(ch)

    buf = MessageCharBuffer()
    push(buf, "12345")
    buf.flush()
    assert not buf.quoting()

    buf.begin_quote("[", "]")
    assert buf.quoting()

    push(buf, " NUWA TSUKA MOUUUUN YAME TARA? ")
    assert buf.quoting()
    
    push(buf, "]")
    assert not buf.quoting()

    buf.flush()
    buf.last() == " NUWA TSUKA MOUUUUN YAME TARA? "


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
    
    # construct from string
    ptest("--/ 1) 'Beck' & 'Johny' Store/ Str", " 1) 'Beck' & 'Johny' Store")
    ptest("--/0x32/ Int", 0x32)
    ptest("--/0x7F/ Int", 0x7F)
    ptest("--/3+5j/ Complex", 3+5j)

def test_parameter_list_end():
    ptest("--|{}/{}/{}| format: 1999 7 31 :. slice: 0 5", "1999/")
    ptest("--|{}/{}/{}| format: 1999 7 31 :. . 1 + 1", 2)


#@run
def test_constructor():
    ptest("1 Int", 1)
    ptest("1 Int + (2 Int)", 3)
    ptest("10 Int + ((20 Int) Float)", 30.0)

    # 引数あり
    def deep_equals(l, r):
        if len(l) != len(r):
            return False
        for ll, rr in zip(l, r):
           if ll != rr:
               return False
        return True

    ptest("1 /+ 2 /+ 3 Sheet: Int positive negative :. row_values 1", [2,-2], q=deep_equals)

    # ブロック型
    def type_equals(l, r):
        if not isinstance(l,TypeProxy):
            return False
        return l.get_conversion() == r

    ptest("Sheet: Int positive negative", "Sheet: Int positive negative", q=type_equals)


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

#
def test_message_as_selector():
    # 1引数のセレクタ
    ptest("4 (sq + rt)", 2)
    ptest("abc (1 + 1)", "c")
    ptest("1234 ('Str' Type)", "1234")

    # セレクタが続く
    l = ptest("'450' ('Int' Type) * 2", 900)

    # 2引数のセレクタ：引数が続く
    l = ptest("4 (mu + l) 5", 20)

def test_message_as_selector_multi_blocks():
    # ブロックが2つ続く
    l = ptest("(2 (mu + l) 5) ('Str' Type)", "10")
    l = ptest("(2 (mu + l) 5) ('Str' Type) * 3", "101010")

    # ブロックが3つ以上続く
    l = ptest("(10 (ad + d) 2) ('Str' Type) (mu + l) (10 / 5 floor)", "1212")


def test_python_fn_selector():
    import sys
    # モジュールから関数・定数をインポートする
    ptest("9 (math.sqrt py)", 3)
    ptest("_ (sys.version py)", sys.version)
    ptest("_ (sys.version py): 1 2 3", sys.version) # 定数の場合、余計な引数は無視される

    # 引数無しの関数を呼び出す
    import datetime
    ptest("__ignored_param__ (datetime pymod #> datetime #> today void)", None, q=lambda l,r:isinstance(l, datetime.datetime))
    import platform
    ptest("__ignored_param__ (platform pymod #> python-version void)", platform.python_version())

    # クラスを直接生成する
    ptest("2000 (datetime.datetime py): 8 31", datetime.datetime(2000, 8, 31)) # Invocationに包む
    ptest("2000 (datetime pymod #> datetime): 8 31", datetime.datetime(2000, 8, 31)) # クラスオブジェクトがセレクタ
    import argparse
    ptest("_ (argparse pymod #> ArgumentParser void)", None, q=lambda l,r:isinstance(l,argparse.ArgumentParser)) # クラスオブジェクトがセレクタ
    

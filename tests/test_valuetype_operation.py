import pytest

from machaon.valuetype.operation import (
    tokenize, TOKEN_BLOCK_BEGIN, TOKEN_BLOCK_END,
    parse_expression, expression,
    parse_literal
)


#
#========================================================
# テスト
#========================================================
#
def test_tokenize():
    assert list(
        tokenize("modtime within 2010/06/05 2012/08/07")
    ) == [
        TOKEN_BLOCK_BEGIN, "modtime within 2010/06/05 2012/08/07", TOKEN_BLOCK_END
    ]

    assert list(
        tokenize("(name == kenzo) && (age == 20)")
    ) == [
        TOKEN_BLOCK_BEGIN, 
            TOKEN_BLOCK_BEGIN, "name == kenzo", TOKEN_BLOCK_END, 
        " && ",  # 空白には手を加えない
            TOKEN_BLOCK_BEGIN, "age == 20", TOKEN_BLOCK_END,
        TOKEN_BLOCK_END
    ]

    assert list(
        tokenize("(age+20)isodd ")
    ) == [
        TOKEN_BLOCK_BEGIN, 
            TOKEN_BLOCK_BEGIN, "age+20", TOKEN_BLOCK_END, 
        "isodd ", 
        TOKEN_BLOCK_END
    ]

    assert list(
        tokenize("isalive and (age < 30)")
    ) == [
        TOKEN_BLOCK_BEGIN, 
        "isalive and ",
            TOKEN_BLOCK_BEGIN, "age < 30", TOKEN_BLOCK_END, 
        TOKEN_BLOCK_END
    ]

#
def test_parseexpression():
    expr = parse_expression("price * 0.7")
    assert expr.S() == "(* 'price' 0.7)"

    expr = parse_expression(expr, "* 1.1")
    assert expr.S() == "(* (* 'price' 0.7) 1.1)"
    
    expr = parse_expression(parse_expression("A && B"), "||", parse_expression("C && D"))
    assert expr.S() == "(|| (&& 'A' 'B') (&& 'C' 'D'))"

#
def test_parseliteral():
    assert parse_literal("0") == 0
    assert parse_literal("0x32") == 0x32
    assert parse_literal("0o32") == 0o32
    assert parse_literal("0b0101") == 0b0101
    assert parse_literal("True") == True
    assert parse_literal("0.1") == 0.1
    assert parse_literal("-0.25") == -0.25
    assert parse_literal("'string'") == "string"

    assert parse_literal("unknown") == "unknown"


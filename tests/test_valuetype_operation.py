import pytest

from machaon.object.operation import (
    tokenize, TOKEN_BLOCK_BEGIN, TOKEN_BLOCK_END,
    expression, parser_context, eval_context,
    parse_operator_name, modify_operator, resolve_operator,
    OPERATION_REVERSE, OPERATION_NEGATE
)

class octopus:
    def get_operator(self, name):
        return getattr(self, name, None)
    def count_leg(self):
        return 8
    def get_color(self):
        return "red"

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
def test_nocontext_parse_expression():
    cxt = parser_context()
    ecxt = eval_context()
    
    def parse_expression(*tokens):
        return cxt.parse(*tokens)

    expr = parse_expression("price * 0.7")
    assert expr.S(debug_operator=True) == "(operator.mul 'price' 0.7)"

    expr = parse_expression(expr, "* 1.1")
    assert expr.S(debug_operator=True) == "(operator.mul (operator.mul 'price' 0.7) 1.1)"
    
    expr = parse_expression(parse_expression("A && B"), "||", parse_expression("C && D"))
    assert expr.S(debug_operator=True) == "(mbuiltin.logical_or (mbuiltin.logical_and 'A' 'B') (mbuiltin.logical_and 'C' 'D'))"
    
    expr = parse_expression("0.5 + 0.2")
    assert expr.S(debug_operator=True) == "(operator.add 0.5 0.2)"
    assert expr.eval(ecxt) == 0.7

    expr = parse_expression(parse_expression("2 ** 8"), "==", parse_expression("4 ** 4"))
    assert expr.S(debug_operator=True) == "(operator.eq (operator.pow 2 8) (operator.pow 4 4))"
    assert expr.eval(ecxt) is True
    
    expr = parse_expression(parse_expression("sea-of-nurnen slice 7 -3"), "== nur")
    assert expr.S(debug_operator=True) == "(operator.eq (mbuiltin.string_slice 'sea-of-nurnen' 7 -3) 'nur')"
    assert expr.eval(ecxt) is True
    
    assert parse_expression(parse_expression("sea-of-nurnen slice None 3"), "== sea").eval(ecxt) is True
    assert parse_expression(parse_expression("sea-of-nurnen slice 7"), "== nurnen").eval(ecxt) is True

    assert parse_expression("sea-of-nurnen startswith sea").eval(ecxt) is True

#
def test_nocontext_parse_literal():
    cxt = parser_context()

    def parse_literal(lit):
        return cxt.parse_literal(lit)

    assert parse_literal("0") == 0
    assert parse_literal("0x32") == 0x32
    assert parse_literal("0o32") == 0o32
    assert parse_literal("0b0101") == 0b0101
    assert parse_literal("True") == True
    assert parse_literal("0.1") == 0.1
    assert parse_literal("-0.25") == -0.25
    assert parse_literal("'string'") == "string"
    assert parse_literal("unknown") == "unknown"

#
def test_parse_operator_name():
    assert parse_operator_name("lt") == ("lt", 0)
    assert parse_operator_name("~greater") == ("greater", OPERATION_REVERSE)
    assert parse_operator_name("!startswith") == ("startswith", OPERATION_NEGATE)
    assert parse_operator_name("!special-reg-match") == ("special_reg_match", OPERATION_NEGATE)

def test_modify_operator():
    assert modify_operator(lambda l,r:l<r, 0)(3, 4)
    assert modify_operator(lambda l,r:l<r, OPERATION_NEGATE)(4, 3)
    assert modify_operator(lambda l,r:l/r, OPERATION_REVERSE)(6, 3) == 3/6

def test_resolve_operator():
    import operator
    assert resolve_operator(None, "le") is operator.le
    assert resolve_operator(None, "is") is operator.is_

    assert resolve_operator(octopus(), "count_leg")() == 8
    assert resolve_operator(octopus(), "query_interface") is None

    assert resolve_operator(None, "&&")(True, False) is False

#
#
def test_contextual_parse_expression():
    cxt = parser_context({"octopus":octopus()}, {})

    def parse_expression(*tokens):
        return cxt.parse(*tokens)

    expr = parse_expression("price * 0.7")
    assert expr.S() == "(mul 'price' 0.7)"


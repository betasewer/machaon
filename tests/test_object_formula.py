import pytest

from machaon.object.type import TypeTraits, TypeModule
from machaon.object.desktop import ObjectDesktop
from machaon.object.formula import (
    tokenize_expression, TOKEN_BLOCK_BEGIN, TOKEN_BLOCK_END,
    FormulaParser, FormulaExpression, ValuesEvalContext,
    parse_formula
)


#
#========================================================
# テスト
#========================================================
#
def test_tokenize():
    assert list(
        tokenize_expression("modtime within 2010/06/05 2012/08/07")
    ) == [
        TOKEN_BLOCK_BEGIN, "modtime within 2010/06/05 2012/08/07", TOKEN_BLOCK_END
    ]

    assert list(
        tokenize_expression("(name == kenzo) && (age == 20)")
    ) == [
        TOKEN_BLOCK_BEGIN, 
            TOKEN_BLOCK_BEGIN, "name == kenzo", TOKEN_BLOCK_END, 
        " && ",  # 空白には手を加えない
            TOKEN_BLOCK_BEGIN, "age == 20", TOKEN_BLOCK_END,
        TOKEN_BLOCK_END
    ]

    assert list(
        tokenize_expression("(age+20)isodd ")
    ) == [
        TOKEN_BLOCK_BEGIN, 
            TOKEN_BLOCK_BEGIN, "age+20", TOKEN_BLOCK_END, 
        "isodd ", 
        TOKEN_BLOCK_END
    ]

    assert list(
        tokenize_expression("isalive and (age < 30)")
    ) == [
        TOKEN_BLOCK_BEGIN, 
        "isalive and ",
            TOKEN_BLOCK_BEGIN, "age < 30", TOKEN_BLOCK_END, 
        TOKEN_BLOCK_END
    ]

#
def test_nocontext_parse_expression():
    parser = FormulaParser()
    ecxt = ValuesEvalContext({})
    
    def parse_expression(*tokens):
        tokens = [TOKEN_BLOCK_BEGIN, *tokens, TOKEN_BLOCK_END] 
        return parser.parse(tokens)

    expr = parse_expression("price * 0.7")
    assert expr.S(debug_operator=True) == "(std_operator.mul 'price' 0.7)"

    expr = parse_expression(expr, "* 1.1")
    assert expr.S(debug_operator=True) == "(std_operator.mul (std_operator.mul 'price' 0.7) 1.1)"
    
    expr = parse_expression(parse_expression("A && B"), "||", parse_expression("C && D"))
    assert expr.S(debug_operator=True) == "(machaon_operator.logical_or (machaon_operator.logical_and 'A' 'B') (machaon_operator.logical_and 'C' 'D'))"
    
    expr = parse_expression("0.5 + 0.2")
    assert expr.S(debug_operator=True) == "(std_operator.add 0.5 0.2)"
    assert expr.eval(ecxt) == 0.7

    expr = parse_expression(parse_expression("2 ** 8"), "==", parse_expression("4 ** 4"))
    assert expr.S(debug_operator=True) == "(std_operator.eq (std_operator.pow 2 8) (std_operator.pow 4 4))"
    assert expr.eval(ecxt) is True
    
    expr = parse_expression(parse_expression("sea-of-nurnen slice 7 -3"), "== nur")
    assert expr.S(debug_operator=True) == "(std_operator.eq (machaon_operator.slice_ 'sea-of-nurnen' 7 -3) 'nur')"
    assert expr.eval(ecxt) is True
    
    #
    # 実行
    #
    assert parse_expression(parse_expression("sea-of-nurnen slice None 3"), "== sea").eval(ecxt) is True
    assert parse_expression(parse_expression("sea-of-nurnen slice 7"), "== nurnen").eval(ecxt) is True

    assert parse_expression("sea-of-nurnen startswith sea").eval(ecxt) is True

#
def test_nocontext_parse_literal():
    parser = FormulaParser()
    def parse_literal(lit):
        return parser.parse_arg_string(lit)

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
#
#
class Octopus:
    def leg_count(self):
        return 8
    
    def color(self):
        return "#800000"

    def price(self):
        return 2500
    
    def compare(self, right):
        return True
    
    @classmethod
    def describe_object(cls, traits):
        traits.describe(
            typename="octopus"
        )["member leg-count"](
            help="足の数"
        )["member color"](
            help="色"
        )["member price"](
            help="値段"
        )["operator compare"](
            help="比較"
        )

class Aquarium():
    def octopus(self):
        return Octopus()
    
    @classmethod
    def describe_object(cls, traits):
        traits.describe(
            typename="aquarium"
        )["member octopus"](
            help="タコを生成"
        )


@pytest.fixture
def objectdesk():
    desk = ObjectDesktop()
    from machaon.object.fundamental import fundamental_type
    desk.add_types(fundamental_type)
    return desk

def test_contextual_parse_expression(objectdesk):
    parser = FormulaParser(objectdesk.get_type(Octopus), objectdesk)

    def parse_expression(*tokens):
        tokens = [TOKEN_BLOCK_BEGIN, *tokens, TOKEN_BLOCK_END] 
        return parser.parse(tokens)

    expr = parse_expression("@price * 0.7")
    assert expr.S(debug_operator=True) == "(std_operator.mul [operand price] 0.7)"
    assert expr.eval(ValuesEvalContext({"price":2500})) == 2500 * 0.7


def test_parse_formula(objectdesk):
    def p(expr):
        f = parse_formula(expr, objectdesk, objectdesk.get_type(Octopus))
        cxt = f.create_values_context(Octopus())
        return f(cxt)

    assert p("(1 + 2) == 3")
    assert p("nurnen endswith nen")
    assert p("nurnen contains nen")
    assert p("n in nurnen")
    assert p("neleido !in nurnen")

    assert p("(@price * 100) == 250000")
    assert p("((@leg-count + 2) == 10) && (@color == #800000)")

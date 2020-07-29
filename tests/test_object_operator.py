from machaon.object.type import (
    TypeTraits, TypeTraitsDelegation
)
from machaon.object.operator import (
    ObjectOperator, parse_operator_expression,
    OPERATION_REVERSE, OPERATION_NEGATE
)

#
def test_parse_operator_name():
    p = parse_operator_expression
    assert p("lt").calling() == "lt"
    assert p("~greater").calling() == "~greater"
    assert p("!startswith").calling() == "!startswith"
    assert p("!special-reg-match").calling() == "!special-reg-match"

def test_resolve_operator():
    def o(*args):
        return ObjectOperator(*args)

    # 型メソッド（クラス実装）
    class Date(TypeTraits):
        @classmethod
        def describe_type(cls, traits):
            traits.describe(
                typename="datetime"
            )["member isocalendar"](
                help="ISO暦の日付"
            )
        
        def isocalendar(self, date):
            return date.isocalendar()

    import datetime
    d = datetime.date(1990,1,1)
    assert o("isocalendar", Date().make_described(Date))(d) == d.isocalendar()

    # 型メソッド（インスタンス実装）
    class Rakuda():
        def __init__(self):
            self._buggages = 0
        
        def put_buggage(self, num):
            self._buggages += num
            return self._buggages

        @classmethod
        def describe_type(cls, traits):
            traits.describe(
                typename="datetime"
            )["operator put-buggage"](
                help="荷物を追加する",
                return_type=int
            )

    rak = Rakuda()
    raktype = TypeTraitsDelegation(Rakuda).make_described(Rakuda)
    assert o("put-buggage", raktype)(rak, 3) == 3
    assert o("put-buggage", raktype)(rak, 2) == 5

    # 標準演算子
    import operator
    assert o("le", None, 0)._resolved is operator.le
    assert o("is", None, 0)._resolved is operator.is_
    assert o("in")(2, [1,2,3])
    assert o("contains")([1,2,3], 2)
    assert o("&&")(True, False) is False # machaon_operator

    # インスタンスメソッド
    assert o("startswith")("doggy", "do")
    assert o("endswith", None, OPERATION_NEGATE)("berulade", "xxx")
    assert o("bit-length")(32) == (32).bit_length()
    
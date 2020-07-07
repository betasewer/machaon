from typing import Sequence, Optional, Any, List

#
#
#
# type_traitsで使用されるメンバ
type_traits_members = [
    "value_type",
    "from_string",
    "to_string",
]

#
class int_type():
    value_type = int

    @staticmethod
    def from_string(s):
        return int(s)
        
class float_type():
    value_type = float

    @staticmethod
    def from_string(s):
        return float(s)

class string_type():
    value_type = str

    @staticmethod
    def from_string(s):
        return s

# デフォルト
def _to_string(v):
    if v is None:
        return ""
    else:
        return str(v)

#
#
#
OPERATION_REVERSE = 0x1
OPERATION_NEGATE = 0x2

#
operators_map = {
    "==" : "eq",
    "!=" : "ne",
    "<=" : "le",
    "<" : "lt",
    ">=" : "ge",
    ">" : "gt",
    "in" : "~contains",
}
def parse_operator_name(expression):
    bits = 0

    if expression.startswith("~"):
        bits |= OPERATION_REVERSE
        expression = expression[1:]
    
    if expression.startswith("!"):
        bits |= OPERATION_NEGATE
        expression = expression[1:]

    operator_name = operators_map.get(expression, expression).replace("-","_")
    
    return operator_name, bits

#
def modify_operator(operator, bits):
    opr = operator

    if bits & OPERATION_REVERSE:
        def rev(fn):
            def _rev(*a):
                return fn(*reversed(a))
            return _rev
        opr = rev(opr)

    if bits & OPERATION_NEGATE:
        def neg(fn):
            def _neg(*a):
                return not opr(*a)
            return _neg
        opr = neg(opr)
    
    return opr

#
#
#
def parse_operator_operation(type_traits, expression):
    operator_name, bits = parse_operator_name(expression)

    # 予め定義されたオペレータ
    opr = getattr(type_traits, operator_name, None)
    if opr is None:
        # 標準のオペレーターを使う
        import operator
        opr = getattr(operator, operator_name, None)
        if opr is None:
            # 左辺値のメソッドを呼び出す
            def lhs_operation(left, right):
                return getattr(left, operator_name)(right)
            opr = lhs_operation

    if bits > 0:
        opr = modify_operator(opr, bits)
    return opr

#
#
#
def _search_operators(specs, obj, title, testrunval=None):
    for name in dir(obj):
        if any(x for x, _, _ in specs if x==name):
            continue
        if name.startswith("__"):
            continue

        ca = getattr(obj, name, None)
        if not callable(ca):
            continue

        #
        import inspect
        try:
            sig = inspect.signature(ca)
        except ValueError:
            continue

        arity = len(sig.parameters)
        if arity <= 0 or 3 <= arity:
            continue

        if testrunval is not None:
            if arity == 1:
                try: 
                    r = ca(testrunval)
                except Exception as e: 
                    print(name, e)
                    continue
                
                if not isinstance(r, (bool, type(testrunval))):
                    print(name, "not unary operatable result type {}".format(type(r).__name__))
                    continue
            
            elif arity == 2:
                try: 
                    r = ca(testrunval, testrunval)
                except Exception as e: 
                    print(name, e)
                    continue
        
                if not isinstance(r, bool):
                    print(name, "not binary operatable result type {}".format(type(r).__name__))
                    continue

        specs.append((name, arity, title))

    return specs

#
#
def list_predicate_operations(type_traits=None, *, value_type=None, testrun=False):
    specs = []
    if testrun:
        testval = type_traits.value_type()
    else:
        testval = None
    
    # type_traitsから検索
    _search_operators(specs, type_traits, str(type_traits))
    # -- type_traits専用のメンバを除外する
    specs = [(x,_a,_b) for (x,_a,_b) in specs if x not in type_traits_members] 

    # 汎用の演算子から検索
    import operator
    _search_operators(specs, operator, "generic-operator", testval)
    # -- 記号形式を追加する
    for sign, name in operators_map.items():
        for n, arity, _ in specs:
            if n == name:
                specs.append((sign, arity, "generic-operator"))

    # 値のメソッドの中から検索
    _search_operators(specs, type_traits.value_type, str(type_traits.value_type), testval)
    
    return specs

#
import pprint
pprint.pprint(list_predicate_operations(float_type, testrun=True))


#
#
#
class Predicate():
    class NOVALUE():
        pass
    class UNDEFINED():
        pass

    def __init__(self, 
        predtype, 
        description,
        value,
    ):
        self.description = description
        self.value = value or Predicate.UNDEFINED
        
        #
        if isinstance(predtype, type):
            pass
        elif not predtype or predtype == "str":
            predtype = string_type
        elif predtype == "int":
            predtype = int_type
        elif predtype == "float":
            predtype = float_type
        elif predtype == "datetime":
            predtype = string_type #
        else:
            raise BadOperatorError(predtype)
        self.predtype = predtype

    def get_description(self):
        return self.description
    
    def get_pred_type(self):
        return self.predtype

    def is_number(self):
        return self.predtype == "int" or self.predtype == "float"
    
    def is_printer(self):
        return self.predtype == "printer"
    
    #
    def get_value(self, item):
        if self.is_printer():
            return Predicate.NOVALUE
        else:
            return self.value(item)
    
    def do_print(self, item, spirit):
        if self.is_printer():
            self.value(item, spirit)
        else:
            v = self.value(item)
            spirit.message(v)
    
    def value_to_string(self, value):
        if self.is_printer() or value is Predicate.NOVALUE:
            return Predicate.NOVALUE
        elif hasattr(self.predtype, "to_string"):
            return self.predtype.to_string(value)
        else:
            return _to_string(value)
    
    #
    def parse_operation(self, operator_expression: str):
        return parse_operator_operation(self.predtype, operator_expression)
    
    def parse_operands(self, operand_expressions: Sequence[str]):
        return [self.predtype.from_string(x) for x in operand_expressions]

#
#
#
class BadPredicateError(Exception):
    def __init__(self, pred):
        self.pred = pred
    def __str__(self):
        return "'{}'は不明な述語です".format(self.pred)
        
class BadOperatorError(Exception):
    def __init__(self, pred):
        self.pred = pred
    def __str__(self):
        return "'{}'は不明な演算子です".format(self.pred)

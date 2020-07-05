from typing import Sequence, Optional, Any, List

#
#
#
class int_type():
    @staticmethod
    def from_string(s):
        return int(s)
        
class float_type():
    @staticmethod
    def from_string(s):
        return float(s)

class string_type():
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
operators_map = {
    "==" : "eq",
    "!=" : "ne",
    "<=" : "le",
    "<" : "lt",
    ">=" : "ge",
    ">" : "gt",
    "}" : "contains",
    "{" : "~contains",
    "in" : "~contains",
}
def parse_operator_operation(type_traits, expression):
    invbit = False
    operator_name = operators_map.get(expression, expression).replace("-","_")
    if operator_name.startswith("~"):
        invbit = True
        operator_name = operator_name[1:]

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

    if invbit:
        def _inv(l,r):
            return opr(r,l)
        return _inv
    return opr

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

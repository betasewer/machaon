from typing import Sequence, List, Any, Tuple

#
class BadPredicateError(Exception):
    pass

#
#
#
class ValueWrapper():
    def __init__(self, value, compare_operator):
        self.value = value
        self.compare = compare_operator
    
    def __lt__(self, right) -> bool:
        left = self
        if left.value is None and right.value is not None:
            return True
        elif right.value is None:
            return False
        return left.compare(left.value, right.value)
    
    def __eq__(self, right) -> bool:
        left = self
        return left.value == right.value
    
#
#
#
class Sortkey():
    def __init__(self):
        self._predicates: List[Tuple[str, bool]] = [] # (predicate, isascend)
        self._operators: List[Any] = [] # lessthan-operator

    def add(self, predicate, ascend):
        self._predicates.append((predicate, ascend))
    
    def setup_operators(self, dataview):
        for member_name, ascend in self._predicates:
            if member_name == "" and not ascend:
                member_name = dataview.get_top_column_name()
            
            column = dataview.find_current_column(member_name)
            if column is None:
                raise BadPredicateError(member_name)

            # 比較演算子（less）を決定
            lessthan_opr = column.make_compare_operator(lessthan=ascend)
            self._operators.append(lessthan_opr)
    
    def __call__(self, evalcontext) -> Tuple[ValueWrapper, ...]:
        values = []
        for (member_name, _), ltopr in zip(self._predicates, self._operators):
            val = evalcontext.get_member_value(member_name)
            values.append(ValueWrapper(val, ltopr))
        return tuple(values)
    
    def get_related_members(self) -> List[str]:
        return [x for (x,_) in self._predicates]

#
#
#
def parse_sortkey(expression: str):
    key = Sortkey()

    for predicate in expression.split(","):
        # 昇順（デフォ）か降順か
        if predicate.startswith("!"):
            ascend = False
            predicate = predicate[1:]
        else:
            ascend = True
        
        key.add(predicate, ascend)
    
    return key

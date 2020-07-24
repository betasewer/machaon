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
        self.predicates: List[Tuple[str, Any, bool]] = [] # (predicate, lessthan-operator, isascend)
    
    def add(self, predicate, lessthan_opr, ascend):
        self.predicates.append((predicate, lessthan_opr, ascend))
    
    def __call__(self, row: Sequence[Any]) -> Tuple[ValueWrapper, ...]:
        return tuple(ValueWrapper(v, ltopr) for v, (_, ltopr, _) in zip(row, self.predicates))
    
    def get_related_members(self) -> List[str]:
        return [x for (x,_,_) in self.predicates]

#
#
#
def parse_sortkey(expression: str, dataset, objdesk):
    key = Sortkey()

    for predicate in expression.split(","):
        # 昇順（デフォ）か降順か
        if predicate.startswith("~"):
            ascend = False
            predicate = predicate[1:]
        else:
            ascend = True

        # 述語を取得する
        if predicate == "" and not ascend:
            predicate = dataset.get_top_column_name()
        
        column = dataset.make_column(predicate, objdesk)
        if column is None:
            raise BadPredicateError(predicate)

        # 比較演算子（less）を決定
        lessthan_opr = column.make_compare_operator(lessthan=ascend)

        key.add(predicate, lessthan_opr, ascend)
    
    return key

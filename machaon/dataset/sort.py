from typing import Sequence, List, Any, Tuple
from machaon.dataset.predicate import Predicate, BadPredicateError

#
#
#
class KeyWrapper():
    def __init__(self, value, opr):
        self.value = value
        self.ltopr = opr
    
    def __lt__(self, right) -> bool:
        left = self
        if left.value is None and right.value is not None:
            return True
        elif right.value is None:
            return False
        return left.ltopr(left.value, right.value)
    
    def __eq__(self, right) -> bool:
        left = self
        return left.value == right.value
    
#
#
#
class DataSortKey():
    def __init__(self, ref, expression: str, dispmode=False):
        self.ref = ref
        self.failure = None

        columnnames = []
        sortspec = []
        parts = expression.split()
        for part in parts:
            # 昇順（デフォ）か降順か
            ascsort = True
            if part.startswith("~"):
                ascsort = False
                part = part[1:]

            # 述語を取得する
            if part == "_":
                predname, pred = self.ref.get_first_pred()
            else:
                pred = self.ref.find_pred(part)
                predname = part
            if pred is None:
                raise BadPredicateError(part)

            # 比較演算子（less）を決定
            if ascsort:
                ltopr = pred.parse_operation("lt")
            else:
                ltopr = pred.parse_operation("~lt")

            sortspec.append((ascsort, ltopr))
            columnnames.append(predname)

        self.related_columns: List[str] = columnnames
        self.sortspec = sortspec
    
    def __call__(self, row: Sequence[Any]) -> Tuple[KeyWrapper, ...]:
        if len(self.related_columns) != len(row):
            raise ValueError("invalid row length")
        return tuple(KeyWrapper(x, opr) for x, (_, opr) in zip(row, self.sortspec))
    
    def get_related_columns(self) -> List[str]:
        return self.related_columns

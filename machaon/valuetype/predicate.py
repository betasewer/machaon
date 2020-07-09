from collections import defaultdict
from typing import Any, Dict, List, Sequence, Optional, Tuple, DefaultDict

#
#
#
class predicate():
    class PRINTER():
        pass
    class UNDEFINED():
        pass

    def __init__(self, 
        typetraits, 
        description,
        value,
    ):
        self.description = description
        self.value = value or predicate.UNDEFINED
        self.predtype = typetraits

    def get_description(self):
        return self.description
    
    def get_type(self):
        return self.predtype

    def is_printer(self):
        return self.predtype is predicate.PRINTER
    
    #
    def get_value(self, item):
        if self.is_printer():
            return predicate.PRINTER
        else:
            return self.value(item)
    
    def do_print(self, item, spirit):
        if self.is_printer():
            self.value(item, spirit)
        else:
            v = self.value(item)
            spirit.message(v)
    
    def value_to_string(self, value):
        if self.is_printer():
            return predicate.PRINTER
        else:
            return self.predtype.convert_to_string(value)

#
#
#
class BadPredicateError(Exception):
    def __init__(self, pred):
        self.pred = pred
    def __str__(self):
        return "'{}'は不明な述語です".format(self.pred)

#
#
#
class predicate_library():
    def __init__(self, *, itemclass):
        self._predicates: Dict[str, Tuple[str, predicate]] = {}
        self._alias: Dict[str, List[str]] = {} 
    
    def add(self, names, p):
        firstname, _keywords = names
        if "_top" not in self._alias:
            self._alias["_top"] = [firstname]
        for name in names:
            self._predicates[name] = (firstname, p)
    
    def get(self, name) -> Optional[predicate]:
        entry = self._predicates.get(name, None)
        if entry:
            return entry[1]
        return None

    def get_entry(self, name) -> Tuple[str, predicate]:
        try:
            return self._predicates[name]
        except KeyError:
            raise BadPredicateError(name)
    
    def get_top_entry(self):
        if "_top" not in self._alias:
            raise BadPredicateError("<no first predicate specified>")
        name = self._alias["_top"][0]
        return self.get_entry(name)
    
    def getall(self) -> List[Tuple[predicate, List[str]]]:
        predset: DefaultDict[predicate, List[str]] = defaultdict(list)
        for key, (_topkey, pred) in self._predicates.items():
            predset[pred].append(key)

        entries = list(predset.items())
        entries.sort(key=lambda e:e[1][0])
        return entries

    def normalize_name(self, name) -> str:
        return self.get_entry(name)[0]

    def select_preds(self, column_names):
        preds = []
        invalids = []
        for column_name in column_names:
            if column_name in self._predicates:
                preds.append(self.get_pred(column_name)[1])
            else:
                invalids.append(column_name)
        return preds, invalids
        
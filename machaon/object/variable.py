from collections import defaultdict
from typing import Any, Dict, List, Sequence, Optional, Tuple, DefaultDict, Union

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
class variable():
    def __init__(self, names: str, pred: predicate):
        self.names = names
        self.predicate = pred
    
    @property
    def name(self):
        return self.names[0]
    
    def get_type(self):
        return self.predicate.get_type()

#
#
#
class variable_defs():
    def __init__(self):
        self._variables: Dict[str, variable] = {}
        self._alias: Dict[str, List[str]] = {} 
    
    def new(self, names, *args, **kwargs):
        p = predicate(*args, **kwargs)
        v = variable(names, p)
        return self.add(v)
    
    def add(self, var: variable):
        if "_top" not in self._alias:
            self._alias["_top"] = [var.name]
        for name in var.names:
            self._variables[name] = var
        return var
    
    def get(self, name) -> Optional[variable]:
        v = self._variables.get(name, None)
        if v:
            return v
        return None

    def entry(self, name) -> variable:
        try:
            return self._variables[name]
        except KeyError:
            raise BadPredicateError(name)
    
    def top_entry(self):
        if "_top" not in self._alias:
            raise BadPredicateError("<no first predicate specified>")
        name = self._alias["_top"][0]
        return self.entry(name)
    
    def select(self, names: Sequence[str]) -> Tuple[List[variable], List[str]]:
        if isinstance(names, str):
            raise TypeError("names")
        vas = []
        invalids = []
        for name in names:
            if name in self._variables:
                va = self.entry(name)
                vas.append(va)
            elif name in self._alias:
                for aliasname in self._alias[name]:
                    vas.append(self.entry(aliasname))
            else:
                invalids.append(name)
        return vas, invalids
    
    def selectone(self, name: str):
        if not isinstance(name, str):
            raise TypeError("name")
        prs, _ = self.select((name,))
        return prs[0] if prs else None
    
    def getall(self) -> List[variable]:
        # 重複を取り除く
        buckets: Dict[str, variable] = {}
        for v in self._variables.values():
            if v.name not in buckets:
                buckets[v.name] = v
                
        entries = sorted(buckets.values(), key=lambda v:v.name)
        return entries
        
    def normalize_names(self, names) -> List[Union[str, None]]:
        ret: List[Union[str, None]] = []
        for name in names:
            if name in self._variables:
                ret.append(self._variables[name].name)
            else:
                ret.append(None)
        return ret
    
    def set_alias(self, name, alias: Union[str, List[str]]):
        if isinstance(alias, str):
            alias = [alias]
        self._alias[name] = alias

#
#
#
class BadPredicateError(Exception):
    def __init__(self, pred):
        self.pred = pred
    def __str__(self):
        return "'{}'は不明な述語です".format(self.pred)

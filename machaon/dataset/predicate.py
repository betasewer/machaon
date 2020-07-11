from typing import Sequence, Optional, Any, List


#
class BadOperatorError(Exception):
    pass
class BadPredicateError(Exception):
    pass

class Predicate:
    pass

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
#import pprint
#pprint.pprint(list_predicate_operations(float_type, testrun=True))


#
def parse_operation(self, operator_expression: str):
    return parse_operator_operation(self.predtype, operator_expression)

def parse_operands(self, operand_expressions: Sequence[str]):
    return [self.predtype.from_string(x) for x in operand_expressions]



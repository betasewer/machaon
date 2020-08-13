import re

from machaon.object.type import TypeTraits
from machaon.object.object import ObjectValue
from machaon.object.message import MessageParser

#-----------------------------------------------------------------------
# スタブ
#
class StrType(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        traits.describe(
            typename="str",
            doc="Python.str",
            value_type=str
        )["operator regmatch -> bool"](
            doc="正規表現に先頭から適合するか"
        )["operator regsearch -> bool"](
            doc="正規表現に一部が適合するか"
        )
    
    def regmatch(self, s, pattern):
        m = re.match(pattern, s)
        if m:
            return True
        return False
    
    def regsearch(self, s, pattern):
        m = re.search(pattern, s)
        if m:
            return True
        return False
        
class IntType(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        traits.describe(
            typename="int",
            doc="Python.int",
            value_type=int
        )

class BoolType(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        traits.describe(
            typename="bool",
            doc="Python.bool",
            value_type=bool
        )

"""
fundamental types -- 

  primitives:
Int
Float
Str
Bool
Complex
List
Dataset

  system:
Object
Window
Invocation

Window data add-column Range new 5 start: 2 step: 2
Window last-invocation what

Constants search 闇
Api search class Card

Cdb all search where 


 name value: クリフォート・アクセス


"""

#
class StubInvocationContext:
    def __init__(self):
        self.locals = []
        self.results = []

    def get_type(self, typename):
        if typename == "str" or typename is str:
            return StrType().make_described(StrType)
        elif typename == "int" or typename is int:
            return IntType().make_described(IntType)
        elif typename == "bool" or typename is bool:
            return BoolType().make_described(BoolType)

    def get_object(self, name):
        pass

    def get_object_by_typename(self, typename):
        pass

    def push_local_object(self, obj):
        self.locals.append(obj)
    
    def top_local_object(self):
        if not self.locals:
            return None
        return self.locals[-1]

    def pop_local_object(self):
        self.locals.pop()

    def get_local_objects(self):
        return self.locals
    
    def get_last_result(self):
        return self.results[-1]
    
    def _push_result(self, val):
        self.results.append(val)
    
    def push_invocation(self, entry):
        self.results.append(entry.get_first_result())

#
class StubInvocation:
    def __init__(self, operator_name, arity):
        import operator
        self.opr = getattr(operator, operator_name)
        self.arity = arity
    
    def get_max_arity(self):
        return self.arity
    
    def get_min_arity(self):
        return self.arity
    
    def invoke(self, context, *args):
        r = self.opr(*args)
        context._push_result(ObjectValue(type(r), r))

#-----------------------------------------------------------------------



def p(s):
    parser = MessageParser(s)
    context = StubInvocationContext()
    parser.run(context, log=True)
    return [x.value for x in context.get_local_objects()]

def run(f):
    f()

#
@run
def test_parse_literals():
    # static method
    assert p("1 add 2") == [3]
    assert p("1 add 2 add 3") == [6]
    assert p("4 neg") == [-4]
    assert p("(5 add 6) neg") == [-11]
    assert p("(7 mul 8) add (9 mul 10) ") == [7*8+9*10]
    assert p("(7 mul 8) add ((9 add (10 neg)) mul 11) ") == [7*8+(9-10)*11]
    
    # dynamic method
    assert p("ABC startswith A") == [True]
    assert p("ABC ljust 5 _") == ["ABC__"]
    assert p("ABC ljust (2 mul 2) _") == ["ABC_"]

    # type method & string literal
    assert p("'9786' regmatch [0-9]+") == [True]


    """
    assert p("0 add 2") == "(0 add 2)"
    assert p("0 minus") == "(0 minus)"
    assert p("0 add 1 minus") == "((0 add 1) minus)"
    assert p("0 add 1 add 2 add 3") == "(((0 add 1) add 2) add 3)"
    assert p("(0 add 1) add (2 add 3)") == "((0 add 1) add (2 add 3))"
    assert p("((0 add 1) minus) add (2 add 3)") == "(((0 add 1) minus) add (2 add 3))"
    #
    assert p("0 add '1)skip'") == "(0 add 1)skip)"
    assert p('''0 add "1) 'Beck' & 'Johny' Store "''') == '''(0 add 1) 'Beck' & 'Johny' Store )'''
    """
    






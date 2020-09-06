from machaon.object.fundamental import fundamental_type
from machaon.object.type import Type, TypeModule

def run(fn):
    fn()

@fundamental_type.definition(typename="Dummy-Rabbit")
class Dummy_Rabbit():
    describe_count = 0
    
    @classmethod
    def describe_object(cls, traits):
        traits.describe(doc="うさぎ")
        cls.describe_count += 1

def test_typemodule_get():
    assert fundamental_type.get("Dummy_Rabbit").typename == "Dummy-Rabbit"
    assert fundamental_type.get(Dummy_Rabbit).typename == "Dummy-Rabbit"
    assert fundamental_type.Dummy_Rabbit.get_method_delegator().describe_count == 1
    
def test_typemodule_move():
    new_typeset = TypeModule()
    new_typeset.define(typename="AltString")
    new_typeset.define(Dummy_Rabbit, typename="Second-Rabbit")

    fundamental_type.add_ancestor(new_typeset)
    
    assert fundamental_type.get("Int").construct_from_string("0x35") == 0x35
    assert fundamental_type.get("AltString").typename == "AltString"
    assert fundamental_type.Dummy_Rabbit.typename == "Dummy-Rabbit"
    assert fundamental_type.Second_Rabbit.typename == "Second-Rabbit"
    assert fundamental_type.Dummy_Rabbit.get_method_delegator().describe_count == 2 # Dummy-Rabbit, Second-Rabbitの両方で呼ばれる

def test_fundamental():
    assert fundamental_type.Int.typename == "Int"
    assert fundamental_type.Int.construct_from_string("32") == 32
    assert fundamental_type.Int.convert_to_string(32) == "32"
    assert fundamental_type.Int.convert_to_string(0xFF) == "255"

    assert fundamental_type.Bool.typename == "Bool"
    assert fundamental_type.Bool.construct_from_string("False") is False

    assert fundamental_type.Float.typename == "Float"
    assert fundamental_type.Float.construct_from_string("-0.05") == -0.05

    assert fundamental_type.Complex.typename == "Complex"
    assert fundamental_type.Complex.construct_from_string("2+3j") == 2+3j

    assert fundamental_type.Str.typename == "Str"
    assert fundamental_type.Str.construct_from_string("AAA") == "AAA"

@run
def test_method():
    regmatch = fundamental_type.Str.select_method("regmatch")
    assert regmatch is not None
    assert regmatch.name == "regmatch"
    assert regmatch.get_first_result_typename() == "Bool"

    act = regmatch.get_action()
    assert act(None, "0123.txt", "[0-9]+")
    assert not act(None, "AIUEO.wav", "[0-9]+")

    assert regmatch.get_action_target() == "TypeMethod:regmatch"


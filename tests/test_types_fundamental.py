from machaon.types.fundamental import fundamental_type
from machaon.core.type import Type, TypeModule

def run(fn):
    fn()

@fundamental_type.definition(typename="Dummy-Rabbit")
class Dummy_Rabbit():
    describe_count = 0
    
    @classmethod
    def describe_object(cls, traits):
        traits.describe(doc="うさぎ")
        cls.describe_count += 1
    
def test_fundamental_find():
    assert fundamental_type.find("Int") is not None

def test_typemodule_get():
    assert fundamental_type.get("Dummy_Rabbit").typename == "Dummy-Rabbit"
    assert fundamental_type.get(Dummy_Rabbit).typename == "Dummy-Rabbit"
    assert fundamental_type.get(Dummy_Rabbit).describer.describe_count == 1

def test_typemodule_move():
    new_typeset = TypeModule()
    new_typeset.define(typename="AltString")
    new_typeset.define(Dummy_Rabbit, typename="Second-Rabbit")

    fundamental_type.add_ancestor(new_typeset)
    
    assert fundamental_type.get("Int").construct_from_string(None, "0x35") == 0x35
    assert fundamental_type.get("AltString").typename == "AltString"
    assert fundamental_type.get("Dummy_Rabbit") is not None
    assert fundamental_type.get("Dummy_Rabbit").typename == "Dummy-Rabbit"
    assert fundamental_type.get("Dummy_Rabbit").describer.describe_count == 2 # Dummy-Rabbit, Second-Rabbitの両方で呼ばれる
    assert fundamental_type.get("Second_Rabbit") is not None
    assert fundamental_type.get("Second_Rabbit").typename == "Second-Rabbit"

def test_fundamental():
    Int = fundamental_type.get("int")
    assert Int.typename == "Int"
    assert Int.construct_from_string(None, "32") == 32
    assert Int.convert_to_string(32) == "32"
    assert Int.convert_to_string(0xFF) == "255"

    Bool = fundamental_type.get("bool")
    assert Bool.typename == "Bool"
    assert Bool.construct_from_string(None, "False") is False

    Float = fundamental_type.get("float")
    assert Float.typename == "Float"
    assert Float.construct_from_string(None, "-0.05") == -0.05

    Complex = fundamental_type.get("complex")
    assert Complex.typename == "Complex"
    assert Complex.construct_from_string(None, "2+3j") == 2+3j

    Str = fundamental_type.get("str")
    assert Str.typename == "Str"
    assert Str.construct_from_string(None, "AAA") == "AAA"

def test_method():
    regmatch = fundamental_type.get("Str").select_method("reg-match")
    assert regmatch is not None
    assert regmatch.name == "reg-match"
    assert regmatch.get_result().get_typename() == "Bool"

    act = regmatch.get_action()
    assert act(None, "0123.txt", "[0-9]+")
    assert not act(None, "AIUEO.wav", "[0-9]+")

    assert regmatch.get_action_target() == "machaon.types.fundamental.StrType:reg-match"

def test_any():
    anytype = fundamental_type.get("Any")
    assert anytype.is_loaded()
    assert anytype.is_any()

def test_function():
    fntype = fundamental_type.get("Function")
    fnpower = fntype.construct_from_string(None, "@ * @")
    assert fnpower
    from machaon.core.message import MessageEngine
    assert isinstance(fnpower, MessageEngine)


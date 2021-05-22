from machaon.types.fundamental import fundamental_type
from machaon.core.type import Type, TypeModule
from machaon.core.object import Object

def run(fn):
    fn()

class Dummy_Rabbit():
    describe_count = 0
    
    @classmethod
    def describe_object(cls, traits):
        traits.describe(doc="うさぎ")
        cls.describe_count += 1
    

fundamental_type.define(Dummy_Rabbit, typename="Dummy-Rabbit")

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
    
    assert fundamental_type.get("Int").construct(None, "0x35") == 0x35
    assert fundamental_type.get("AltString").typename == "AltString"
    assert fundamental_type.get("Dummy_Rabbit") is not None
    assert fundamental_type.get("Dummy_Rabbit").typename == "Dummy-Rabbit"
    assert fundamental_type.get("Dummy_Rabbit").describer.describe_count == 2 # Dummy-Rabbit, Second-Rabbitの両方で呼ばれる
    assert fundamental_type.get("Second_Rabbit") is not None
    assert fundamental_type.get("Second_Rabbit").typename == "Second-Rabbit"

def test_fundamental():
    Int = fundamental_type.get("int")
    assert Int.typename == "Int"
    assert Int.construct(None, "32") == 32
    assert Int.convert_to_string(32) == "32"
    assert Int.convert_to_string(0xFF) == "255"

    Bool = fundamental_type.get("bool")
    assert Bool.typename == "Bool"
    assert Bool.construct(None, "False") is False

    Float = fundamental_type.get("float")
    assert Float.typename == "Float"
    assert Float.construct(None, "-0.05") == -0.05

    Complex = fundamental_type.get("complex")
    assert Complex.typename == "Complex"
    assert Complex.construct(None, "2+3j") == 2+3j

    Str = fundamental_type.get("str")
    assert Str.typename == "Str"
    assert Str.construct(None, "AAA") == "AAA"

def test_method():
    regmatch = fundamental_type.get("Str").select_method("reg-match")
    assert regmatch is not None
    assert regmatch.name == "reg-match"
    assert regmatch.get_result().get_typename() == "Bool"

    act = regmatch.get_action()
    assert act(None, "0123.txt", "[0-9]+")
    assert not act(None, "AIUEO.wav", "[0-9]+")

    assert regmatch.get_action_target() == "Str:reg-match"

def test_any():
    anytype = fundamental_type.get("Any")
    assert anytype.is_loaded()
    assert anytype.is_any()
    assert anytype.value_type is None
    inst = Dummy_Rabbit()
    assert anytype.convert_to_string(inst) == anytype.describer.stringify(anytype, inst)

def test_function():
    fntype = fundamental_type.get("Function")
    fnpower = fntype.construct(None, "@ * @")
    assert fnpower
    from machaon.core.message import MessageEngine
    assert isinstance(fnpower, MessageEngine)


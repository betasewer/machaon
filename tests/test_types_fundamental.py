from machaon.types.fundamental import fundamental_type
from machaon.core.type import Type, TypeModule
from machaon.core.object import Object
from machaon.core.invocation import instant_context

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
    
    cxt = instant_context()
    cxt.type_module = fundamental_type

    assert cxt.get_type("Int").construct(cxt, "0x35") == 0x35
    assert cxt.get_type("AltString").typename == "AltString"
    assert cxt.get_type("Dummy_Rabbit") is not None
    assert cxt.get_type("Dummy_Rabbit").typename == "Dummy-Rabbit"
    assert cxt.get_type("Dummy_Rabbit").describer.describe_count == 2 # Dummy-Rabbit, Second-Rabbitの両方で呼ばれる
    assert cxt.get_type("Second_Rabbit") is not None
    assert cxt.get_type("Second_Rabbit").typename == "Second-Rabbit"

def test_fundamental():
    cxt = instant_context()

    Int = cxt.get_type("int")
    assert Int.typename == "Int"
    assert Int.construct(cxt, "32") == 32
    assert Int.stringify_value(32) == "32"
    assert Int.stringify_value(0xFF) == "255"

    Bool = fundamental_type.get("bool")
    assert Bool.typename == "Bool"
    assert Bool.construct(cxt, "False") is False

    Float = fundamental_type.get("float")
    assert Float.typename == "Float"
    assert Float.construct(cxt, "-0.05") == -0.05

    Complex = fundamental_type.get("complex")
    assert Complex.typename == "Complex"
    assert Complex.construct(cxt, "2+3j") == 2+3j

    Str = fundamental_type.get("str")
    assert Str.typename == "Str"
    assert Str.construct(cxt, "AAA") == "AAA"

def test_method():
    cxt = instant_context()

    regmatch = cxt.get_type("Str").select_method("reg-match")
    assert regmatch is not None
    assert regmatch.name == "reg-match"
    assert regmatch.get_result().get_typename() == "bool"

    act = regmatch.get_action()
    assert act(None, "0123.txt", "[0-9]+")
    assert not act(None, "AIUEO.wav", "[0-9]+")

    assert regmatch.get_action_target() == "Str:reg-match"

def test_any():
    anytype = fundamental_type.get("Any")
    assert anytype.is_loaded()
    assert anytype.is_any_type()
    assert anytype.value_type is None
    inst = Dummy_Rabbit()
    assert anytype.stringify_value(inst) == anytype.describer.stringify(anytype, inst)

def test_function():
    cxt = instant_context()

    fntype = cxt.get_type("Function")
    fnpower = fntype.construct(cxt, "@ * @")
    assert fnpower
    from machaon.core.message import MessageExpression
    assert isinstance(fnpower, MessageExpression)


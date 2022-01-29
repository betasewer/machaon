from machaon.core.typedecl import METHODS_BOUND_TYPE_TRAIT_INSTANCE
from machaon.types.fundamental import fundamental_types
from machaon.core.type import TYPE_TYPETRAIT_DESCRIBER, Type, TypeModule
from machaon.core.object import Object
from machaon.core.invocation import instant_context

fundamental_type = fundamental_types()

def run(fn):
    fn()

def test_fundamental_basic():
    t = fundamental_type.find("Bool")
    assert t
    assert t.get_value_type() is bool

    t = fundamental_type.find("Int")
    assert t
    assert t.get_value_type() is int
    assert t.get_conversion() == "Int"
    
    t = fundamental_type.find("Str")
    assert t
    assert t.get_value_type() is str
    assert t.get_conversion() == "Str"
    
    t = fundamental_type.find("Function")
    assert t
    from machaon.core.message import FunctionExpression
    assert t.get_value_type() is FunctionExpression
    
    t = fundamental_type.find("None")
    assert t
    assert t.get_value_type() is type(None)
    assert t.is_none_type()
    
    t = fundamental_type.find("ObjectCollection")
    assert t
    from machaon.core.object import ObjectCollection
    assert t.get_value_type() is ObjectCollection
    assert t.is_object_collection_type


def test_fundamental_metamethod_resolve():
    cxt = instant_context()

    t = fundamental_type.find("Int")
    assert t
    assert len(t.get_type_params()) == 0
    fns = t.resolve_meta_method("constructor", cxt, "0", None)
    assert fns is not None
    assert len(fns[1:]) == 1 # 引数1

    t = fundamental_type.find("Function")
    assert t
    assert len(t.get_type_params()) == 1
    fns = t.resolve_meta_method("constructor", cxt, "0", None)
    assert fns is not None
    assert len(fns[1:]) == 2 # 引数2 (contextあり)
    assert fns[1] is cxt


def test_fundamental_construct():
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

test_method()

def test_function():
    cxt = instant_context()

    fntype = cxt.get_type("Function")
    fnpower = fntype.construct(cxt, "@ * @")
    assert fnpower
    from machaon.core.message import MessageExpression
    assert isinstance(fnpower, MessageExpression)

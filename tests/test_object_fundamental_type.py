#from machaon.object.fundamental import fundamental_type
#from machaon.object.type import TypeTraits, TypeModule

@fundamental_type.definition
class dummy_rabbit(TypeTraits):
    describe_count = 0
    
    @classmethod
    def describe_object(cls, traits):
        traits.describe(
            typename = "dummy-rabbit"
        )
        cls.describe_count += 1

def test_typemodule_get():
    assert fundamental_type.get().typename == "str"
    assert fundamental_type.get("dummy_rabbit").typename == "dummy-rabbit"
    assert fundamental_type.get(dummy_rabbit).typename == "dummy-rabbit"
    assert fundamental_type.dummy_rabbit.describe_count == 1
    
def test_typemodule_move():
    new_typeset = TypeModule()
    new_typeset.define(typename="alt-string")
    new_typeset.define(dummy_rabbit, typename="second-rabbit")

    fundamental_type.add_ancestor(new_typeset)
    
    assert fundamental_type.get().typename == "str"
    assert fundamental_type.get(int).convert_from_string("0x35") == 0x35
    assert fundamental_type.get("alt-string").typename == "alt-string"
    assert fundamental_type.dummy_rabbit.typename == "dummy-rabbit"
    assert fundamental_type.second_rabbit.typename == "second-rabbit"
    assert fundamental_type.dummy_rabbit.describe_count == 1

def test_fundamental():
    assert fundamental_type.int.typename == "int"
    assert fundamental_type.int.convert_from_string("32") == 32
    assert fundamental_type.int.convert_to_string(32) == "32"
    assert fundamental_type.int.convert_to_string(0xFF) == "255"

    assert fundamental_type.bool.typename == "bool"
    assert fundamental_type.bool.convert_from_string("False") is False

    assert fundamental_type.float.typename == "float"
    assert fundamental_type.float.convert_from_string("-0.05") == -0.05

    assert fundamental_type.complex.typename == "complex"
    assert fundamental_type.complex.convert_from_string("2+3j") == 2+3j

    assert fundamental_type.str.typename == "str"
    assert fundamental_type.str.convert_from_string("AAA") == "AAA"

def test_method():
    regmatch = fundamental_type.str.get_method("regmatch")
    assert regmatch is not None
    assert regmatch.name == "regmatch"
    assert regmatch.return_typecode == "bool"
    assert regmatch.resolve(fundamental_type.str)("0123.txt", "[0-9]+")
    assert not regmatch.resolve(fundamental_type.str)("AIUEO.wav", "[0-9]+")


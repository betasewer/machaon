from machaon.object import types


def test_fundamental():
    assert types.int.typename == "int"
    assert types.int.convert_from_string("32") == 32
    assert types.int.convert_to_string(32) == "32"
    assert types.int.convert_to_string(0xFF) == "255"
    
    assert types.bool.typename == "bool"
    assert types.bool.convert_from_string("False") is False

    assert types.float.typename == "float"
    assert types.float.convert_from_string("-0.05") == -0.05

    assert types.complex.typename == "complex"
    assert types.complex.convert_from_string("2+3j") == 2+3j

    assert types.str.typename == "str"
    assert types.str.convert_from_string("AAA") == "AAA"


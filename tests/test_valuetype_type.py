from machaon.valuetype import (
    valtype
)
from machaon.valuetype.variable import (
    predicate, variable, variable_defs
)

def test_predicate():
    length = predicate(valtype.int, "its length", lambda item:item["length"])
    assert length.get_description() == "its length"
    assert length.get_type() is valtype.int
    assert not length.is_printer()
    assert length.get_value({"length":32}) == 32
    assert length.value_to_string(32) == "32"

def test_variabledefs():
    defs = variable_defs()
    width = defs.new(("width", "w"), valtype.int, "its width", lambda item:item["width"])
    height = defs.new(("height", "h"), valtype.int, "its height", lambda item:item["height"])
    name = defs.new(("name", "n"), valtype.str, "its name", lambda item:item["name"])

    assert defs.get("width") is width
    assert defs.get("n") is name

    assert defs.top_entry() is width

    assert defs.select(("width", "height")) == ([width, height], [])
    assert defs.select(("undefined", "height")) == ([height], ["undefined"])
    assert defs.selectone("width") is width
    assert defs.selectone("undefined") is None

    assert defs.getall() == [height, name, width]

    assert defs.normalize_names(("w", "h")) == ["width", "height"]

    defs.set_alias("dimension", ["width", "height"])
    assert defs.select(("dimension",)) == ([width, height], [])
    assert defs.select(("n", "dimension")) == ([name, width, height], [])
    assert defs.selectone("dimension") is width # Looks like bad usage

    assert defs.get("dimension") is None # getではエイリアスが利かない


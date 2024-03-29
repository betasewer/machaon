from machaon.core.context import InvocationContext, instant_context
from machaon.macatest import run

def test_newobject_deduction():
    context = instant_context()

    t = context.new_object(1)
    assert t.get_typename() == "Int"

    t = context.new_object(True)
    assert t.get_typename() == "Bool"

    import datetime
    t = context.new_object(datetime.datetime.now())
    assert t.get_typename() == "Datetime"
    
    t = context.new_object([1,2,3])
    assert t.get_typename() == "Tuple"

    t = context.new_object({"a":1, "b":2, "c":3})
    assert t.get_typename() == "ObjectCollection"
    
    from machaon.types.shell import Path
    t = context.new_object(Path("/usr/local"))
    assert t.get_typename() == "Path"


def test_newobject_conversion():
    context = instant_context()

    t = context.new_object([1,2,3], conversion="Tuple")
    assert t.get_typename() == "Tuple"
    assert t.value.count() == 3
    
    t = context.new_object(["A","BB","CCC"], conversion="Sheet[str]")
    assert t.get_typename() == "Sheet"
    assert t.value.count() == 3
    t.value.view(context, "@", "length")
    assert [x.value for x in t.value.column_values(context, "@")] == ["A","BB","CCC"]
    assert [x.value for x in t.value.column_values(context, "length")] == [1,2,3]


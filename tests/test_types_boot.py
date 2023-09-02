from machaon.core.context import instant_context
from machaon.core.type.basic import TypeProxy


def test_boot_package_load():
    cxt = instant_context()

    assert cxt.select_type("Path") is not None
    assert cxt.select_type("TextFile") is not None
    assert cxt.select_type("Datetime") is not None
    assert cxt.select_type("Date") is not None
    assert cxt.select_type("Time") is not None



def test_boot_package_deduce():
    context = instant_context()

    import datetime
    t = context.type_module.deduce(datetime.datetime)
    assert t.get_typename() == "Datetime"
    
    from machaon.types.shell import Path
    t = context.type_module.deduce(Path)
    assert t.get_typename() == "Path"


def test_load_new_module():
    context = instant_context()

    t = context.type_module.select("Flow", "machaon.flow")
    assert t
    assert isinstance(t, TypeProxy)
    assert t.get_describer_qualname() == "machaon.flow.flow.Flow"

    t = context.type_module.select("Flow", "machaon.flow")
    assert t
    assert isinstance(t, TypeProxy)
    assert t.get_describer_qualname() == "machaon.flow.flow.Flow"

    t = context.type_module.select("Flow", "machaon")
    assert t
    assert isinstance(t, TypeProxy)

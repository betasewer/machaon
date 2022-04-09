from machaon.core.context import instant_context
from machaon.macatest import run


def test_boot_package_load():
    cxt = instant_context()

    assert cxt.select_type("Path") is not None
    assert cxt.select_type("TextFile") is not None
    assert cxt.select_type("Datetime") is not None
    assert cxt.select_type("Date") is not None
    assert cxt.select_type("Time") is not None

    assert cxt.type_module.get_subtype("Str", "Enclosed") is not None
    assert cxt.type_module.get_subtype("Date", "Date8") is not None
    assert cxt.type_module.get_subtype("Date", "Sep") is not None


def test_boot_package_deduce():
    context = instant_context()

    import datetime
    t = context.type_module.deduce(datetime.datetime)
    assert t.get_typename() == "Datetime"
    
    from machaon.types.shell import Path
    t = context.type_module.deduce(Path)
    assert t.get_typename() == "Path"

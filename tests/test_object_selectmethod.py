from machaon.core.message import select_method
from machaon.core.invocation import instant_context
from machaon.types.fundamental import fundamental_type
from machaon.core.method import Method

def test_straight_select():
    StrType = fundamental_type.get("Str")

    tm = select_method("reg-match", StrType)
    assert tm
    assert tm.display() == ("TypeMethod", "machaon.types.fundamental.StrType:reg-match", "")

    im = select_method("startswith", StrType)
    assert im
    assert im.display() == ("InstanceMethod", "startswith", "")

    gm = select_method("+", StrType)
    assert gm
    assert gm.display() == ("TypeMethod", "machaon.types.generic.GenericMethods:add", "")

    age_getter = Method("mental-age")
    age_getter.load_as_getter("Int")
    StrType.add_method(age_getter)
    ogm = select_method("mental-age", StrType)
    assert ogm
    assert ogm.display() == ("ObjectGetter", "mental-age", "")


def test_modified_select():
    StrType = fundamental_type.get("Str")

    tm = select_method("!reg-search", StrType)
    assert tm
    assert tm.display() == ("TypeMethod", "machaon.types.fundamental.StrType:reg-search", "negate")

    im = select_method("!startswith", StrType)
    assert im
    assert im.display() == ("InstanceMethod", "startswith", "negate")

    gm = select_method("~in", StrType)
    assert gm
    assert gm.display() == ("TypeMethod", "machaon.types.generic.GenericMethods:is-in", "reverse-args")


def test_anyobject_method_select():
    AnyType = fundamental_type.get("Any")

    im = select_method("instance-method", AnyType)
    assert im
    assert im.display() == ("InstanceMethod", "instance_method", "")

    gm = select_method("<", AnyType)
    assert gm
    assert gm.display() == ("TypeMethod", "machaon.types.generic.GenericMethods:less", "")

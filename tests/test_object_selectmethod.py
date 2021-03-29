from machaon.core.message import select_method
from machaon.core.invocation import instant_context, ObjectRefInvocation
from machaon.types.fundamental import fundamental_type
from machaon.core.method import Method
from machaon.core.object import ObjectCollection, Object

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

def test_objcol_select():
    StrType = fundamental_type.get("Str")

    col = ObjectCollection()
    col.push("apple", Object(StrType, "リンゴ"))
    col.push("gorilla", Object(StrType, "ゴリラ"))
    col.push("trumpet", Object(StrType, "ラッパ"))
    col.push("#delegate", Object(StrType, "コレクション"))

    ColType = fundamental_type.get("ObjectCollection")
    om = select_method("apple", ColType, reciever=col)
    assert om
    assert om.display() == ("ObjectRef", "apple", "")
    
    # メソッドの移譲
    dm = select_method("startswith", ColType, reciever=col)
    assert dm
    assert dm.display() == ("ObjectRef", "startswith", "")


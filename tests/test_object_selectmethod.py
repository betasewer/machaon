import pytest

from machaon.core.message import select_method
from machaon.core.invocation import InstanceMethodInvocation, instant_context, ObjectMemberInvocation
from machaon.core.typedecl import PythonType
from machaon.types.fundamental import fundamental_types
from machaon.core.method import Method
from machaon.core.object import ObjectCollection, Object

fundamental_type = fundamental_types()

def test_straight_select():
    StrType = fundamental_type.get("Str")

    tm = select_method("reg-match", StrType)
    assert tm
    assert tm.display() == ("TypeMethod", "Str:reg-match", "")

    gm = select_method("+", StrType)
    assert gm
    assert gm.display() == ("TypeMethod", "GenericMethods:add", "")


def test_modified_select():
    StrType = fundamental_type.get("Str")

    tm = select_method("!reg-search", StrType)
    assert tm
    assert tm.display() == ("TypeMethod", "Str:reg-search", "negate-result")

    gm = select_method("~in", StrType)
    assert gm
    assert gm.display() == ("TypeMethod", "GenericMethods:is-in", "reverse-args")

    gm = select_method("`=", StrType)
    assert gm
    assert gm.display() == ("TypeMethod", "GenericMethods:identical", "basic-reciever")
    
    gm = select_method("join?", StrType)
    assert gm
    assert gm.display() == ("TypeMethod", "Str:join", "show-help")


def test_pytype_method_select():
    AnyType = PythonType(complex)

    im = select_method("instance-method", AnyType)
    assert im
    assert im.display() == ("InstanceMethod", "instance_method", "")

    gm = select_method("<", AnyType)
    assert gm
    assert gm.display() == ("TypeMethod", "GenericMethods:less", "")


def test_objcol_select():
    StrType = fundamental_type.get("Str")

    # delegate有り
    col = ObjectCollection()
    col.push("apple", Object(StrType, "リンゴ"))
    col.push("gorilla", Object(StrType, "ゴリラ"))
    col.push("trumpet", Object(StrType, "ラッパ"))
    col.set_delegation(Object(StrType, "コレクション"))

    ColType = fundamental_type.get("ObjectCollection")
    om = select_method("apple", ColType, reciever=col)
    assert om
    assert om.display() == ("ObjectMember", "apple", "")
    
    # メソッドの移譲
    dm = select_method("startswith", ColType, reciever=col)
    assert dm
    assert dm.display() == ("ObjectMember", "startswith", "delegate-reciever")

    # delegate無し
    col.set_delegation(None)
    
    om = select_method("gorilla", ColType, reciever=col)
    assert om
    assert om.display() == ("ObjectMember", "gorilla", "")

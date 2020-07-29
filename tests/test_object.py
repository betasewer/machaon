import pytest
from machaon.object.object import Object, ObjectValue
from machaon.object.desktop import ObjectDesktop
from machaon.object.fundamental import fundamental_type

def test_desktop():
    desk = ObjectDesktop()
    desk.add_types(fundamental_type)

    desk.push("obj-1", "int", 3)
    desk.push("obj-2", ObjectValue("int", 100))
    desk.push(Object("obj-3", desk.get_type("complex"), 3+5j))
    desk.push("obj-4", ObjectValue("ip-address", "128.0.0.1"))

    assert desk.pick("obj-1").value == 3

    assert desk.pick_by_type("int").name == 'obj-2'
    assert desk.pick_by_type("complex").name == 'obj-3'
    assert desk.pick_by_type("ip-address").name == 'obj-4'
    assert desk.pick_by_type("ip-address").value == "128.0.0.1"
    

def test_object_new():
    desk = ObjectDesktop()
    desk.add_types(fundamental_type)

    o = desk.new("value", int, 1)
    assert o.name == "value"
    assert o.value == 1
    assert o.type == desk._types.get("int")
    
    # まだオブジェクトは追加されていない
    assert desk.pick_by_type("int") is None
    desk.push(o)
    assert desk.pick_by_type("int") is o

    o2 = desk.push("obj-1", "postcode", 1001623)
    assert desk.pick_by_type("postcode") is o2
    assert o2.type == desk._types.get("postcode")
    assert o2.value == "1001623" # デフォルトは文字列型


def test_object_method():
    desk = ObjectDesktop()
    desk.add_types(fundamental_type)

    o = desk.push("a_sentence", "str", "gegege no ge")

    # 型定義メソッド
    v = o.call_method("regmatch", "[a-zA-Z]+")
    assert v.typecode is bool
    assert v.value is True
    
    # インスタンスメソッド
    v = o.call_method("title")
    assert v.typecode is str
    assert v.value == "Gegege No Ge"

    # グローバルメソッド
    assert o.call_method("length").value == len("gegege no ge")






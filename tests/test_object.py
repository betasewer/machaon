import pytest
from machaon.core.object import Object, ObjectValue, ObjectCollection
from machaon.types.fundamental import fundamental_type

Int = fundamental_type.get("Int")
Float = fundamental_type.get("Float")
Complex = fundamental_type.get("Complex")

def run(f):
    f()
@run
def test_desktop():
    desk = ObjectCollection()

    desk.push("obj-1", Object(Int, 100))
    desk.push("obj-2", Object(Int, 7))
    desk.push("obj-3", Object(Complex, 3+5j))
    desk.push("obj-4", Object(fundamental_type.new("IpAddress"), "128.0.0.1"))

    assert desk.get_by_name("obj-1").value == 100

    assert desk.get_by_type("int").name == 'obj-2' # 最後に追加したオブジェクトになる
    assert desk.get_by_type("complex").name == 'obj-3'
    assert desk.get_by_type("IpAddress").name == 'obj-4'
    assert desk.get_by_type("IpAddress").value == "128.0.0.1"

    # まだオブジェクトは追加されていない
    assert desk.get_by_type("float") is None
    o = desk.push("obj-5", Object(Float, 33.3))
    assert desk.get_by_type("float") is o


def test_object_new():
    desk = ObjectCollection()

    o = desk.new("obj-new", Int, 128)
    assert o.name == "obj-new"
    assert o.value == 128
    assert o.type == Int
    
"""
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
"""




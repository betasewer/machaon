import pytest

from machaon.core.message import select_method
from machaon.core.type.extend import get_type_extension_loader
from machaon.core.type.pytype import PythonType
from machaon.types.fundamental import fundamental_types
from machaon.core.object import ObjectCollection, Object
from machaon.core.context import instant_context

fundamental_type = fundamental_types()

def test_straight_select():
    StrType = fundamental_type.get("Str")

    tm = select_method("reg-match", StrType)
    assert tm
    assert tm.display() == ("TypeMethod", "Str:machaon.core#reg-match", "")

    gm = select_method("+", StrType)
    assert gm
    assert gm.display() == ("TypeMethod", "Generic:machaon.core#add", "")


def test_modified_select():
    StrType = fundamental_type.get("Str")

    tm = select_method("reg-search!", StrType)
    assert tm
    assert tm.display() == ("TypeMethod", "Str:machaon.core#reg-search", "negate-result")

    gm = select_method("in>", StrType)
    assert gm
    assert gm.display() == ("TypeMethod", "Generic:machaon.core#is-in", "consume-args")

    gm = select_method("identity`", StrType)
    assert gm
    assert gm.display() == ("TypeMethod", "Generic:machaon.core#identity", "basic-reciever")
    
    gm = select_method("join?", StrType)
    assert gm
    assert gm.display() == ("TypeMethod", "Str:machaon.core#join", "show-help")


def test_pytype_method_select():
    AnyType = PythonType(complex)

    im = select_method("instance-method", AnyType)
    assert im
    assert im.display() == ("InstanceMethod", "instance_method", "")

    gm = select_method("<", AnyType)
    assert gm
    assert gm.display() == ("TypeMethod", "Generic:machaon.core#less", "")


def test_objcol_select():
    StrType = fundamental_type.get("Str")
    ColType = fundamental_type.get("ObjectCollection")

    col = ObjectCollection()
    col.push("apple", Object(StrType, "リンゴ"))
    col.push("gorilla", Object(StrType, "ゴリラ"))
    col.push("trumpet", Object(StrType, "ラッパ"))
    
    om = select_method("gorilla", ColType, reciever=col)
    assert om
    assert om.display() == ("Function", "ObjectCollectionMemberGetter<gorilla>", "")


def test_extend_select():
    StrType = fundamental_type.get("Str")

    cxt = instant_context()
    base = StrType.new_object("基底")
    extobj = cxt.new_object({
        "#extend" : base,
        "apple" : "リンゴ",
        "gorilla" : "ゴリラ",
        "trumpet" : Object(StrType, "ラッパ")
    }, type=StrType)
    exttype = extobj.type
    
    # 特異メソッド
    om = select_method("apple", exttype, reciever=base)
    assert om
    assert om.display() == ("Function", "ImmediateValue<apple>", "")
    assert om._invoke(cxt, base) == "リンゴ" # 元のインスタンスを渡す
    
    om = select_method("gorilla", exttype, reciever=base)
    assert om
    assert om.display() == ("Function", "ImmediateValue<gorilla>", "")
    assert om._invoke(cxt, extobj) == "ゴリラ" # 新しいオブジェクトと元のオブジェクトの値は同じ
    
    om = select_method("trumpet", exttype, reciever=base)
    assert om
    assert om.display() == ("Function", "ImmediateValue<trumpet>", "")
    assert om._invoke(cxt, base) == "ラッパ"
    
    # 元の型のTypeMethod
    dm = select_method("startswith", exttype, reciever=base)
    assert dm
    assert dm.display() == ("TypeMethod", "Str:machaon.core#startswith", "")
    assert dm._invoke(cxt, base, "基") is True

    # Generic TypeMethod
    gm = select_method("=", exttype, reciever=base)
    assert gm
    assert gm.display() == ("TypeMethod", "Generic:machaon.core#identity", "")
    assert gm._invoke(cxt, base) == base


def test_explicit_type_method_select():
    cxt = instant_context()

    sub = cxt.new_object("0xABC", type="Str")
    hex = select_method("Int#from-hex", sub.type, reciever=sub, context=cxt)
    assert hex
    assert hex.display() == ("TypeMethod", "Int:machaon.core#from-hex", "")
    assert hex._invoke(cxt, sub) == 0xABC

    sub = cxt.new_object("1010111", type="Str")
    hex = select_method("Int#from-bin", sub.type, reciever=sub, context=cxt)
    assert hex
    assert hex.display() == ("TypeMethod", "Int:machaon.core#from-bin", "")
    assert hex._invoke(cxt, sub) == 0b1010111

    # コンストラクタ構文
    sub = cxt.new_object("04321", type="Str")
    hex = select_method("oct>>Int", sub.type, reciever=sub, context=cxt)
    assert hex
    assert hex.display() == ("TypeMethod", "Int:machaon.core#from-oct", "")
    assert hex._invoke(cxt, sub) == 0o04321


@pytest.mark.xfail
def test_call_external_method_as_member():
    cxt = instant_context()

    sub = cxt.new_object(0xABC, type="Int")
    hex = select_method("hex", sub.type, reciever=sub, context=cxt)
    assert hex._invoke(cxt, sub) # 型エラー

import re

from machaon.core.invocation import (
    InvocationEntry, BasicInvocation, TypeMethodInvocation, 
    InstanceMethodInvocation, FunctionInvocation, ObjectMemberInvocation, ObjectMemberGetterInvocation,
    Bind1stInvocation, TypeConstructorInvocation,
    instant_context
)
from machaon.core.object import ObjectCollection, Object
from machaon.types.fundamental import fundamental_types
from machaon.core.type import full_qualified_name
from machaon.macatest import run

fundamental_type = fundamental_types()

def plus2mul(x, y):
    return (x + 2) * (y + 2)

def divide(x, y):
    return x / y

def get_first_result(ent):
    return ent.result

#
#
#
def test_function():
    cxt = instant_context()

    inv = FunctionInvocation(plus2mul)
    ent = InvocationEntry(inv, inv.get_action(), (2,3), {})
    assert not ent.is_failed()
    ent.invoke(cxt)
    assert get_first_result(ent)
    assert get_first_result(ent).value == plus2mul(2,3)

    inv = FunctionInvocation(divide, modifier={"REVERSE_ARGS"})
    ent = InvocationEntry(inv, inv.get_action(), (4,2), {})
    ent.invoke(cxt)
    assert get_first_result(ent)
    assert get_first_result(ent).value == 2/4

    
def test_bound_method():
    cxt = instant_context()
    StrType = cxt.get_type("Str")

    # メソッドの呼び出し
    up = InstanceMethodInvocation("upper")
    assert hasattr("abc", "upper")
    assert up.resolve_bound_method("abc") is not None
    assert up.prepare_invoke(cxt, StrType.new_object("abc"))._invokeaction() == "ABC"

    # 値の呼び出し
    string = InstanceMethodInvocation("string")
    m = re.match("[a-zA-Z]", "abc")
    assert string.resolve_bound_method(m) is not None
    assert string.prepare_invoke(cxt, cxt.get_py_type(type(m)).new_object(m))._invokeaction() == "abc"



def test_objectref():    
    StrType = fundamental_type.get("Str")
    cxt = instant_context()

    col = ObjectCollection()
    col.push("apple", Object(StrType, "リンゴ"))
    col.push("gorilla", Object(StrType, "ゴリラ"))
    col.push("trumpet", Object(StrType, "ラッパ"))
    col.push("staff_id", Object(StrType, "社員ID"))

    arg = fundamental_type.get("ObjectCollection").new_object(col)

    inv = ObjectMemberInvocation("apple")
    assert inv.prepare_invoke(cxt, arg)._invokeaction().value == "リンゴ"
    assert isinstance(inv._resolved, ObjectMemberGetterInvocation)
    assert inv.get_min_arity() == 0
    assert inv.get_max_arity() == 0
    assert inv.get_parameter_spec(0) is None
    assert inv._resolved.typename == "Str"
    
    inv = ObjectMemberInvocation("trumpet")
    assert inv.prepare_invoke(cxt, arg)._invokeaction().value == "ラッパ"

    inv = ObjectMemberInvocation("staff_id")
    assert inv.prepare_invoke(cxt, arg)._invokeaction().value == "社員ID"
    
    inv = ObjectMemberInvocation("staff-id")
    assert inv.prepare_invoke(cxt, arg)._invokeaction() is None

    # generic method (Collectionを参照する)
    inv = ObjectMemberInvocation("=")
    assert full_qualified_name(type(inv.prepare_invoke(cxt, arg)._invokeaction())) == "machaon.core.object.Object"
    assert inv.prepare_invoke(cxt, arg)._invokeaction().get_typename() == "ObjectCollection"

    # delegation
    col.set_delegation(Object(StrType, "{math}math.pi"))
    
    inv = ObjectMemberInvocation("gorilla")
    assert inv.prepare_invoke(cxt, arg)._invokeaction().value == "ゴリラ"

    # unary type method
    import math
    inv = ObjectMemberInvocation("dopy")
    assert inv.prepare_invoke(cxt, arg)._invokeaction() == math.pi
    assert isinstance(inv._resolved, TypeMethodInvocation)
    assert inv.get_min_arity() == 0
    assert inv.get_max_arity() == 0
    assert inv.get_parameter_spec(0) is None
    assert inv._resolved.get_method().get_result().get_typename() == "Any"

    # unary instance method
    #inv = ObjectMemberInvocation("iskanji")
    #assert isinstance(inv._resolved, InstanceMethodInvocation)
    
    # unary generic method
    inv = ObjectMemberInvocation("length")
    assert inv.prepare_invoke(cxt, arg)._invokeaction() == len("{math}math.pi")
    assert isinstance(inv._resolved, TypeMethodInvocation)

    # binary type method
    inv = ObjectMemberInvocation("reg-match")
    assert inv.prepare_invoke(cxt, arg, StrType.new_object("[A-z{}]+"))._invokeaction() is True
    assert isinstance(inv._resolved, TypeMethodInvocation)
    assert inv.get_min_arity() == 1
    assert inv.get_max_arity() == 1
    assert inv._resolved.get_method().get_result().get_typename() == "bool"

    # generic method (移譲先のオブジェクトを参照する)
    inv = ObjectMemberInvocation("=")
    assert full_qualified_name(type(inv.prepare_invoke(cxt, arg)._invokeaction())) == "machaon.core.object.Object"
    assert inv.prepare_invoke(cxt, arg)._invokeaction().get_typename() == "Str"

    # generic method (BASIC_RECIEVERで明示的にCollectionを参照する)
    inv = ObjectMemberInvocation("=", {"BASIC_RECIEVER"})
    assert full_qualified_name(type(inv.prepare_invoke(cxt, arg)._invokeaction())) == "machaon.core.object.Object"
    assert inv.prepare_invoke(cxt, arg)._invokeaction().get_typename() == "ObjectCollection"


def test_bind1st():
    StrType = fundamental_type.get("Str")
    cxt = instant_context()
    
    meth = StrType.select_method("reg-match")
    oinv = TypeMethodInvocation(StrType, meth)
    inv = Bind1stInvocation(oinv, "[A-Za-z]+", "str")

    arg = cxt.new_object("aiueo", type="str")
    assert inv.prepare_invoke(cxt, arg)._invokeaction() is True


def test_type_constructor():
    cxt = instant_context()

    # 引数なし
    inv = TypeConstructorInvocation("Complex")
    arg = cxt.new_object("1+3j", type="str")
    assert inv.prepare_invoke(cxt, arg)._invokeaction() == 1+3j

    inv = TypeConstructorInvocation("Int")
    arg = cxt.new_object("456", type="str")
    assert inv.prepare_invoke(cxt, arg)._invokeaction() == 456
    
    inv = TypeConstructorInvocation("Sheet")
    arg1 = cxt.new_object(["0","1","2"], type="Tuple")
    sht = inv.prepare_invoke(cxt, arg1)._invokeaction()
    assert [x.value for x in sht.row_values(0)] == ["0"]

    # 引数あり + TypeDecl + 引数で指定
    inv = TypeConstructorInvocation("Sheet")
    arg1 = cxt.new_object(["1","2","3"], type="Tuple")
    arg2 = cxt.new_object("Int", type="Type")
    arg3 = cxt.new_object("positive")
    arg4 = cxt.new_object("negative")
    sht = inv.prepare_invoke(cxt, arg1, arg2, arg3, arg4)._invokeaction()
    assert [x.value for x in sht.row_values(0)] == [1, -1]
    assert sht.get_current_column_names() == ["positive", "negative"]

    # 引数あり + TypeDecl + TypeDeclで指定
    inv = TypeConstructorInvocation("Sheet[Int](positive,negative)")
    arg1 = cxt.new_object(["4","5","6"], type="Tuple")
    sht = inv.prepare_invoke(cxt, arg1)._invokeaction()
    assert sht.get_current_column_names() == ["positive", "negative"]
    assert [x.value for x in sht.row_values(0)] == [4, -4]

    # 引数あり + TypeDecl + 引数とTypeDeclの両方で指定
    inv = TypeConstructorInvocation("Sheet[Int](positive)")
    arg1 = cxt.new_object(["7","8","9"], type="Tuple")
    arg2 = cxt.new_object("negative") 
    sht = inv.prepare_invoke(cxt, arg1, arg2)._invokeaction()
    assert sht.get_current_column_names() == ["positive", "negative"] # 追加される
    assert [x.value for x in sht.row_values(0)] == [7, -7]

    # 引数あり + TypeInstanceで指定
    t = cxt.instantiate_type("Sheet", "Int", "positive", "negative")
    inv = TypeConstructorInvocation(t)
    arg1 = cxt.new_object(["11","12","13"], type="Tuple")
    sht = inv.prepare_invoke(cxt, arg1)._invokeaction()
    assert [x.value for x in sht.row_values(2)] == [13, -13]
    assert sht.get_current_column_names() == ["positive", "negative"]

    # サブタイプ
    t = cxt.instantiate_type("Int:Hex", "010")
    inv = TypeConstructorInvocation(t)
    arg1 = cxt.new_object("98ABCDEF")
    s = inv.prepare_invoke(cxt, arg1)._invokeaction()
    assert s == 0x98ABCDEF


def test_type_inv_entry_result_type():
    cxt = instant_context()

    # 実行時の型引数がついた型を正しく返す
    t = cxt.instantiate_type("Sheet")
    inv = TypeConstructorInvocation(t)
    arg1 = cxt.new_object(["11","12","13"], type="Tuple")
    arg2 = cxt.new_object("Int", type="Type")
    arg3 = cxt.new_object("positive")
    arg4 = cxt.new_object("negative")
    entry = inv.prepare_invoke(cxt, arg1, arg2, arg3, arg4)
    ret = entry.invoke(cxt)

    assert ret.value.get_current_column_names() == ["positive", "negative"]
    assert [x.value for x in ret.value.row_values(2)] == [13, -13]
    
    assert ret.get_conversion() == "Sheet: Int positive negative" # 型引数が保存されている

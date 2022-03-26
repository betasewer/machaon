import re

from machaon.core.invocation import (
    InvocationEntry, BasicInvocation, TypeMethodInvocation, 
    InstanceMethodInvocation, FunctionInvocation, ObjectMemberInvocation, ObjectMemberGetterInvocation,
    Bind1stInvocation, 
    instant_context
)
from machaon.core.object import ObjectCollection, Object
from machaon.types.fundamental import fundamental_types
from machaon.core.type import full_qualified_name

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
    assert inv.get_result_spec().get_typename() == "Str"
    
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
    assert inv.get_result_spec().get_typename() == "Any"

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
    assert inv.get_result_spec().get_typename() == "bool"

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




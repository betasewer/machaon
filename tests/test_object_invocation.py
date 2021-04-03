from machaon.core.invocation import (
    InvocationEntry, BasicInvocation, TypeMethodInvocation, 
    InstanceMethodInvocation, FunctionInvocation, ObjectMemberInvocation, ObjectMemberGetterInvocation,
    instant_context
)
from machaon.core.object import ObjectValue, ObjectCollection, Object
from machaon.types.fundamental import fundamental_type

def plus2mul(x, y):
    return (x + 2) * (y + 2)

def divide(x, y):
    return x / y

def get_first_result(ent):
    return ent.results[0]

#
#
#
def test_entry():
    inv = FunctionInvocation(plus2mul)
    ent = InvocationEntry(inv, inv.get_action(), (2,3), {})
    assert not ent.is_failed()
    ent.invoke()
    assert get_first_result(ent)
    assert get_first_result(ent)[0] == plus2mul(2,3)

    inv = FunctionInvocation(divide, BasicInvocation.MOD_REVERSE_ARGS)
    ent = InvocationEntry(inv, inv.get_action(), (4,2), {})
    ent.invoke()
    assert get_first_result(ent)
    assert get_first_result(ent)[0] == 2/4


def test_objectref():    
    StrType = fundamental_type.get("Str")
    cxt = instant_context()

    col = ObjectCollection()
    col.push("apple", Object(StrType, "リンゴ"))
    col.push("gorilla", Object(StrType, "ゴリラ"))
    col.push("trumpet", Object(StrType, "ラッパ"))
    col.push("#delegate", Object(StrType, "math.pi"))

    arg = fundamental_type.get("ObjectCollection").new_object(col)

    inv = ObjectMemberInvocation("apple")
    assert inv.prepare_invoke(cxt, arg)._invokeaction().value == "リンゴ"
    assert isinstance(inv._resolved, ObjectMemberGetterInvocation)
    assert inv.get_min_arity() == 0
    assert inv.get_max_arity() == 0
    assert inv.get_parameter_spec(0) is None
    assert len(inv.get_result_specs()) == 1
    assert inv.get_result_specs()[0].get_typename() == "Str"
    
    inv = ObjectMemberInvocation("trumpet")
    assert inv.prepare_invoke(cxt, arg)._invokeaction().value == "ラッパ"

    # delegation

    # unary type method
    import math
    inv = ObjectMemberInvocation("pyvalue")
    assert inv.prepare_invoke(cxt, arg)._invokeaction() == math.pi
    assert isinstance(inv._resolved, TypeMethodInvocation)
    assert inv.get_min_arity() == 0
    assert inv.get_max_arity() == 0
    assert inv.get_parameter_spec(0) is None
    assert len(inv.get_result_specs()) == 1
    assert inv.get_result_specs()[0].get_typename() == "Any"

    # unary instance method
    inv = ObjectMemberInvocation("islower")
    assert inv.prepare_invoke(cxt, arg)._invokeaction() is True
    assert isinstance(inv._resolved, InstanceMethodInvocation)
    
    # unary generic method
    inv = ObjectMemberInvocation("length")
    assert inv.prepare_invoke(cxt, arg)._invokeaction() == len("math.pi")
    assert isinstance(inv._resolved, TypeMethodInvocation)

    # binary type method
    inv = ObjectMemberInvocation("reg-match")
    assert inv.prepare_invoke(cxt, arg, StrType.new_object("[A-z]+"))._invokeaction() is True
    assert isinstance(inv._resolved, TypeMethodInvocation)
    assert inv.get_min_arity() == 1
    assert inv.get_max_arity() == 1
    assert len(inv.get_result_specs()) == 1
    assert inv.get_result_specs()[0].get_typename() == "Bool"

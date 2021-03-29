from machaon.core.invocation import (
    InvocationEntry, BasicInvocation, TypeMethodInvocation, 
    InstanceMethodInvocation, FunctionInvocation, ObjectRefInvocation,
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

    inv = ObjectRefInvocation("apple")
    assert inv.prepare_invoke(cxt, arg)._invokeaction().value == "リンゴ"
    
    inv = ObjectRefInvocation("trumpet")
    assert inv.prepare_invoke(cxt, arg)._invokeaction().value == "ラッパ"

    # type method
    import math
    inv = ObjectRefInvocation("pyvalue")
    assert inv.prepare_invoke(cxt, arg)._invokeaction() == math.pi

    # instance method
    inv = ObjectRefInvocation("islower")
    assert inv.prepare_invoke(cxt, arg)._invokeaction() is True
    
    # generic method
    inv = ObjectRefInvocation("length")
    assert inv.prepare_invoke(cxt, arg)._invokeaction() == len("math.pi")


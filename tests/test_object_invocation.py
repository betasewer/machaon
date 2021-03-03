from machaon.core.invocation import InvocationEntry, BasicInvocation, TypeMethodInvocation, InstanceMethodInvocation, FunctionInvocation, ObjectRefInvocation
from machaon.core.object import ObjectValue

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



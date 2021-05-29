from machaon.core.invocation import (
    InvocationEntry, BasicInvocation, TypeMethodInvocation, 
    InstanceMethodInvocation, FunctionInvocation, ObjectMemberInvocation, ObjectMemberGetterInvocation,
    Bind1stInvocation,
    instant_context
)
from machaon.core.object import ObjectCollection, Object
from machaon.types.fundamental import fundamental_type
from machaon.core.type import full_qualified_name
from machaon.core.method import Method, MethodParameter, MethodResult

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
    inv = FunctionInvocation(plus2mul)
    ent = InvocationEntry(inv, inv.get_action(), (2,3), {})
    assert not ent.is_failed()
    ent.invoke()
    assert get_first_result(ent)
    assert get_first_result(ent) == plus2mul(2,3)

    inv = FunctionInvocation(divide, BasicInvocation.MOD_REVERSE_ARGS)
    ent = InvocationEntry(inv, inv.get_action(), (4,2), {})
    ent.invoke()
    assert get_first_result(ent)
    assert get_first_result(ent) == 2/4

    
def test_type():
    m = Method()


def test_objectref():    
    StrType = fundamental_type.get("Str")
    cxt = instant_context()

    col = ObjectCollection()
    col.push("apple", Object(StrType, "リンゴ"))
    col.push("gorilla", Object(StrType, "ゴリラ"))
    col.push("trumpet", Object(StrType, "ラッパ"))

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

    # generic method (Collectionを参照する)
    inv = ObjectMemberInvocation("=")
    assert full_qualified_name(type(inv.prepare_invoke(cxt, arg)._invokeaction())) == "machaon.core.object.Object"
    assert inv.prepare_invoke(cxt, arg)._invokeaction().get_typename() == "ObjectCollection"

    # delegation
    col.set_delegation(Object(StrType, "math.pi"))
    
    inv = ObjectMemberInvocation("gorilla")
    assert inv.prepare_invoke(cxt, arg)._invokeaction().value == "ゴリラ"

    # unary type method
    import math
    inv = ObjectMemberInvocation("pyvalue")
    assert inv.prepare_invoke(cxt, arg)._invokeaction() == math.pi
    assert isinstance(inv._resolved, TypeMethodInvocation)
    assert inv.get_min_arity() == 0
    assert inv.get_max_arity() == 0
    assert inv.get_parameter_spec(0) is None
    assert inv.get_result_spec().get_typename() == "Any"

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
    assert inv.get_result_spec().get_typename() == "Bool"

    # generic method (移譲先のオブジェクトを参照する)
    inv = ObjectMemberInvocation("=")
    assert full_qualified_name(type(inv.prepare_invoke(cxt, arg)._invokeaction())) == "machaon.core.object.Object"
    assert inv.prepare_invoke(cxt, arg)._invokeaction().get_typename() == "Str"

    # generic method (明示的にCollectionを参照する)
    inv = ObjectMemberInvocation("=", BasicInvocation.MOD_BASE_RECIEVER)
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




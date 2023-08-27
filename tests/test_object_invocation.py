import re

from machaon.core.invocation import (
    InvocationEntry, BasicInvocation, TypeMethodInvocation, 
    InstanceMethodInvocation, FunctionInvocation,
    Bind1stInvocation, TypeConstructorInvocation,
)
from machaon.core.context import instant_context
from machaon.core.object import ObjectCollection, Object
from machaon.types.fundamental import fundamental_types
from machaon.core.symbol import full_qualified_name
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

    inv = FunctionInvocation(divide, modifier={"NEGATE_RESULT"})
    ent = InvocationEntry(inv, inv.get_action(), (4,2), {})
    ent.invoke(cxt)

    
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

    # 引数あり + TypeDecl
    inv = TypeConstructorInvocation("Sheet[Int]")
    arg1 = cxt.new_object(["1","2","3"], type="Tuple")
    arg2 = cxt.new_object("positive")
    arg3 = cxt.new_object("negative")
    sht = inv.prepare_invoke(cxt, arg1, arg2, arg3)._invokeaction()
    assert [x.value for x in sht.row_values(0)] == [1, -1]
    assert sht.get_current_column_names() == ["positive", "negative"]

    # 引数あり + TypeInstanceで指定
    t = cxt.instantiate_type("Sheet", "Int")
    inv = TypeConstructorInvocation(t)
    arg1 = cxt.new_object(["11","12","13"], type="Tuple")
    arg2 = cxt.new_object("positive")
    arg3 = cxt.new_object("negative")
    sht = inv.prepare_invoke(cxt, arg1, arg2, arg3)._invokeaction()
    assert [x.value for x in sht.row_values(2)] == [13, -13]
    assert sht.get_current_column_names() == ["positive", "negative"]



def test_type_inv_entry_result_type():
    cxt = instant_context()

    # 実行時の型引数がついた型を正しく返す
    t = cxt.instantiate_type("Sheet[Int]")
    inv = TypeConstructorInvocation(t)
    arg1 = cxt.new_object(["11","12","13"], type="Tuple")
    arg2 = cxt.new_object("positive")
    arg3 = cxt.new_object("negative")
    entry = inv.prepare_invoke(cxt, arg1, arg2, arg3)
    ret = entry.invoke(cxt)

    assert not ret.is_error()
    assert ret.value.get_current_column_names() == ["positive", "negative"]
    assert [x.value for x in ret.value.row_values(2)] == [13, -13]
    
    assert ret.get_conversion() == "Sheet:machaon.core: Int:machaon.core" # 型引数が保存されている

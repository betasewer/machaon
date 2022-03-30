
from machaon.core.object import Object
from machaon.core.message import (
    MessageEngine, MessageExpression, MemberGetExpression, 
    MessageTokenBuffer, SequentialMessageExpression, 
    parse_function, parse_sequential_function, run_function
)
from machaon.process import TempSpirit
from machaon.types.fundamental import fundamental_types

from machaon.macatest import parse_test, put_instructions, run, parse_instr, message_test

fundamental_type = fundamental_types()


def test_context(*, silent=False):
    from machaon.core.invocation import InvocationContext, instant_context
    
    cxt = instant_context()
    inputs = cxt.input_objects
    inputs.new("this-year", 2020, fundamental_type.get("Int"))    
    inputs.new("this-month", 8, fundamental_type.get("Int")) 
    inputs.new("customer-name", "Yokomizo", fundamental_type.get("Str"))
    if not silent:
        cxt.set_flags("RAISE_ERROR")
    return cxt


#
#
#
def test_parse_function():
    def ltest(s, subject, *rhs):
        from machaon.core.object import ObjectCollection, Object
        from machaon.core.invocation import InvocationContext

        context = InvocationContext(input_objects=ObjectCollection(), type_module=fundamental_type)
        
        engine = MessageEngine(s)
        returned = engine.run_here(context)
        if returned.is_error():
            spi = TempSpirit()
            returned.pprint(spi)
            spi.printout()
        
        assert message_test(s, context, returned.get_typename(), "Function")

        fundamental_type.define({
            "Typename" : "Dog",
            "ValueType" : str,
            "Methods" : [{
                "Name" : "name",
                "Returns" : { "Typename" : "Str" },
                "Action" : lambda x: "lucky"
            },{
                "Name" : "type",
                "Returns" : { "Typename" : "Str" },
                "Action" : lambda x: "Golden Retriever"
            },{
                "Name" : "sex",
                "Returns" : { "Typename" : "Str" },
                "Action" : lambda x: "female"
            },{
                "Name" : "age",
                "Returns" : { "Typename" : "Int" },
                "Action" : lambda x: 3
            }]
        })

        subcontext = context.inherit()
        subj = Object(fundamental_type.get("Dog"), subject)
        fn = returned.value

        lhso = fn.run(subj, subcontext)
        assert message_test(fn.get_expression(), subcontext, lhso, rhs[0])
        
        # 再入
        lhso = fn.run(subj, subcontext)
        assert message_test(fn.get_expression(), subcontext, lhso, rhs[0])

    lucky = {}
    ltest("Function ctor -> @ name == lucky", lucky, True)
    ltest("Function ctor -> @ type startswith: Golden", lucky, True)
    ltest("Function ctor -> @ age * 10", lucky, 30)
    ltest("Function ctor -> (@ age * 5 == 25) || (@ name == lucky)", lucky, True)
    ltest("Function ctor -> 32 * 45 ", lucky, 32 * 45)


#
def test_message_failure():
    # エラーが起きた時点で実行は中止され、エラーオブジェクトが返される
    context = test_context(silent=True)
    r = run_function("2 / 0 + 5 non-exisitent-method 0", None, context)
    assert r.is_error() # zero division error
    assert r.value.get_error_typename() == "ZeroDivisionError"

    context = test_context(silent=True)
    r = run_function("2 * 3 + 5 non-exisitent-method 0", None, context)
    assert r.is_error() # bad method
    assert r.value.get_error_typename() == "BadExpressionError"

    # 関数の実行中のエラー
    context = test_context(silent=True)
    r = run_function("--[10 / 0] do non-existent-method", None, context)
    assert r.is_error() # bad method
    assert r.value.get_error_typename() == "ZeroDivisionError" # do以降は中断される

    #
    # "--[10 / 0] don ifn --[] else --[]" 
    #

#
def test_message_reenter():
    context = test_context(silent=True)
    func = MessageEngine("210 / @")

    # 1.
    r = func.run_function(context.new_object(7), context)
    assert r.value == 30
    # 2.
    r = func.run_function(context.new_object(5), context)
    assert r.value == 42
    # 3. (error)
    r = func.run_function(context.new_object(0), context)
    assert r.is_error()
    # 4. 
    r = func.run_function(context.new_object(2), context)
    assert r.value == 105

    # use cache
    context = test_context()
    func = MessageEngine("210 / @ * 100")

    # 1st
    r = func.run_function(context.new_object(7), context, cache=True)
    assert r.value == 3000
    # 2nd (constructed)
    r = func.run_function(context.new_object(5), context, cache=True)
    assert r.value == 4200
    # 3rd (constructed)
    r = func.run_function(context.new_object(2), context, cache=True)
    assert r.value == 10500


#
def test_message_block():
    context = test_context()

    # 二つ以上のメッセージを含むブロック
    r = run_function("10 * (1 + 2 + 3)", None, context)
    assert r.value == 10 * 6

    r = run_function("'1-2-3' startswith: (1 Str + '-')", None, context)
    assert r.value is True
    
    r = run_function("('1 2 3' + ' ' + '4 5') split as Int reduce +", None, context)
    assert r.value == (1 + 2 + 3 + 4 + 5)

    # ネスト
    r = run_function("100 / ((1 + 2 + 3) * (4 + 5 + 6))", None, context)
    assert r.value == 100 / ((1 + 2 + 3) * (4 + 5 + 6))
    
    # ブロックの完結後に値が続く場合
    r = run_function("title center: (5 * (3 + 1)) =", None, context)
    assert r.value == "title".center(5 * (3 + 1), "=")

    r = run_function("(10 ** (1 + 2)) * 3", None, context)
    assert r.value == 10 ** (1 + 2) * 3


#
def test_message_discard():
    context = test_context()

    r = run_function("10 + 20 . 2 * 4", None, context)
    assert r.value == 2 * 4

    r = run_function(". 10 + 20 . 3 * 5 .", None, context)
    assert r.value == 3 * 5

    r = run_function("100 * (1 + 2 + 3 . 8 =)", None, context)
    assert r.value == 100 * 8

#
def test_message_type_indicator():
    context = test_context()

    r = parse_function("Int :: 1 + 2")
    assert isinstance(r, MessageExpression)
    assert r.get_type_conversion() == "Int"
    assert r.get_expression() == "1 + 2"
    assert r.run(None, context).value == 3
    
    r = parse_function("Str :: name")
    assert isinstance(r, MemberGetExpression)
    assert r.get_type_conversion() == "Str"
    assert r.get_expression() == "name"

    obj = context.new_object({"name" : "waon"})
    assert r.run(obj, context).value == "waon"
    
#
def test_message_sequential_function():
    context = test_context()
    assert not context.is_sequential_invocation()

    fn = parse_sequential_function("1 + 1", context)
    assert isinstance(fn, SequentialMessageExpression)
    assert fn.context.is_sequential_invocation()
    assert fn.context.is_set_raise_error()
    assert not fn.context.is_set_print_step()
    assert fn.get_expression() == "1 + 1"

    # run - no subject
    obj = context.new_object(None)
    r = fn.run(obj) 
    assert isinstance(r, Object)
    assert r.value == 2
    assert r.get_typename() == "Int"

    # call with subject
    fn = parse_sequential_function("@ reduce +", context, "Tuple[Int]")
    r = fn([1,2,3])
    assert isinstance(r, int)
    assert r == 6
    r = fn([4,5,6])
    assert isinstance(r, int)
    assert r == 15

    # call with multiple args
    fn = parse_sequential_function("(@ values) reduce (@ operator)", context, {
            "values": "Tuple[Int]", 
            "operator" : "Str",
        })
    
    assert fn.memberspecs["values"].get_conversion() == "Tuple: Int"
    assert fn.memberspecs["operator"].get_conversion() == "Str"
    r = fn({"values" : [7,8,9], "operator" : "+"})
    assert isinstance(r, int)
    assert r == 7+8+9
    r = fn({"values" : [7,8,9], "operator" : "*"})
    assert r == 7*8*9
    r = fn({"values" : [7,8,9], "operator" : "/"})
    assert r == 7/8/9


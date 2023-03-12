from machaon.core.object import Object
from machaon.process import TempSpirit
from machaon.core.message import MessageEngine
import pytest

def message_test(source, context, lhs, rhs, tester=None):
    if isinstance(lhs, Object):
        if lhs.is_error():
            print("Error occurred on the left side:")
            print("")
            spi = TempSpirit()
            lhs.pprint(spi)
            spi.printout()
            print("--- instructions ----------------")
            print(put_instructions(context))
            print("\n".join([x["message-expression"] for x in context.get_invocations()]))
            return False
        lhs = lhs.value

    if tester is None: 
        def equals(l,r):
            return l == r
        tester = equals

    if not tester(lhs, rhs):
        print("Assertion is failed: {}(({}) => {}, {})".format(tester.__name__, source, lhs, rhs))
        print("")
        print("--- instructions ----------------")
        print(put_instructions(context))
        print("\n".join([x["message-expression"] for x in context.get_invocations()]))
        if context.is_failed():
            error = context.new_invocation_error_object()
            spi = TempSpirit()
            error.pprint(spi)
            spi.printout()
        return False
    
    return True

def put_instructions(cxt, sep='\n'):
    f1 = "{instruction} {options}"
    f2 = "{instruction} {options} > {args}"
    return sep.join(f1.format(**d) if d["args"] is None else f2.format(**d) for d in cxt.get_instructions())

def run(f):
    f()

def runmain(*, fn):
    # 起動前に関数が定義済みでなければならないので、デコレータにはできない
    _h, sep, name = fn.__name__.partition("test_")
    if not sep:
        name = fn.__name__
    pytest.main(["-k", name])

def parse_test(context, s, rhs, *, q=None):
    parser = MessageEngine(s)
    lhso = parser.run_here(context)
    assert message_test(s, context, lhso.value, rhs, q)
    return put_instructions(context, "; ")

def parse_instr(context, s):
    parser = MessageEngine(s)
    parser.run_here(context)
    return put_instructions(context, "; ")

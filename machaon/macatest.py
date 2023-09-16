from machaon.core.object import Object
from machaon.process import TempSpirit
from machaon.core.message import MessageEngine, InternalMessageError
import pytest

def message_test(source, context, lhs, rhs, tester=None):
    if isinstance(lhs, Object):
        if lhs.is_error():
            print("Error occurred on the left side:")
            print("")
            spi = TempSpirit()
            lhs.pprint(spi)
            spi.printout()
            return False
        lhs = lhs.value

    if tester is None: 
        def equals(l,r):
            return l == r
        tester = equals

    if not tester(lhs, rhs):
        print("Assertion is failed: {}(".format(tester.__name__))
        print("    {},".format(lhs))
        print("    {}".format(rhs))
        print(") message: ({})".format(source))
        if context.is_failed():
            error = context.new_invocation_error_object()
            spi = TempSpirit()
            error.pprint(spi)
            spi.printout()
        return False
    
    return True

def put_instructions(cxt, sep='\n'):
    asts = []
    for d in cxt.get_instructions():
        asts.extend(d.display_instructions())
    return sep.join(asts)

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
    try:
        lhso = parser.run_here(context)
    except InternalMessageError:
        raise
    except Exception as e:
        raise InternalMessageError(e, parser, context) from e
    if not message_test(s, context, lhso.value, rhs, q):
        e = AssertionError(lhso.value, rhs)
        raise InternalMessageError(e, parser, context)
    return put_instructions(context, "; ")

def parse_instr(context, s):
    parser = MessageEngine(s)
    parser.run_here(context)
    return put_instructions(context, "; ")

#
#
#
def sequence_equals(l, r):
    if len(l) != len(r):
        return False
    for ll, rr in zip(l, r):
        if ll != rr:
            return False
    return True


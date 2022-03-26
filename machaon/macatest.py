from machaon.core.object import Object
from machaon.process import TempSpirit


def parse_test(parser, context, lhs, rhs, tester=None):
    if isinstance(lhs, Object):
        if lhs.is_error():
            print("Error occurred on the left side:")
            print("")
            spi = TempSpirit()
            lhs.pprint(spi)
            spi.printout()
            print("--- instructions ----------------")
            print(put_instructions(context))
            return False
        lhs = lhs.value

    if tester is None: 
        def equals(l,r):
            return l == r
        tester = equals

    if not tester(lhs, rhs):
        print("Assertion is failed: {}(({}) => {}, {})".format(tester.__name__, parser.source, lhs, rhs))
        print("")
        print("--- instructions ----------------")
        print(put_instructions(context))
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


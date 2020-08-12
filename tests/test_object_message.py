from machaon.object.message import MessageParser

def p(s):
    parser = MessageParser(s)
    parser.parse(log=True)
    return parser.sequence_sexprs()

def run(f):
    f()

#
def test_parse_literals():
    assert p("0 stub-binary 2") == "(0 stub-method-1-1 2)"
    assert p("0 stub-unary") == "(0 stub-method-0-0)"
    assert p("0 stub-binary 1 stub-unary") == "((0 stub-method-1-1 1) stub-method-0-0)"
    assert p("0 stub-binary 1 stub-binary 2 stub-binary 3") == "(((0 stub-method-1-1 1) stub-method-1-1 2) stub-method-1-1 3)"
    assert p("(0 stub-binary 1) stub-binary (2 stub-binary 3)") == "((0 stub-method-1-1 1) stub-method-1-1 (2 stub-method-1-1 3))"
    assert p("((0 stub-binary 1) stub-unary) stub-binary (2 stub-binary 3)") == "(((0 stub-method-1-1 1) stub-method-0-0) stub-method-1-1 (2 stub-method-1-1 3))"
    #
    assert p("0 stub-binary '1)skip'") == "(0 stub-method-1-1 1)skip)"
    assert p('''0 stub-binary "1) 'Beck' & 'Johny' Store "''') == '''(0 stub-method-1-1 1) 'Beck' & 'Johny' Store )'''
    






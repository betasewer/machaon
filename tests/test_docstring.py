from machaon.core.docstring import DocStringParser

def test_oneliner():
    doc = "一行のドキュメント"
    p = DocStringParser(doc, ("Params",))
    assert p.get_string("Document") == "一行のドキュメント"

    doc = "      字下げされた一行のドキュメント"
    p = DocStringParser(doc, ("Params",))
    assert p.get_string("Document") == "字下げされた一行のドキュメント"

def test_methoddoc_ordinal():
    def plus(a, b):
        """
        整数の加算を行う。
        Params:
            a (int): Number A
            b (int): Number B
        Returns:
            int: result.
        """
        return a + b
    
    p = DocStringParser(plus.__doc__, ("Params", "Returns"))
    assert p.detect_indent(plus.__doc__.splitlines(), ignore_first_line=True) == 8
    assert p.get_string("Document") == "整数の加算を行う。"
    assert p.get_lines("Params") == ["    a (int): Number A", "    b (int): Number B"]
    assert p.get_lines("Returns") == ["    int: result."]

def test_moduledoc():
    module_doc = """@module
Using:
    Typename1: module-name
    Typename2: module-name
"""
    
    p = DocStringParser(module_doc, ("Using", ))
    assert p.detect_indent(module_doc, True) == 0
    assert p.get_string("Using") == "    Typename1: module-name\n    Typename2: module-name"

    

    
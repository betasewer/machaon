from machaon.core.docstring import DocStringParser

def test_oneliner():
    doc = "一行のドキュメント"
    p = DocStringParser(doc, ("Params",))
    assert p.get_string("Document") == "一行のドキュメント"

    doc = "      字下げされた一行のドキュメント"
    p = DocStringParser(doc, ("Params",))
    assert p.get_string("Document") == "字下げされた一行のドキュメント"

def test_methoddoc():
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
    assert p.get_string("Document") == "整数の加算を行う。"
    assert p.get_lines("Params") == ["    a (int): Number A", "    b (int): Number B"]
    assert p.get_lines("Returns") == ["    int: result."]

def test_moduledoc():
    class Module:
        """ 
        @Extra-Requirements:
            module-name
        """
    
    p = DocStringParser(Module.__doc__, ("@Extra-Requirements", ))
    assert p.get_string("@Extra-Requirements") == "    module-name"


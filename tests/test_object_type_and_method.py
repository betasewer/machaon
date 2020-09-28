from machaon.object.docstring import DocStringParser
from machaon.object.method import Method
from machaon.object.fundamental import fundamental_type

class SomeValue:
    """
    適当な値オブジェクト
    """
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def perimeter(self):
        """ @method
        外周
        Returns:
            int: 値
        """
        return self.x * 2 + self.y * 2

def test_valuetype_define():
    t = fundamental_type.define(SomeValue)
    assert t.value_type is SomeValue
    assert t.doc == "適当な値オブジェクト"
    assert not t.is_methods_type_bound()

def test_method_docstring():
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
    assert p.get_string("Description") == "整数の加算を行う。"
    assert p.get_lines("Params") == ["    a (int): Number A", "    b (int): Number B"]
    assert p.get_lines("Returns") == ["    int: result."]
    
    m = Method("test")
    m.load_syntax_from_docstring(plus.__doc__, plus)
    assert m.get_param_count() == 2

def test_method_loading():
    newmethod = fundamental_type.Str.select_method("regmatch")
    assert newmethod
    assert newmethod.is_loaded()
    assert newmethod.get_name() == "regmatch"
    assert newmethod.get_param_count() == 2
    assert newmethod.get_result_count() == 1
    assert newmethod.params[0].is_required()
    assert newmethod.params[1].is_required()
    assert newmethod.get_required_argument_min() == 2
    assert newmethod.get_acceptable_argument_max() == 2
    assert newmethod.is_type_bound() is True

    newmethod = fundamental_type.Type.select_method("new")
    assert newmethod
    assert newmethod.is_loaded()
    assert newmethod.get_name() == "new"
    assert newmethod.get_result_count() == 1
    assert newmethod.get_required_argument_min() == 1
    assert newmethod.get_acceptable_argument_max() == 2
    assert newmethod.is_type_bound() is True

    t = fundamental_type.define(SomeValue)
    newmethod = t.select_method("perimeter")
    assert newmethod.get_param_count() == 0
    assert newmethod.get_result_count() == 1
    assert newmethod.get_name() == "perimeter"
    assert not newmethod.is_type_bound()


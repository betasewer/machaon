from machaon.core.docstring import DocStringParser
from machaon.core.method import Method
from machaon.types.fundamental import fundamental_type

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
    
    def modify(self, a, b):
        """ @method
        返り値の定義を省略した場合、レシーバオブジェクトを返す。
        Params:
            a(int): 第一項
            b(int): 第二項
        """
        self.x = a+b
        self.y = a-b


def test_valuetype_define():
    t = fundamental_type.define(SomeValue)
    assert t.value_type is SomeValue
    assert t.doc == "適当な値オブジェクト"
    assert not t.is_methods_type_bound()

def test_method_docstring():
    def plus(a, b):
        """ @method
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
    m.parse_syntax_from_docstring(plus.__doc__, plus)
    assert m.get_param_count() == 2

def test_method_loading():
    Str = fundamental_type.get("Str")
    newmethod = Str.select_method("reg-match")
    assert newmethod
    assert newmethod.is_loaded()
    assert newmethod.get_name() == "reg-match"
    assert newmethod.get_param_count() == 1
    assert newmethod.get_result_count() == 1
    assert newmethod.params[0].is_required()
    assert newmethod.get_required_argument_min() == 1
    assert newmethod.get_acceptable_argument_max() == 1
    assert newmethod.is_type_bound() is True

    Type = fundamental_type.get("Type")
    newmethod = Type.select_method("new")
    assert newmethod
    assert newmethod.is_loaded()
    assert newmethod.get_name() == "new"
    assert newmethod.get_param_count() == 1
    assert newmethod.get_result_count() == 1
    assert newmethod.get_required_argument_min() == 0
    assert newmethod.get_acceptable_argument_max() == 1
    assert newmethod.is_type_bound() is True

    t = fundamental_type.define(SomeValue)
    newmethod = t.select_method("perimeter")
    assert newmethod.get_param_count() == 0
    assert newmethod.get_result_count() == 1
    assert newmethod.get_name() == "perimeter"
    assert not newmethod.is_type_bound()

#
def test_method_alias():
    Str = fundamental_type.get("Str")
    newmethod1 = Str.select_method("location")
    newmethod2 = Str.select_method("loc")
    assert newmethod1 is newmethod2


#
def test_method_return_self():
    t = fundamental_type.define(SomeValue)
    m = t.select_method("modify")
    assert m.get_result_count() == 1
    assert m.get_results()[0].is_return_self()


import pytest

from machaon.core.typedecl import parse_type_declaration, METHODS_BOUND_TYPE_INSTANCE
from machaon.types.fundamental import fundamental_types
from machaon.core.method import Method
from machaon.core.invocation import instant_context

fundamental_type = fundamental_types()

class BasicValue:
    def basic_constant(self):
        """ @method
        定数
        Returns:
            int: 値
        """
        return 100

class SomeValue(BasicValue):
    """ @type
    適当な値オブジェクト
    Params:
        T(Type):
        param1(int):
    """
    def __init__(self, x, y, itemtype=None):
        self.x = x
        self.y = y
        self.itemtype = itemtype
    
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
    
    def constructor(self, value, T, param1):
        """ @meta 
        Params:
            int:
        """
        return SomeValue(value, value*param1, T)
    
    def stringify(self):
        """ @meta noarg """
        return "({},{})".format(self.x, self.y)



def test_valuetype_define():
    t = fundamental_type.define(SomeValue)
    assert t.typename == "SomeValue"
    assert t.value_type is SomeValue
    assert t.doc == "<no document>"
    assert t.get_methods_bound_type() == METHODS_BOUND_TYPE_INSTANCE

    
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
    assert newmethod.params[0].is_required()
    assert newmethod.get_required_argument_min() == 1
    assert newmethod.get_acceptable_argument_max() == 1
    assert newmethod.is_type_bound() is True

    Type = fundamental_type.get("Type")
    newmethod = Type.select_method("new")
    assert newmethod
    assert newmethod.is_loaded()
    assert newmethod.get_name() == "new"
    assert newmethod.get_param_count() == 0
    assert newmethod.get_required_argument_min() == 0
    assert newmethod.get_acceptable_argument_max() == 0
    assert newmethod.is_type_bound() is True

    t = fundamental_type.define(SomeValue)
    newmethod = t.select_method("perimeter")
    assert newmethod.get_param_count() == 0
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
    assert m.get_result().is_return_self()

#
def test_meta_method():
    cxt = instant_context()
    t = cxt.type_module.load_definition(SomeValue).load_type()

    v = t.instantiate(cxt, [], [2]).construct(cxt, 3)
    assert isinstance(v, SomeValue)
    assert v.x == 3
    assert v.y == 6
    assert v.itemtype is None

    decl = parse_type_declaration("SomeValue[Str](42)")
    t = decl.instance(cxt)
    v = t.construct(cxt, 11)
    assert isinstance(v, SomeValue)
    assert v.x == 11
    assert v.y == 11 * 42
    assert v.itemtype is cxt.get_type("Str")

    v = t.stringify_value(SomeValue(1,2))
    assert v == "(1,2)"


@pytest.mark.xfail
def test_constructor_typecheck_fail():
    cxt = instant_context()
    p = cxt.get_type("Function")
    p.construct(cxt, 12345) # TypeConversionError

def test_enum_method():
    t = fundamental_type.define(SomeValue)
    n = []
    for names, method in t.enum_methods():
        if isinstance(method, Exception):
            continue
        n.extend(names)
    # 定義順、派生→基底クラス順
    assert n == [
        "perimeter",
        "modify",
        "basic-constant"
    ]

#
def test_load_from_dict():
    # Dog型を定義
    cxt = instant_context()
    Dog = cxt.define_type({
        "Typename" : "Dog",
        "Methods" : [{
            "Name" : "name",
            "Returns" : { "Typename" : "Str" },
            "Action" : lambda x: "gabliel"
        },{
            "Name" : "type",
            "Returns" : { "Typename" : "Str" },
            "Action" : lambda x: "Shiba"
        },{
            "Name" : "sex",
            "Returns" : { "Typename" : "Str" },
            "Action" : lambda x: "male"
        },{
            "Name" : "age",
            "Returns" : { "Typename" : "Int" },
            "Action" : lambda x: 2
        }]
    })
    m = Dog.select_method("name")
    assert m.is_loaded()
    assert m.get_name() == "name"
    assert m.get_param_count() == 0
    assert m.get_required_argument_min() == 0
    assert m.get_acceptable_argument_max() == 0
    r = m.get_result()
    assert r is not None
    assert r.get_typename() == "Str"
    assert r.get_typedecl().to_string() == "Str"


def test_load_from_docstring():
    # 終わりのコロンが無い
    doc = """@method
    Returns:
        Int
    Params:
        p1 (Float)
        p2 (Complex)
    """
    m = Method()
    m.parse_syntax_from_docstring(doc)
    assert m.get_required_argument_min() == 2
    assert m.get_acceptable_argument_max() == 2
    assert m.get_param_count() == 2
    assert m.get_param(0).get_name() == "p1"
    assert m.get_param(0).get_typename() == "Float"
    assert m.get_param(1).get_name() == "p2"
    assert m.get_param(1).get_typename() == "Complex"
    assert m.get_result() is not None
    assert m.get_result().get_typename() == "Int"
    
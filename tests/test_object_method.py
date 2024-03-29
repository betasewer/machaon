import pytest

from machaon.core.type.alltype import (
    TypeDecl, TypeInstance, instantiate_type, parse_type_declaration, METHODS_BOUND_TYPE_INSTANCE
)
from machaon.types.fundamental import fundamental_types
from machaon.core.method import RETURN_SELF, Method, MethodResult, METHOD_LOADED
from machaon.core.context import instant_context

from machaon.macatest import run

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
    
    def constructor(self, T, x, y):
        """ @meta 
        Params:
            x(int):
            y(int):
        """
        return SomeValue(x, y, T)
    
    def stringify(self, T):
        """ @meta noarg """
        return "({},{})".format(self.x, self.y)

def test_define():
    cxt = instant_context()
    t = cxt.type_module.select(SomeValue)
    
    print(", ".join([x.get_conversion() for _, x in cxt.type_module.getall()]))

    t2 = cxt.get_type("SomeValue")
    assert t.get_conversion() == t2.get_conversion()
    assert len(t2.get_type_params()) == 1
    assert t is t2


def test_valuetype_define():
    t = fundamental_type.select(SomeValue)
    assert t.typename == "SomeValue"
    assert t.value_type is SomeValue
    assert t.doc == "適当な値オブジェクト"
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
    assert newmethod.is_type_value_bound() is True

    Type = fundamental_type.get("Type")
    newmethod = Type.select_method("new")
    assert newmethod
    assert newmethod.is_loaded()
    assert newmethod.get_name() == "new"
    assert newmethod.get_param_count() == 1
    assert newmethod.get_required_argument_min() == 0
    assert newmethod.get_acceptable_argument_max() is None
    assert newmethod.is_type_value_bound() is True

    t = fundamental_type.select(SomeValue)
    newmethod = t.select_method("perimeter")
    assert newmethod.get_param_count() == 0
    assert newmethod.get_name() == "perimeter"
    assert not newmethod.is_type_value_bound()

#
def test_method_alias():
    Str = fundamental_type.get("Str")
    newmethod1 = Str.select_method("location")
    newmethod2 = Str.select_method("loc")
    assert newmethod1 is newmethod2


#
def test_method_return_self():
    cxt = instant_context()
    t = cxt.select_type(SomeValue)
    m = t.select_method("modify")
    assert m.get_result().is_return_self()
    
    from machaon.core.message import Message
    rec = cxt.new_object(SomeValue(10, 20))
    msg = Message(rec)
    rettype, ret = m.get_result().make_result_value(cxt, None, message=msg)
    assert rettype.get_conversion() == "SomeValue:tests.test_object_method.SomeValue"
    assert isinstance(ret, SomeValue)
    assert ret.x == 10
    assert ret.y == 20


#
def test_meta_method():
    cxt = instant_context()
    t = cxt.type_module.select(SomeValue)

    m = t.get_constructor()
    assert m is not None
    assert m.is_loaded()
    assert m.get_param(-1).get_typename() == "Int"
    assert m.get_param(-1).get_name() == "x"
    assert m.get_param(0).get_name() == "y"

    ps = t.get_type_params()
    assert len(ps) == 1
    assert ps[0].get_typename() == "Type"
    assert ps[0].get_name() == "T"

    ti = t.instantiate(cxt, ["Any"])
    assert len(ti.get_args()) == 1
    assert ti.get_args()[0].get_typename() == "Any"

    meta = ti.get_typedef().get_meta_method("constructor")
    ca = meta.prepare_invoke_args([10, 15], selftype=ti.get_typedef(), context=cxt, typeargs=ti.get_args())
    assert len(ca) == 4
    assert ca[0] is SomeValue 
    assert ca[1].get_typename() == "Any"
    assert ca[2] == 10
    assert ca[3] == 15

    from machaon.core.type.instance import TypeAny

    v = ti.construct(cxt, 3, 6)
    assert isinstance(v, SomeValue)
    assert v.x == 3
    assert v.y == 6
    assert isinstance(v.itemtype, TypeAny)

    t = instantiate_type("SomeValue[Str]", cxt)
    assert isinstance(t, TypeInstance)
    assert t.get_args()[0].get_conversion() == "Str:machaon.core"
    v = t.construct(cxt, 11, 22)
    assert isinstance(v, SomeValue)
    assert v.x == 11
    assert v.y == 22
    assert v.itemtype is cxt.get_type("Str")

    v = t.stringify_value(SomeValue(1,2))
    assert v == "(1,2)"


@pytest.mark.xfail
def test_constructor_typecheck_fail():
    cxt = instant_context()
    p = cxt.get_type("Function")
    p.construct(cxt, 12345) # TypeConversionError

def test_enum_method():
    t = fundamental_type.select(SomeValue)
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
    Dog = cxt.select_type({
        "DescriberName" : "instant",
        "Typename" : "Dog",
        "ValueType" : str, # ダミー型
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
    m = Method(flags=METHOD_LOADED)
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



def test_result_value():
    cxt = instant_context()

    # 型指定
    r = MethodResult(parse_type_declaration("Int"))
    assert r.typename == "Int"
    assert not r.is_already_instantiated()
    assert not r.is_type_to_be_deduced()

    assert r.make_result_value(cxt, "9")[-1] == 9
    assert r.make_result_value(cxt, 11)[-1] == 11

    # 推測
    r = MethodResult(parse_type_declaration("Any"))
    assert r.typename == "Any"
    assert not r.is_already_instantiated()
    assert r.is_type_to_be_deduced()

    assert r.make_result_value(cxt, "9")[0].get_conversion() == "Str:machaon.core"
    assert r.make_result_value(cxt, "9")[-1] == "9"
    assert r.make_result_value(cxt, 11)[0].get_conversion() == "Int:machaon.core"
    assert r.make_result_value(cxt, 11)[-1] == 11

    # 型インスタンス
    '''
    r = MethodResult(parse_type_declaration("Int:Hex", cxt, "08"))
    assert r.typename == "Int:Hex: 08"
    assert r.is_already_instantiated()
    assert not r.is_type_to_be_deduced()
    
    assert r.make_result_value(cxt, "FF")[0].get_conversion() == "Int:Hex: 08"
    assert r.make_result_value(cxt, "FF")[-1] == 0xFF
    '''

    # レシーバオブジェクト
    r = MethodResult(special=RETURN_SELF)
    assert not r.is_already_instantiated()
    assert r.is_type_to_be_deduced()

    from machaon.core.message import Message
    rec = cxt.new_object(2000)
    msg = Message(rec)
    assert r.make_result_value(cxt, None, message=msg)[0].get_conversion() == "Int:machaon.core"
    assert r.make_result_value(cxt, None, message=msg)[-1] == 2000

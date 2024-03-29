import pytest

from machaon.core.type.alltype import (
    ModuleTypeDecl, TypeInstance, parse_type_declaration, TypeUnion, 
    PythonType, ExtendedType, get_type_extension_loader, Type
)
from machaon.core.invocation import InstanceMethodInvocation, FunctionInvocation
from machaon.core.context import instant_context

TypeDecl = ModuleTypeDecl
parse_ = parse_type_declaration

def reflectparse(s):
    d = parse_type_declaration(s)
    assert s == d.to_string()

def equalparse(s,r):
    d = parse_type_declaration(s)
    assert d.to_string() == r

def test_decl_disp():
    assert TypeDecl("Int").to_string() == "Int"
    assert TypeDecl("List", [TypeDecl("Str")]).to_string() == "List[Str]"
    assert TypeDecl("Sheet", [TypeDecl("Room")]).to_string() == "Sheet[Room]"
    assert TypeDecl("Hotel", [TypeDecl("Room"), TypeDecl("Sheet", [TypeDecl("Room")]), TypeDecl("name")]).to_string() == "Hotel[Room,Sheet[Room],name]"
    assert TypeDecl("Sheet", [TypeDecl("sub"), TypeDecl("mul")]).to_string() == "Sheet[sub,mul]"
    assert TypeDecl("Sheet", []).to_string() == "Sheet"

def test_decl_parse():
    reflectparse("Int")
    reflectparse("Tuple[Str]")
    reflectparse("Sheet[Room]")
    reflectparse("Hotel[Sheet[Room]]")
    equalparse("Sheet[]", "Sheet")
    reflectparse("Generator[Int,None,None]")
    reflectparse("Generator[Sheet[Room],Sheet[Room],Sheet[Room]]")
    reflectparse("Tuple[Tuple[Tuple[Int]]]")

    equalparse("Sheet[Int|Str]", "Sheet[Union[Int,Str]]")
    equalparse("Tuple[Int|Str]|Sheet[Int|Str]", "Union[Tuple[Union[Int,Str]],Sheet[Union[Int,Str]]]")

    # 空白は削除される
    equalparse("Sheet[Room, Int, Float]", "Sheet[Room,Int,Float]")
    
    reflectparse("Sheet[Room,'What','Is-This']")
    reflectparse("Sheet[Room,Wh$at,Im&&ena]") # 型名に使用できない文字が含まれる


@pytest.mark.xfail
def test_decl_fail_1():
    # かっこが足りない
    parse_type_declaration("List[List[List[]]")

@pytest.mark.xfail
def test_decl_fail_2():
    # かっこが多い
    parse_type_declaration("List[List[List]]]")

@pytest.mark.xfail
def test_decl_fail_3():
    # コンストラクタ引数が型引数よりも前にある
    parse_type_declaration("Sheet(name, type)[Int]")

#
#
#
def test_decl_instance():
    cxt = instant_context()

    # 引数なし
    assert parse_("Int").instance(cxt) is cxt.get_type("Int")
    assert isinstance(cxt.get_type("Sheet"), Type)
    assert isinstance(parse_("Sheet").instance(cxt), TypeInstance) # Anyが束縛される
    
    # declで束縛
    d = parse_("Sheet[Int]").instance(cxt)
    assert isinstance(d, TypeInstance)
    assert d is not cxt.get_type("Sheet")
    assert d.get_typedef() is cxt.get_type("Sheet")
    assert len(d.get_args()) == 1
    assert d.get_args()[0] is cxt.get_type("Int")
    assert d.get_typename() == "Sheet"
    assert d.get_conversion() == "Sheet:machaon.core: Int:machaon.core"
    
    # declとinstanceで束縛
    d = parse_("Sheet[]").instance(cxt, ["Int"])
    assert len(d.get_args()) == 1
    assert d.get_args()[0] is cxt.get_type("Int")
    assert d.get_conversion() == "Sheet:machaon.core: Int:machaon.core" 
    
    # default
    from machaon.core.type.instance import TypeAny
    d = parse_("Sheet[]").instance(cxt)
    assert len(d.get_args()) == 1
    assert isinstance(d.get_args()[0], TypeAny)
    assert d.get_conversion() == "Sheet:machaon.core: Any" 

    # Any
    t = parse_("Any").instance(cxt)
    assert t
    assert isinstance(t, TypeAny)

    

def test_decl_instantiate_args():
    cxt = instant_context()
    t = cxt.get_type("Sheet")

    d = parse_type_declaration("Sheet[Str]")
    args = d.instance(cxt).get_args()
    assert len(args) == 1
    assert args[0].get_conversion() == "Str:machaon.core"
    
    d = parse_type_declaration("Sheet[]")
    args = d.instance(cxt).get_args()
    assert len(args) == 1
    assert args[0].get_conversion() == "Any"

def test_decl_syntax_check():
    cxt = instant_context()
    def instance(expr):
        decl = parse_type_declaration(expr)
        return decl.instance(cxt)

    t = instance("Int")
    assert isinstance(t, Type)
    assert t.check_value_type(int)
    assert not t.check_value_type(str)

    t = instance("Int | Str")
    assert isinstance(t, TypeUnion)
    assert t.check_value_type(int)
    assert t.check_value_type(str)
    assert not t.check_value_type(float)
    
    # 小文字のmachaonの型
    t = instance("str")
    assert isinstance(t, Type)
    assert t.get_value_type() is str
    
    t = instance("builtins.bytes")
    assert isinstance(t, PythonType)
    assert t.check_value_type(bytes)
    assert not t.check_value_type(str)



#
# PythonType
#
class PyType:
    """
    classmethod, instance bound -> method
    staticmethod -> function

    function (staticmethod, classmethod) -> FunctionInvocation
    value (type bound) -> FunctionInvocation
    value (instance bound) -> InstanceMethodInvocation
    method -> InstanceMethodInvocation 
    """
    def __init__(self):
        self.ivalue = 200
        self._value = 100

    def method2(self, x, y):
        """ m x y """
        return x * y * self._value

    def method0(self):
        """ m """
        return self._value

    """ - """
    const = 10000

    @property
    def prop(self):
        """ m """
        return self._value

    @classmethod
    def clsmethod2(cls, x, y):
        """ - """
        return cls.const - x - y

    @staticmethod
    def stmethod2(x, y):
        """ - """
        return x + y

    
def test_enummethods_pythontype():
    cxt = instant_context()

    t = PythonType(PyType, "pytype")
    
    assert t.get_typename() == "pytype"
    assert t.get_conversion() == "pytype"
    assert t.is_selectable_instance_method()

    methods = list(t.enum_methods())

    instance = PyType()

    # メソッド
    name, m = methods[0]
    assert name == ["method2"]
    assert m.get_param_count() == 2
    assert m.get_param(0).typename == "Any"
    assert isinstance(m.make_invocation(), InstanceMethodInvocation)
    assert m.make_invocation().get_min_arity() == 2
    assert m.make_invocation().get_max_arity() == 2
    assert m.make_invocation()._invoke(cxt, instance, 2, 3) == instance.method2(2, 3)
    assert m.get_signature() == "@ Any Any -> Any"
    
    name, m = methods[1]
    assert name == ["method0"]
    assert m.get_param_count() == 0
    assert isinstance(m.make_invocation(), InstanceMethodInvocation)
    assert m.make_invocation().get_min_arity() == 0
    assert m.make_invocation().get_max_arity() == 0
    assert m.make_invocation()._invoke(cxt, instance) == instance.method0()
    assert m.get_signature() == "@ -> Any"
    
    # classmethod
    name, m = methods[2]
    assert name == ["clsmethod2"]
    assert m.get_param_count() == 2
    assert m.get_param(0).typename == "Any"
    assert isinstance(m.make_invocation(), FunctionInvocation)
    assert m.make_invocation().get_min_arity() == 2
    assert m.make_invocation().get_max_arity() == 2
    assert m.make_invocation()._invoke(cxt, 4, 5) == PyType.clsmethod2(4, 5)
    assert m.get_signature() == "@ Any Any -> Any"
    
    # staticmethod
    name, m = methods[3]
    assert name == ["stmethod2"]
    assert m.get_param_count() == 2
    assert m.get_param(0).typename == "Any"
    assert isinstance(m.make_invocation(), FunctionInvocation)
    assert m.make_invocation().get_min_arity() == 2
    assert m.make_invocation().get_max_arity() == 2
    assert m.make_invocation()._invoke(cxt, 4, 5) == PyType.stmethod2(4, 5)
    assert m.get_signature() == "@ Any Any -> Any"
    
    # class value
    name, m = methods[4]
    assert name == ["const"]
    assert m.get_param_count() == 0
    assert isinstance(m.make_invocation(), InstanceMethodInvocation)
    assert m.make_invocation().get_min_arity() == 0
    assert m.make_invocation().get_max_arity() == 0
    assert m.make_invocation()._invoke(cxt, instance) == PyType.const
    assert m.get_signature() == "@ -> Int"
    
    # property
    name, m = methods[5]
    assert name == ["prop"]
    assert m.get_param_count() == 0
    assert isinstance(m.make_invocation(), InstanceMethodInvocation)
    assert m.make_invocation()._invoke(cxt, instance) == instance.prop
    assert m.get_signature() == "@ -> Any"
    
    # instance value
    inv = InstanceMethodInvocation("ivalue")
    assert inv.get_min_arity() == 0
    assert inv.get_max_arity() == 0xFFFF
    assert inv._invoke(cxt, instance) == instance.ivalue

def test_selectmethod_pythontype():
    cxt = instant_context()

    t = PythonType(PyType, "pytype")

    instance = PyType()

    m = t.select_method("method2")
    assert m is not None
    assert m.get_name() == "method2"
    assert m.get_param_count() == 2
    assert m.make_invocation()._invoke(cxt, instance, 2, 3) == instance.method2(2, 3)

    m = t.select_method("clsmethod2")
    assert m is not None
    assert m.get_name() == "clsmethod2"
    assert m.get_param_count() == 2
    assert m.make_invocation()._invoke(cxt, 2, 3) == PyType.clsmethod2(2, 3)

    m = t.select_method("prop")
    assert m is not None
    assert m.get_name() == "prop"
    assert m.get_param_count() == 0
    assert m.make_invocation()._invoke(cxt, instance) == instance.prop


class PySlotsType:
    """ 
    __dict__が無いケース：
        __slots__を使う場合や、ビルトインクラスなど
    """
    __slots__ = ("first", "second")

    def __init__(self) -> None:
        self.first = 1
        self.second = 2

    def method0(self):
        return 32

    @property
    def prop(self):
        """ m """
        return self.first

    @classmethod
    def clsmethod2(cls, x, y):
        """ - """
        return x - y

    @staticmethod
    def stmethod2(x, y):
        """ - """
        return x + y

    const = 10000


def test_enummethods_pythontype_2():
    cxt = instant_context()

    t = PythonType(PySlotsType, "pytype")
    
    methods = list(t.enum_methods())

    instance = PySlotsType()

    # メソッド
    name, m = methods[0]
    assert name == ["method0"]
    assert m.get_param_count() == 0
    assert isinstance(m.make_invocation(), InstanceMethodInvocation)
    assert m.make_invocation().get_min_arity() == 0
    assert m.make_invocation().get_max_arity() == 0
    assert m.make_invocation()._invoke(cxt, instance) == instance.method0()
    
    # classmethod
    name, m = methods[1]
    assert name == ["clsmethod2"]
    assert m.get_param_count() == 2
    assert m.get_param(0).typename == "Any"
    assert isinstance(m.make_invocation(), FunctionInvocation)
    assert m.make_invocation().get_min_arity() == 2
    assert m.make_invocation().get_max_arity() == 2
    assert m.make_invocation()._invoke(cxt, 4, 5) == PySlotsType.clsmethod2(4, 5)
    
    # staticmethod
    name, m = methods[2]
    assert name == ["stmethod2"]
    assert m.get_param_count() == 2
    assert m.get_param(0).typename == "Any"
    assert isinstance(m.make_invocation(), FunctionInvocation)
    assert m.make_invocation().get_min_arity() == 2
    assert m.make_invocation().get_max_arity() == 2
    assert m.make_invocation()._invoke(cxt, 4, 5) == PySlotsType.stmethod2(4, 5)
    
    # class value
    name, m = methods[3]
    assert name == ["const"]
    assert m.get_param_count() == 0
    assert isinstance(m.make_invocation(), InstanceMethodInvocation)
    assert m.make_invocation().get_min_arity() == 0
    assert m.make_invocation().get_max_arity() == 0
    assert m.make_invocation()._invoke(cxt, instance) == PyType.const
    
    # property
    name, m = methods[4]
    assert name == ["first"]
    assert m.get_param_count() == 0
    assert isinstance(m.make_invocation(), InstanceMethodInvocation)
    assert m.make_invocation()._invoke(cxt, instance) == instance.first

    # property
    name, m = methods[5]
    assert name == ["prop"]
    assert m.get_param_count() == 0
    assert isinstance(m.make_invocation(), InstanceMethodInvocation)
    assert m.make_invocation()._invoke(cxt, instance) == instance.prop
    
    # property
    name, m = methods[6]
    assert name == ["second"]
    assert m.get_param_count() == 0
    assert isinstance(m.make_invocation(), InstanceMethodInvocation)
    assert m.make_invocation()._invoke(cxt, instance) == instance.second


def test_extension():
    cxt = instant_context()

    basic = cxt.new_object({
        "#extend" : "АБВГДЕ",
        "language" : "cyrillic"
    })
    exttype = basic.type

    assert isinstance(exttype, ExtendedType)
    assert exttype.get_basetype() is cxt.get_type("Str")

    # 拡張メソッドの呼び出し
    assert exttype.is_selectable_method("language")
    assert exttype.select_method("language")
    mth = exttype.select_method("language")
    assert mth.get_name() == "language"
    assert mth.get_param_count() == 0
    assert mth.get_result().get_typename() == "Str"
    
    inv = mth.make_invocation()
    assert inv._invoke(cxt, basic.value) == "cyrillic"

    # 元の型と同じ振る舞い
    assert exttype.get_typename() == "Str"
    assert exttype.get_value_type() is str
    assert exttype.get_typedef() is cxt.get_type("Str")
    assert exttype.construct(cxt, 123) == "123"
    assert exttype.stringify_value(basic.value) == "АБВГДЕ"

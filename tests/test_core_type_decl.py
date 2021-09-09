import pytest
from machaon.core.typedecl import TypeDecl, parse_type_declaration
from machaon.core.invocation import instant_context

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
    assert TypeDecl("Sheet", [TypeDecl("Room")], ["number", "type"]).to_string() == "Sheet[Room](number,type)"
    assert TypeDecl("Hotel", [TypeDecl("Sheet", [TypeDecl("Room")], ["number", "type"])], ["name"]).to_string() == "Hotel[Sheet[Room](number,type)](name)"
    assert TypeDecl("Sheet", [], ["type"]).to_string() == "Sheet[](type)"

def test_decl_parse():
    reflectparse("Int")
    reflectparse("Tuple[Str]")
    reflectparse("Sheet[Room](number,type)")
    reflectparse("Hotel[Sheet[Room](number,type)](name)")
    reflectparse("Sheet[](type)")
    reflectparse("Generator[Int,None,None]")
    reflectparse("Generator[Sheet[Room](number,type),Sheet[Room](number,type),Sheet[Room](number,type)]")
    reflectparse("Tuple[Tuple[Tuple[Int]]]")

    equalparse("Sheet[Int|Str]", "Sheet[Union[Int,Str]]")
    equalparse("Tuple[Int|Str]|Sheet[Int|Str]", "Union[Tuple[Union[Int,Str]],Sheet[Union[Int,Str]]]")


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
    assert parse_("Int").instance(cxt) is cxt.get_type("Int")
    assert parse_("Sheet").instance(cxt) is cxt.get_type("Sheet")
    
    d = parse_("Sheet[Int](@, length)").instance(cxt)
    assert d is not cxt.get_type("Sheet")
    assert d.get_typedef() is cxt.get_type("Sheet")
    assert d.typeargs[0] is cxt.get_type("Int")
    assert d.ctorargs[0] == "@"
    assert d.ctorargs[1] == "length"
    assert d.get_typename() == "Sheet"
    assert d.get_conversion() == "Sheet[Int](@, length)"
    

def test_decl_check():
    #checkvaltype("Int", int)
    #checkvaltype("Int|Str", int, str)
    pass

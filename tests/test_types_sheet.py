import pytest
import operator
from machaon.core.type import TypeModule
from machaon.core.object import ObjectCollection, Object
from machaon.core.invocation import InvocationContext, instant_context
from machaon.core.message import MessageEngine
from machaon.core.sort import ValueWrapper
from machaon.types.sheet import Sheet, make_data_columns, DataMemberColumn, DataItemItselfColumn

class Employee():
    """
    """
    def __init__(self, name, postcode="000-0000"):
        self._name = name
        self._postcode = postcode

    def name(self):
        """ @method
        名前
        Returns: str
        """
        return self._name

    def tall(self):
        """ @method
        身長
        Returns: int
        """
        return len(self._name)
    
    def postcode(self):
        """ @method
        郵便番号
        Returns: str
        """
        return self._postcode


@pytest.fixture
def objectdesk():
    typemod = TypeModule()
    typemod.add_fundamental_types()
    typemod.definition(typename="Employee")(Employee)
    desk = InvocationContext(input_objects=ObjectCollection(), type_module=typemod)
    return desk

#
#
#
def test_column(objectdesk):
    employee = objectdesk.get_type("Employee")
    view = Sheet([
            Employee(x,y) for (x,y) in [("ken", "332-0011"), ("ren", "224-0022"), ("shin", "113-0033")]
        ], 
        employee,
        objectdesk,
        ["name", "postcode"]
    )

    assert view.get_item_type() is employee
    assert view.get_top_column_name() == "name"
    assert view.get_link_column_name() is None

    view.add_column("tall")
    assert view.get_current_column_names() == ["name", "postcode", "tall"]

    namecol = view.get_current_columns()[0]
    assert namecol.get_name() == "name"
    assert namecol.get_type(objectdesk, None) is objectdesk.get_type("Str")

    # カラムの値を得る
    subject = Object(employee, view.items[0])
    assert namecol.get_function()
    assert namecol.get_function().get_expression() == "name"
    namecol.eval(subject, objectdesk) == "ken"

    subject = Object(employee, view.items[2])
    assert namecol.eval(subject, objectdesk) == "shin"

    subject = Object(employee, view.items[1])
    assert namecol.eval(subject, objectdesk) == "ren"

#
#
#
def test_create_no_mod(objectdesk):
    datas = [Employee(x) for x in ("ken", "yuuji", "kokons")]
    employee = objectdesk.get_type("Employee")

    view = Sheet(datas, employee, objectdesk, ["name"])
    
    assert view.count() == 3
    assert len(view.get_current_columns()) == 1
    assert view.get_current_columns()[0].get_name() == "name"

    assert view.rows == [(0, ["ken"]), (1, ["yuuji"]), (2, ["kokons"])]

    assert view.rows_to_string_table(objectdesk) == [(0, ["ken"]), (1, ["yuuji"]), (2, ["kokons"])]
    view.select(1)
    assert view.selection_index() == 1
    assert view.get_row(0) == ["ken"]
    assert view.get_row(view.selection_index()) == ["yuuji"]

#
#
#
def test_expand_view(objectdesk):
    items = [Employee(x, y) for (x,y) in (("ken","111-1111"), ("yuuji","222-2222"), ("kokons","333-3333"))]
    employee = objectdesk.get_type("Employee")

    view = Sheet(items, employee, objectdesk, ["name", "postcode"])
    view.view_append(objectdesk, ["tall"])

    assert view.get_current_column_names() == ["name", "postcode", "tall"]
    assert view.count() == 3
    assert view.get_row(0) == ["ken", "111-1111", 3]



@pytest.mark.skip()
def test_create_filtered(objectdesk):
    datas = [Employee(x) for x in ("ken", "ishulalmandij", "yuuji")]
    employee = objectdesk.get_type("Employee")

    f = Function("(ke in @name) || (@tall == 5)")
    bits = [f.run(Object(objectdesk.get_type(Employee), x), objectdesk) for x in datas]
    assert bits == [True, False, True]
    
    # TODO: get_lambda_argument_namesの実装
    view = Sheet(datas, employee).view(objectdesk, "table", predicate=f)
    assert view.count() == 2
    assert view.rows_to_string_table(objectdesk) == ([(0, ["ken","3"]), (2, ["yuuji","5"])], [5, 1])


@pytest.mark.skip()
def test_filtered_manytimes(objectdesk):
    datas = [Employee(x) for x in ("ken", "ishulalmandij", "yuuji")]
    
    view = parse_new_setview(objectdesk, datas, "name postcode")
    view.select(1)
    assert view.count() == 3
    assert view.get_row(view.selection()) == ["ishulalmandij", "000-0000"]
    
    view2 = parse_setview(objectdesk, view, "/where @tall < 10")
    assert view2.count() == 2
    assert view2.rows_to_string_table() == ([(0, ["ken","000-0000", "3"]), (2, ["yuuji", "000-0000", "5"])], [5, 8, 1])

    view3 = parse_setview(objectdesk, view2, "/where @name == ken")
    assert view3.count() == 1
    assert view3.rows_to_string_table() == ([(0, ["ken","000-0000", "3"])], [3, 8, 1])

    view4 = parse_setview(objectdesk, view3, "/where @postcode == 777-7777")
    assert view4.count() == 0
    
    view5 = parse_setview(objectdesk, view4, "/where @name == batman")
    assert view5.count() == 0

#
#
#
@pytest.mark.skip()
def test_sorted(objectdesk):
    datas = [Employee(x) for x in ("ken", "ishulalmandij", "yuuji")]
    
    view = parse_new_setview(objectdesk, datas, "name")
    view.select(1)
    assert view.selection_row() == ["ishulalmandij"]

    view2 = parse_setview(objectdesk, view, "/sortby name")
    assert view2.rows_to_string_table() == ([(1, ["ishulalmandij"]), (0, ["ken"]), (2, ["yuuji"])], [13])
    assert view2.selection_row() == ["ishulalmandij"]
    
    view3 = parse_setview(objectdesk, view, "/sortby !tall")
    assert view3.rows_to_string_table() == ([(1, ["ishulalmandij", '13']), (2, ["yuuji", "5"]), (0, ["ken", "3"])], [13, 2])
    assert view3.selection_row() == ["ishulalmandij", 13]
    

#
def test_sortkey_wrapper():
    def wrap(x):
        return ValueWrapper(x, operator.lt)

    assert wrap(3) < wrap(5)
    assert (wrap(3), wrap(10)) < (wrap(3), wrap(15))   


#
#
#
#
#

class Hotel:
    """ @type
    ホテル。
    """
    def __init__(self, name):
        self._name = name
        self._rooms = [
            Room("101", "Twin", "Bed"),
            Room("102", "Twin", "Bed"),
            Room("103", "Single", "Futon"),
            Room("201", "Double", "Bed"),
            Room("202", "Double", "Bed"),
            Room("203", "Twin", "Futon")
        ]

    def name(self):
        """@method
        Returns:
            Str:
        """
        return self._name
    
    def rooms(self):
        """ @method
        Returns:
            Sheet[Room]:
        """
        return self._rooms

class Room:
    """ @type
    ホテルの部屋。
    """
    def __init__(self, name, type, style):
        self._name = name
        self._type = type
        self._style = style
    
    def name(self):
        """ @method
        Returns: 
            Str:
        """
        return self._name
        
    def type(self):
        """ @method
        Returns: 
            Str:
        """
        return self._type

    def style(self):
        """ @method
        Returns: 
            Str:
        """
        return self._style

def hotelrooms(name):
    h = Hotel(name)
    cxt = instant_context()
    o = Sheet(h.rooms(), cxt.new_type(Room))
    return o, cxt

#
def test_construct():
    rooms, _cxt = hotelrooms("Okehazama")
    assert rooms.get_current_columns()
    assert isinstance(rooms.get_current_columns()[0], DataItemItselfColumn)
    assert rooms.get_current_column_names() == ["="]

#
def test_append():
    rooms, cxt = hotelrooms("Okehazama")
    assert [x.name() for x in rooms.current_items()] == ["101", "102", "103", "201", "202", "203"]
    rooms.append(cxt, Room("501", "Suite", "Bed"))
    assert [x.name() for x in rooms.current_items()] == ["101", "102", "103", "201", "202", "203", "501"]

    #
    rooms.view(cxt, ["name", "type"])
    rooms.append(cxt, Room("502", "Single", "Bed"))
    rooms.append(cxt, Room("503", "Single", "Bed"))
    assert [x[0] for _, x in rooms.current_rows()] == ["101", "102", "103", "201", "202", "203", "501", "502", "503"]

#
def test_conversion_construct():
    cxt = instant_context()
    r = cxt.new_object(["A1", "B2B", "C3C3"], conversion="Sheet[Str]: (length, =)")
    sh = r.value
    assert sh.get_row(0) == [2, "A1"]
    assert sh.get_row(1) == [3, "B2B"]
    assert sh.get_row(2) == [4, "C3C3"]


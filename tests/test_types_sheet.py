import pytest
import operator

from machaon.core.type.instance import TypeInstance
from machaon.core.type.typemodule import TypeModule
from machaon.core.object import ObjectCollection, Object
from machaon.core.context import InvocationContext, instant_context
from machaon.core.sort import ValueWrapper
from machaon.core.function import parse_function
from machaon.types.sheet import Sheet, ItemItselfColumn

from machaon.macatest import run

class Employee():
    """ @type
    従業員
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

def employees_sheet(objectdesk, args, columns) -> Sheet:
    datas = [Employee(*a) for a in args]
    view = objectdesk.new_object(datas, *columns, conversion="Sheet[Employee]")
    return view.value

@pytest.fixture
def objectdesk():
    typemod = TypeModule()
    typemod.add_fundamentals()
    typemod.define(Employee, typename="Employee")
    desk = InvocationContext(input_objects=ObjectCollection(), type_module=typemod)
    return desk

#
def values(objects):
    return [x.value for x in objects]

#
# 型
#
def test_type():
    datas = [("ken", "332-0011"), ("ren", "224-0022"), ("shin", "113-0033")]
    columns = ["name", "postcode"]
    cxt = instant_context()
    cxt.type_module.define(Employee)
    sh = cxt.new_object(datas, *columns, conversion="Sheet[Employee]")

    assert isinstance(sh.type, TypeInstance)
    assert len(sh.type.get_args()) == 1
    assert sh.type.get_args()[0].get_conversion() == "Employee:tests.test_types_sheet.Employee"



#
#
# カラム
#
#
def test_column(objectdesk):
    view = employees_sheet(objectdesk, [("ken", "332-0011"), ("ren", "224-0022"), ("shin", "113-0033")], ["name", "postcode"])

    namecol = view.get_current_columns()[0]
    assert namecol.get_name() == "name"
    assert namecol.get_type_conversion() is None # 型指定は無し

    view.add_column("Int :: tall")
    assert view.get_current_column_names() == ["name", "postcode", "tall"]

    tallcol = view.get_current_columns()[2]
    assert tallcol.get_name() == "tall"
    assert tallcol.get_type_conversion() == "Int"

    # カラムの値を得る 
    subject = view.items[0]
    assert namecol.eval(subject, objectdesk).value == "ken"

    subject = view.items[0]
    assert tallcol.eval(subject, objectdesk).value == 3

    subject = view.items[2]
    assert namecol.eval(subject, objectdesk).value == "shin"

    subject = view.items[1]
    assert namecol.eval(subject, objectdesk).value == "ren"


def test_create_no_mod(objectdesk):
    view = employees_sheet(objectdesk, (("ken",), ("yuuji",), ("kokons",)), ("name",))
    
    assert view.count() == 3
    assert len(view.get_current_columns()) == 1
    assert view.get_current_columns()[0].get_name() == "name"
    assert view.get_current_columns()[0].stringify(objectdesk, objectdesk.new_object("ken")) == "ken"

    assert view.rows_to_string_table(objectdesk) == [(0, ["ken"]), (1, ["yuuji"]), (2, ["kokons"])]
    view.select(1)
    assert view.selection_index() == 1
    assert values(view.row_values(0)) == ["ken"]
    assert values(view.row_values(view.selection_index())) == ["yuuji"]


def test_expand_view(objectdesk):
    view = employees_sheet(objectdesk, [("ken","111-1111"), ("yuuji","222-2222"), ("kokons","333-3333")], ["name", "postcode"])

    view.view_extend(objectdesk, "tall", "name")
    assert view.get_current_column_names() == ["name", "postcode", "tall"]
    assert view.count() == 3
    assert values(view.row_values(0)) == ["ken", "111-1111", 3]

    view.view_add(objectdesk, "@ tall * 100")
    assert view.get_current_column_names() == ["name", "postcode", "tall", '"@ tall * 100"']
    assert view.count() == 3
    assert values(view.row_values(0)) == ["ken", "111-1111", 3, 300]

    employee = objectdesk.get_type("Employee")
    view.insert_items_and_generate_rows(objectdesk, -1, [employee.new_object(Employee("irina", "444-4444"))])
    assert view.get_current_column_names() == ["name", "postcode", "tall", '"@ tall * 100"']
    assert view.count() == 4
    assert values(view.row_values(3)) == ["irina", "444-4444", 5, 500]

def test_algorithm(objectdesk):
    view = employees_sheet(objectdesk, [
        ("ken","111-1111"), ("yuuji","222-2222"), ("kokons","333-3333"), ("unknown", None)
    ], ["name", "postcode"])
    employee = objectdesk.get_type("Employee")

    # foreach
    f = parse_function("@ tall * 1000")
    view.foreach(objectdesk, None, f)

    # map
    f = parse_function("@ tall")
    vals = view.map(objectdesk, None, f)
    assert len(vals) == 4
    assert vals[0].value == 3
    assert vals[1].value == 5
    assert vals[2].value == 6
    assert vals[3].value == 7

    # filter
    f = parse_function(".: @ name contains ke :. || .: @ tall == 6 :.")
    view.filter(objectdesk, None, f)
    assert view.count() == 2
    assert values(view.row_values(0)) == ["ken","111-1111"]
    assert values(view.row_values(1)) == ["kokons","333-3333"]

    # collect
    viewhe = heterovalues()
    f = parse_function("@ upper")
    vals = viewhe.collect(objectdesk, None, f)
    assert len(vals) == 2
    assert values(vals) == [ "STRING1", "STRING-STRANG2" ]
    
    # sort
    """
    f = parse_function("@ name")
    # TODO: get_lambda_argument_namesの実装
    view = Sheet(datas, employee).view(objectdesk, "table", predicate=f)
    assert view.count() == 2
    assert view.rows_to_string_table(objectdesk) == ([(0, ["ken","3"]), (2, ["yuuji","5"])], [5, 1])
    """

@pytest.mark.skip()
def test_filtered_manytimes(objectdesk):
    datas = [Employee(x) for x in ("ken", "ishulalmandij", "yuuji")]
    
    view = parse_new_setview(objectdesk, datas, "name postcode")
    view.select(1)
    assert view.count() == 3
    assert values(view.row_values(view.selection())) == ["ishulalmandij", "000-0000"]
    
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

def hotelrooms(name, rooms=None):
    h = Hotel(name)
    cxt = instant_context()
    rooms = rooms if rooms is not None else h.rooms()
    o = Sheet.constructor(Sheet, cxt, cxt.select_type(Room), rooms)
    return o, cxt

def heterovalues():
    values = [
        "string1",
        "string-strang2",
        31,
        123.4,
    ]
    cxt = instant_context()
    v = Sheet.constructor(Sheet, cxt, None, values)
    return v

#
#
def test_construct():
    rooms, _cxt = hotelrooms("Okehazama")
    assert rooms.get_current_columns()
    assert isinstance(rooms.get_current_columns()[0], ItemItselfColumn)
    assert rooms.get_current_column_names() == ["@"]

    # 型推定をテスト
    values = heterovalues()
    assert values.at(0).get_typename() == "Str"
    assert values.at(1).get_typename() == "Str"
    assert values.at(2).get_typename() == "Int"
    assert values.at(3).get_typename() == "Float"


def test_apis():
    rooms, cxt = hotelrooms("Okehazama")
    assert [x.value.name() for x in rooms.current_items()] == ["101", "102", "103", "201", "202", "203"]
    rooms.append(cxt, Room("501", "Suite", "Bed"))
    assert [x.value.name() for x in rooms.current_items()] == ["101", "102", "103", "201", "202", "203", "501"]

    # append
    rooms.view(cxt, "name", "type")
    rooms.append(cxt, Room("502", "Single", "Bed"))
    rooms.append(cxt, Room("503", "Single", "Bed"))
    assert [x[0].value for _, x in rooms.current_rows()] == ["101", "102", "103", "201", "202", "203", "501", "502", "503"]

    # pick
    room = rooms.pick_in_first_column(cxt, None, "202")
    assert room.value.name() == "202" # 完全一致
    room = rooms.pick_in_first_column(cxt, None, "10")
    assert room.value.name() == "101" # 前方一致
    room = rooms.pick_in_first_column(cxt, None, "03")
    assert room.value.name() == "103" # 後方一致

def test_list_conversion_construct():
    cxt = instant_context()
    r = cxt.new_object(["A1", "B2B", "C3C3"], conversion="Sheet[Str]")
    sh = r.value
    sh.view(cxt, "length", "@")
    assert values(sh.row_values(0)) == [2, "A1"]
    assert values(sh.row_values(1)) == [3, "B2B"]
    assert values(sh.row_values(2)) == [4, "C3C3"]

def test_string_tables():
    rooms, cxt = hotelrooms("Okehazama")
    rooms.append(cxt, Room("haunted", None, None))
    
    rooms.view(cxt, "name", "type", "style")
    table = rooms.rows_to_string_table(cxt)
    assert table == [
        (0, ["101", "Twin", "Bed"]),
        (1, ["102", "Twin", "Bed"]),
        (2, ["103", "Single", "Futon"]),
        (3, ["201", "Double", "Bed"]),
        (4, ["202", "Double", "Bed"]),
        (5, ["203", "Twin", "Futon"]),
        (6, ["haunted", "-", "-"]) # Noneは-に変換する
    ]

    # hetero container
    view = heterovalues()
    view.view(cxt, "@", "@ * 2")
    table = view.rows_to_string_table(cxt)
    assert table == [
        (0, ["string1", "string1string1"]),
        (1, ["string-strang2", "string-strang2string-strang2"]),
        (2, ["31", "62"]),
        (3, ["123.4", "246.8"])
    ]



def test_none_value():
    rooms, cxt = hotelrooms("Okehazama", [
        Room("1408", None, None),
        Room("1408", None, None),
        Room("1408", None, None),
    ])
    rooms.insert(cxt, 1, Room("404", "Double", "Bed"))
    
    rooms.view(cxt, "name", "type", "style")
    table = rooms.rows_to_string_table(cxt)
    assert table == [
        (0, ["1408", "-", "-"]),
        (1, ["404", "Double", "Bed"]),
        (2, ["1408", "-", "-"]),
        (3, ["1408", "-", "-"]),
    ]


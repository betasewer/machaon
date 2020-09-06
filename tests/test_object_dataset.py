import pytest

import operator

from machaon.object.type import TypeModule
from machaon.object.object import ObjectCollection
#from machaon.object.dataset import parse_new_dataview, parse_dataview, DataViewRowIndexer, DataView, make_data_columns
#from machaon.object.formula import parse_formula
from machaon.object.sort import ValueWrapper

class Employee():
    """
    
    """
    def __init__(self, name, postcode="000-0000"):
        self._name = name
        self._postcode = postcode

    def name(self):
        return self._name

    def tall(self):
        return len(self._name)
    
    def postcode(self):
        return self._postcode

    @classmethod
    def describe_object(cls, traits):
        traits.describe(
            typename="employee"
        )["name"](
            help="名前"
        )["tall"](
            help="身長",
            return_type="int"
        )["postcode"](
            help="郵便番号"
        )

@pytest.fixture
def objectdesk():
    desk = ObjectDesktop()
    from machaon.object.fundamental import fundamental_type
    desk.add_types(fundamental_type)
    return desk

#
#
#
def test_column(objectdesk):
    employee = objectdesk.get_type(Employee)
    cols = make_data_columns(employee, objectdesk, "name", "postcode")
    view = DataView(employee, [
        Employee(x,y) for (x,y) in [("ken", "332-0011"), ("ren", "224-0022"), ("shin", "113-0033")]
    ], viewcolumns=cols)

    assert view.get_item_type() is employee
    assert view.get_current_columns() == cols
    assert view.get_top_column_name() == "name"
    assert view.get_default_column_names() == ["name"]
    assert view.get_link_column_name() is None

    assert view.find_current_column("name") is not None
    assert view.find_current_column("postcode") is not None
    assert view.find_current_column("tall") is None
    view.new_current_column(objectdesk, "tall")
    assert view.find_current_column("tall") is not None

#
#
#
def test_create_no_mod(objectdesk):
    datas = [Employee(x) for x in ("ken", "yuuji", "kokons")]
    
    view = parse_new_dataview(objectdesk, datas)

    assert view.count() == 3
    assert len(view.get_current_columns()) == 1
    assert view.get_current_columns()[0].get_name() == "name"
    assert view.rows_to_string_table() == ([(0, ["ken"]), (1, ["yuuji"]), (2, ["kokons"])], [6])
    view.select(1)
    assert view.selection() == 1
    assert view.row(view.selection()) == ["yuuji"]

    # column
    name_col = view.get_current_columns()[0]
    assert name_col.make_value(view.itemtype, view.items[0]) == "ken"

    
def test_create_filtered(objectdesk):
    datas = [Employee(x) for x in ("ken", "ishulalmandij", "yuuji")]

    f = parse_formula("(ke in @name) || (@tall == 5)", objectdesk, objectdesk.get_type(Employee))
    bits = [f(f.create_values_context(x)) for x in datas]
    assert bits == [True, False, True]
    
    view = parse_new_dataview(objectdesk, datas,
        "/where (ke in @name) || (@tall == 5)"
    )
    assert view.count() == 2
    assert view.rows_to_string_table() == ([(0, ["ken","3"]), (2, ["yuuji","5"])], [5, 1])


def test_filtered_manytimes(objectdesk):
    datas = [Employee(x) for x in ("ken", "ishulalmandij", "yuuji")]
    
    view = parse_new_dataview(objectdesk, datas, "name postcode")
    view.select(1)
    assert view.count() == 3
    assert view.row(view.selection()) == ["ishulalmandij", "000-0000"]
    
    view2 = parse_dataview(objectdesk, view, "/where @tall < 10")
    assert view2.count() == 2
    assert view2.rows_to_string_table() == ([(0, ["ken","000-0000", "3"]), (2, ["yuuji", "000-0000", "5"])], [5, 8, 1])

    view3 = parse_dataview(objectdesk, view2, "/where @name == ken")
    assert view3.count() == 1
    assert view3.rows_to_string_table() == ([(0, ["ken","000-0000", "3"])], [3, 8, 1])

    view4 = parse_dataview(objectdesk, view3, "/where @postcode == 777-7777")
    assert view4.count() == 0
    
    view5 = parse_dataview(objectdesk, view4, "/where @name == batman")
    assert view5.count() == 0

#
#
#
def test_sorted(objectdesk):
    datas = [Employee(x) for x in ("ken", "ishulalmandij", "yuuji")]
    
    view = parse_new_dataview(objectdesk, datas, "name")
    view.select(1)
    assert view.selection_row() == ["ishulalmandij"]

    view2 = parse_dataview(objectdesk, view, "/sortby name")
    assert view2.rows_to_string_table() == ([(1, ["ishulalmandij"]), (0, ["ken"]), (2, ["yuuji"])], [13])
    assert view2.selection_row() == ["ishulalmandij"]
    
    view3 = parse_dataview(objectdesk, view, "/sortby !tall")
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
def test_rowindexer():
    indexer = DataViewRowIndexer(["column-1", "column-2", "column-3"])
    assert indexer.create_column_indexmap(["column-1", "column-4"]) == {"column-1": 0, "column-4": 3}
    assert indexer.create_column_indexmap(["column-4", "column-5"]) == {"column-4": 3, "column-5": 4}
    assert indexer.create_column_indexmap(["column-2", "column-5"]) == {"column-2": 1, "column-5": 4}
    assert indexer.pop_new_columns() == ["column-4", "column-5"]

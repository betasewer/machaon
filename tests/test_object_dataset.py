import pytest

import operator

from machaon.object.type import TypeModule
from machaon.object.object import ObjectCollection, Object
from machaon.object.invocation import InvocationContext
from machaon.object.dataset import DataViewRowIndexer, DataView, make_data_columns, DataColumn
from machaon.object.message import Function
from machaon.object.sort import ValueWrapper

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
    cols = make_data_columns(employee, "name", "postcode")
    view = DataView(employee, 
        items=[
            Employee(x,y) for (x,y) in [("ken", "332-0011"), ("ren", "224-0022"), ("shin", "113-0033")]
        ], 
        viewcolumns=cols
    )

    assert view.get_item_type() is employee
    assert view.get_current_columns() == cols
    assert view.get_top_column_name() == "name"
    assert view.get_default_column_names() == ["name"]
    assert view.get_link_column_name() is None

    assert view.find_current_column("name") is not None
    assert view.find_current_column("postcode") is not None
    assert view.find_current_column("tall") is None
    view.add_current_column("tall")
    assert view.find_current_column("tall") is not None

    namecol = cols[0]
    assert namecol.get_name() == "name"
    assert namecol.get_type(objectdesk) is objectdesk.get_type("Str")
    #assert namecol.get_doc() == ""

    # カラムの値を得る
    subject = Object(employee, view.items[0])
    assert namecol.method
    assert namecol.method.get_action()(subject.value) == "ken"
    DataColumn.evallog = True
    namecol.eval(subject, objectdesk) == "ken"
    namecol.getter.message.pprint_log()

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
    view = DataView(employee, datas).create_view(objectdesk, "table")
    
    assert view.count() == 3
    assert len(view.get_current_columns()) == 1
    assert view.get_current_columns()[0].get_name() == "name"

    assert view.rows == [(0, ["ken"]), (1, ["yuuji"]), (2, ["kokons"])]

    assert view.rows_to_string_table(objectdesk) == ([(0, ["ken"]), (1, ["yuuji"]), (2, ["kokons"])], [6])
    view.select(1)
    assert view.selection() == 1
    assert view.row(view.selection()) == ["yuuji"]

    
def test_create_filtered(objectdesk):
    datas = [Employee(x) for x in ("ken", "ishulalmandij", "yuuji")]
    employee = objectdesk.get_type("Employee")

    f = Function("(ke in @name) || (@tall == 5)")
    bits = [f.run(Object(objectdesk.get_type(Employee), x), objectdesk) for x in datas]
    assert bits == [True, False, True]
    
    # TODO: get_lambda_argument_namesの実装
    view = DataView(employee, datas).create_view(objectdesk, "table", filter=f)
    assert view.count() == 2
    assert view.rows_to_string_table(objectdesk) == ([(0, ["ken","3"]), (2, ["yuuji","5"])], [5, 1])


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

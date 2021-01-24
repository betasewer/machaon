import pytest

import operator

from machaon.core.type import TypeModule
from machaon.core.object import ObjectCollection, Object
from machaon.core.invocation import InvocationContext
from machaon.types.objectset import ObjectSet, make_data_columns, DataColumn
from machaon.core.message import MessageEngine
from machaon.core.sort import ValueWrapper

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
    view = ObjectSet([
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
    assert namecol.get_type(objectdesk) is objectdesk.get_type("Str")

    # カラムの値を得る
    subject = Object(employee, view.items[0])
    assert namecol.invocation
    assert namecol.invocation.get_action()(subject.value) == "ken"
    DataColumn.evallog = True
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

    view = ObjectSet(datas, employee, objectdesk, ["name"])
    
    assert view.count() == 3
    assert len(view.get_current_columns()) == 1
    assert view.get_current_columns()[0].get_name() == "name"

    assert view.rows == [(0, ["ken"]), (1, ["yuuji"]), (2, ["kokons"])]

    assert view.rows_to_string_table(objectdesk) == ([(0, ["ken"]), (1, ["yuuji"]), (2, ["kokons"])], [6])
    view.select(1)
    assert view.selection() == 1
    assert view.row(view.selection()) == ["yuuji"]

#
#
#
def test_expand_view(objectdesk):
    items = [Employee(x, y) for (x,y) in (("ken","111-1111"), ("yuuji","222-2222"), ("kokons","333-3333"))]
    employee = objectdesk.get_type("Employee")

    view = ObjectSet(items, employee, objectdesk, ["name", "postcode"])
    view.expand_view(objectdesk, ["tall"])

    assert view.get_current_column_names() == ["name", "postcode", "tall"]
    assert view.count() == 3
    assert view.row(0) == ["ken", "111-1111", 3]



@pytest.mark.skip()
def test_create_filtered(objectdesk):
    datas = [Employee(x) for x in ("ken", "ishulalmandij", "yuuji")]
    employee = objectdesk.get_type("Employee")

    f = Function("(ke in @name) || (@tall == 5)")
    bits = [f.run(Object(objectdesk.get_type(Employee), x), objectdesk) for x in datas]
    assert bits == [True, False, True]
    
    # TODO: get_lambda_argument_namesの実装
    view = ObjectSet(datas, employee).view(objectdesk, "table", predicate=f)
    assert view.count() == 2
    assert view.rows_to_string_table(objectdesk) == ([(0, ["ken","3"]), (2, ["yuuji","5"])], [5, 1])


@pytest.mark.skip()
def test_filtered_manytimes(objectdesk):
    datas = [Employee(x) for x in ("ken", "ishulalmandij", "yuuji")]
    
    view = parse_new_setview(objectdesk, datas, "name postcode")
    view.select(1)
    assert view.count() == 3
    assert view.row(view.selection()) == ["ishulalmandij", "000-0000"]
    
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


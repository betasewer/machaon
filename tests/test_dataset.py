import pytest

import operator

from machaon.dataset import DataViewFactory
from machaon.dataset.sort import DataSortKey, KeyWrapper

class ADataClass():
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name

    def length(self):
        return len(self._name)

    @classmethod
    def describe(cls, ref):
        ref["name"](
            disp="名前"
        )["length"](
            disp="長さ",
            type="int"
        )

#
#
#
@pytest.mark.skip(True)
def test_clause():
    view = DataViewFactory(
        [ADataClass(x) for x in ("ken", "yuuji", "kokons")], 
        "/where name contains ke || (name == yuuji && length == 5)"
    )
    assert view.count() == 2
    assert view.rows_to_string_table() == ([["ken","3"], ["yuuji","5"]], [5, 1])
    view.select(1)
    assert view.selection() == 1
    assert view.row(view.selection()) == ["yuuji",5]


def test_sortkey_wrapper():
    def wrap(x):
        return KeyWrapper(x, operator.lt)

    assert wrap(3) < wrap(5)
    assert (wrap(3), wrap(10)) < (wrap(3), wrap(15))
    
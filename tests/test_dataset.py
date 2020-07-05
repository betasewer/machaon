from machaon.dataset import DataViewFactory

#
#
#
def test():
    class TestDataClass():
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

    view = DataViewFactory(
        [TestDataClass(x) for x in ("ken", "yuuji", "kokons")], 
        "? name } ke || (name == yuuji && length == 5) || name { ko"
    )
    assert view.count() == 2
    assert view.rows_to_string_table() == ([["ken","3"], ["yuuji","5"]], [5, 1])
    view.select(1)
    assert view.selection() == 1
    assert view.row(view.selection()) == ["yuuji",5]

test()
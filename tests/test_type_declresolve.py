"""@module
Using:
    Path:machaon.types.shell
"""

from machaon.core.context import instant_context
from machaon.core.type.describer import create_type_describer
from machaon.core.type.declresolver import BasicTypenameResolver, ModuleTypenameResolver
from machaon.core.method import Method

class Item:
    """ @type
    アイテム
    """
    def __init__(self, name):
        self.name = name

class Showcase:
    """ @type
    アイテムの陳列台
    Params:
        T(Type):
    """
    def __init__(self):
        self.items = [Item("sardine"), Item("salmon"), Item("mackerel")]

    def get(self, index):
        """ @method
        Params:
            index(Int):
        Returns:
            Item:
        """
        return self.items[index]

    def path(self):
        """ @method
        Returns:
            Path:
        """
        return None


def test_string_describer():
    cxt = instant_context()
    t = cxt.select_type("Showcase[Item]", "tests.test_type_declresolve.Showcase")
    assert t
    assert t.get_describer_qualname() == "tests.test_type_declresolve.Showcase"
    assert isinstance(t.get_describer().get_typename_resolver(), ModuleTypenameResolver)
    
    # このモジュールの型と、machaon.coreの型を検出
    mth: Method = t.select_method("get")
    assert mth
    assert mth.get_result().get_typedecl().to_string() == "Item:tests.test_type_declresolve.Item"
    assert mth.get_param(0).get_typedecl().to_string() == "Int:machaon.core"

    # モジュール宣言の型を検出
    t2 = cxt.select_type("Showcase[Item]", "tests.test_type_declresolve.Showcase")
    assert t2 
    assert t2 is t
    mth: Method = t.select_method("path")
    assert mth
    assert mth.get_result().get_typedecl().to_string() == "Path:machaon.types.shell"
    



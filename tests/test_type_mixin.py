from machaon.core.importer import ClassDescriber
from machaon.core.invocation import TypeMethodInvocation
from machaon.core.context import instant_context
from machaon.core.message import select_method
from machaon.core.type import TypeModule, Type
from machaon.types.fundamental import fundamental_types


class StrEx:
    """ @type mixin
    MixinType:
        Str:
    """
    def sparse(self, s, space=1):
        """ @method
        スペースをあける
        Params:
            space?(Int):
        Returns:
            Str:
        """
        return (" " * space).join(s)

from machaon.macatest import run, parse_test

def test_mixin_load():
    types = TypeModule()
    types.add_fundamentals()
    types.load_definition(StrEx)

    StrType = types.get("Str")
    assert StrType.select_method("sparse") is not None
    assert isinstance(StrType.mixins()[0], ClassDescriber)
    assert StrType.mixins()[0].get_classname() == "StrEx"

    assert isinstance(select_method("sparse", StrType), TypeMethodInvocation)

def test_mixin_run():
    cxt = instant_context()
    cxt.type_module.load_definition(StrEx)

    StrType = cxt.get_type("Str")
    assert cxt.type_module.get_scope("") is not None
    assert isinstance(StrType, Type)
    assert StrType.select_method("sparse") is not None
    
    assert parse_test(cxt, "breakfast sparse", "b r e a k f a s t")
    assert parse_test(cxt, "breakfast sparse: 2", "b  r  e  a  k  f  a  s  t")

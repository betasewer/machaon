from machaon.core.type.describer import TypeDescriberClass
from machaon.core.invocation import TypeMethodInvocation
from machaon.core.context import instant_context
from machaon.core.message import select_method
from machaon.core.type.alltype import TypeModule, Type


class StrEx:
    """ @mixin
    MixinType:
        Str:machaon.core:
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
    types.define(StrEx)

    StrType = types.get("Str")
    assert StrType.select_method("sparse") is not None
    assert isinstance(StrType.get_describer(1), TypeDescriberClass)
    assert StrType.get_describer(1).get_typename() == "StrEx"

    assert isinstance(select_method("sparse", StrType), TypeMethodInvocation)


def test_mixn_load_double():
    types = TypeModule()
    types.add_fundamentals()
    StrType = types.get("Str")

    types.inject_type_mixin(StrEx, StrType)
    
    assert StrType.select_method("sparse") is not None

    types.inject_type_mixin(StrEx, StrType)

    assert StrType.select_method("sparse") is not None
    

def test_mixin_run():
    cxt = instant_context()
    cxt.type_module.define(StrEx)

    StrType = cxt.get_type("Str")
    assert isinstance(StrType, Type)
    assert StrType.select_method("sparse") is not None
    
    assert parse_test(cxt, "breakfast sparse", "b r e a k f a s t")
    assert parse_test(cxt, "breakfast sparse: 2", "b  r  e  a  k  f  a  s  t")



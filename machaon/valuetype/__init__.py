from machaon.valuetype.type import (
    type_traits_library, type_define_decolator, type_generator
)
from machaon.valuetype.fundamental import define_fundamental

#
#
#
#
valtypelib = type_traits_library()
define_valtype = type_define_decolator(valtypelib)
valtype = type_generator(valtypelib)

#
define_fundamental(valtypelib)

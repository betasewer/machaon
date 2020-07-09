from machaon.valuetype.type import (
    type_traits_library, type_define_decolator, type_generate
)
from machaon.valuetype.fundamental import define_fundamental

#
#
#
#
typelib_ = type_traits_library()
define_type = type_define_decolator(typelib_)
type_traits_of = type_generate(typelib_)

#
define_fundamental(typelib_)

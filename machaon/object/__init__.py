from machaon.object.type import (
    type_traits_library, type_definer, type_generator
)
from machaon.object.fundamental import define_fundamental

#
#
#
#
objtypelib = type_traits_library()
define_type = type_definer(objtypelib)
types = type_generator(objtypelib)

#
#define_fundamental(objtypelib)

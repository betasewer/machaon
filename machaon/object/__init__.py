from machaon.object.type import TypeModule
from machaon.object.fundamental import fundamental_type

#
#
#
types = TypeModule()
types.move(fundamental_type)

del (
    fundamental_type
)

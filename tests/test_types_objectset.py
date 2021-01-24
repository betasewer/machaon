from machaon.types.objectset import ObjectSet, DataItemItselfColumn
from machaon.core.type import TypeModule

class Hotel:
    """ @type
    ホテル。
    """
    def __init__(self, name):
        self._name = name
        self._rooms = [
            Room("101", "Twin", "Bed"),
            Room("102", "Twin", "Bed"),
            Room("103", "Single", "Futon"),
            Room("201", "Double", "Bed"),
            Room("202", "Double", "Bed"),
            Room("203", "Twin", "Futon")
        ]

    def name(self):
        """@method
        Returns:
            Str:
        """
        return self._name
    
    def rooms(self):
        """ @method
        Returns:
            Set[Room]:
        """
        return self._rooms

class Room:
    """ @type
    ホテルの部屋。
    """
    def __init__(self, name, type, style):
        self._name = name
        self._type = type
        self._style = style
    
    def name(self):
        """ @method
        Returns: 
            Str:
        """
        return self._name
        
    def type(self):
        """ @method
        Returns: 
            Str:
        """
        return self._type

    def style(self):
        """ @method
        Returns: 
            Str:
        """
        return self._style

def hotelrooms(name):
    h = Hotel(name)
    t = TypeModule()
    o = ObjectSet(h.rooms(), t.new(Room))
    return o

#
def test_construct():
    rooms = hotelrooms("Okehazama")
    assert rooms.get_current_columns()
    assert isinstance(rooms.get_current_columns()[0], DataItemItselfColumn)
    assert rooms.get_current_column_names() == ["="]

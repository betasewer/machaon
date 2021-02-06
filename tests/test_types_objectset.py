from machaon.types.objectset import ObjectSet, DataItemItselfColumn
from machaon.core.type import TypeModule
from machaon.core.invocation import instant_context

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
    cxt = instant_context()
    o = ObjectSet(h.rooms(), cxt.new_type(Room))
    return o, cxt

#
def test_construct():
    rooms, _cxt = hotelrooms("Okehazama")
    assert rooms.get_current_columns()
    assert isinstance(rooms.get_current_columns()[0], DataItemItselfColumn)
    assert rooms.get_current_column_names() == ["="]

#
def test_append():
    rooms, cxt = hotelrooms("Okehazama")
    assert [x.name() for x in rooms.current_items()] == ["101", "102", "103", "201", "202", "203"]
    rooms.append(cxt, Room("501", "Suite", "Bed"))
    assert [x.name() for x in rooms.current_items()] == ["101", "102", "103", "201", "202", "203", "501"]

    #
    rooms.view(cxt, ["name", "type"])
    rooms.append(cxt, Room("502", "Single", "Bed"))
    rooms.append(cxt, Room("503", "Single", "Bed"))
    assert [x[0] for _, x in rooms.current_rows()] == ["101", "102", "103", "201", "202", "203", "501", "502", "503"]

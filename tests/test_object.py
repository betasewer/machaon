import pytest
from machaon.object.desktop import ObjectDesktop, Object

def test_desktop():
    desk = ObjectDesktop()
    desk.push(Object("obj-1", "int", 3))
    desk.push(Object("obj-2", "int", 100))
    desk.push(Object("obj-3", "complex", 3+5j))
    desk.push(Object("obj-4", "ip-address", (128,0,0,1)))

    assert desk.pick("obj-1").value == 3

    assert desk.pick_by_type("int").name == 'obj-2'
    assert desk.pick_by_type("complex").name == 'obj-3'
    assert desk.pick_by_type("ip-address").name == 'obj-4'
    assert desk.pick_by_type("ip-address").value == (128,0,0,1)
    
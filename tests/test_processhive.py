import pytest
from machaon.process import ProcessHive, ProcessChamber, Process

proc_ = 0
def newproc():
    global proc_
    proc_ += 1
    return Process("process{}".format(proc_))

def test_activate():
    hive = ProcessHive()

    # 空の状態
    assert hive.count() == 0
    assert hive.get_active_index() is None
    assert hive.get_active() is None
    assert hive.get_previous_active() is None

    # new activate
    chm1 = hive.new_activate(newproc())
    assert hive.count() == 1
    assert hive.get_active() is chm1
    assert hive.get_previous_active() is None

    chm2 = hive.new_activate(newproc())
    assert hive.count() == 2
    assert hive.get_active() is chm2
    assert hive.get_previous_active() is chm1

    chm3 = hive.new_activate(newproc())
    assert hive.get_active() is chm3
    assert hive.get_previous_active() is chm2

    # activate
    assert hive.activate(chm1.get_index()) is chm1
    assert hive.get_active() is chm1
    assert hive.get_previous_active() is chm3

    # remove
    hive.remove() # アクティブな chm1 が消える
    assert hive.get_active() is chm3
    assert hive.get_previous_active() is chm2
    assert hive.count() == 2
    assert list(hive.rhistory()) == [chm3.get_index(), chm2.get_index()]

    hive.remove() # chm3が消える
    assert hive.get_active() is chm2
    assert hive.get_previous_active() is None
    assert hive.count() == 1
    assert list(hive.rhistory()) == [chm2.get_index()]

    hive.remove() # すべて消失
    assert hive.get_active() is None
    assert hive.get_previous_active() is None
    assert hive.count() == 0

    # remove background
    chm1 = hive.new_activate(newproc())
    chm2 = hive.new_activate(newproc())
    chm3 = hive.new_activate(newproc()) # active
    assert list(hive.rhistory()) == [chm3.get_index(), chm2.get_index(), chm1.get_index()]

    assert hive.get_active() is chm3
    assert hive.get_previous_active() is chm2
    
    hive.remove(chm1.get_index())
    assert hive.get_active() is chm3
    assert hive.get_previous_active() is chm2

    hive.remove(chm2.get_index())
    assert hive.get_active() is chm3
    assert hive.get_previous_active() is None # この挙動分かりにくいか？

    hive.remove(chm3.get_index())
    assert hive.get_active() is None
    assert hive.get_previous_active() is None


@pytest.mark.xfail()
def test_remove_empty():
    hive = ProcessHive()
    hive.remove()

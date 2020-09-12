import pytest
from machaon.process import ProcessHive, ProcessChamber, Process

#
#
#
def test_chamber_activate():
    hive = ProcessHive()

    # 空の状態
    assert hive.count() == 0
    assert hive.get_active_index() is None
    assert hive.get_active() is None
    assert hive.get_previous_active() is None

    # new activate
    chm1 = hive.addnew()
    assert hive.count() == 1
    assert hive.get_active() is chm1
    assert hive.get_previous_active() is None

    chm2 = hive.addnew()
    assert hive.count() == 2
    assert hive.get_active() is chm2
    assert hive.get_previous_active() is chm1

    chm3 = hive.addnew()
    assert hive.get_active() is chm3
    assert hive.get_previous_active() is chm2

    # activate
    hive.activate(chm1.get_index())
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
    chm1 = hive.addnew()
    chm2 = hive.addnew()
    chm3 = hive.addnew() # active
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

#
#
#
def test_chamber_index():
    hive = ProcessHive()
    chm1 = hive.addnew()
    chm2 = hive.addnew()
    chm3 = hive.addnew() # active chm3
    
    # 
    assert hive.get_next_index() is None
    assert hive.get_next_index(delta=-1) == chm2.get_index()
    assert hive.get_next_index(delta=-2) == chm1.get_index()
    assert hive.get_next_index(delta=-3) is None

    # 削除されたチャンバーをスキップ
    hive.activate(chm1.get_index()) # active chm1
    hive.remove(chm2.get_index())
    assert hive.get_next_index() == chm3.get_index()
    assert hive.get_next_index(delta=-1) is None

    hive.remove(chm3.get_index()) 
    chm4 = hive.addnew()
    chm5 = hive.addnew()
    hive.activate(chm1.get_index()) # active chm1 : 1 (2) (3) 4 5  
    assert hive.get_next_index(delta=1) == chm4.get_index()
    assert hive.get_next_index(delta=2) == chm5.get_index()


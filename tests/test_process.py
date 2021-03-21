import pytest
from machaon.core.message import MessageEngine
from machaon.process import Process, ProcessChamber, ProcessMessage, TempSpirit

def ten_messages_chamber_zero():
    _nullmsg = MessageEngine()
    chm = ProcessChamber(0)

    chm.add_prelude_messages([ProcessMessage(">>")])
    pr1 = chm.add(Process(1, _nullmsg))
    pr1.post_message(ProcessMessage("A"))
    pr1.post_message(ProcessMessage("B"))
    pr1.post_message(ProcessMessage("C"))
    pr1.finish()
    chm.handle_process_messages()

    pr2 = chm.add(Process(2, _nullmsg))
    pr2.post_message(ProcessMessage("い"))
    pr2.post_message(ProcessMessage("ろ"))
    pr2.post_message(ProcessMessage("は"))
    pr2.finish()
    chm.handle_process_messages()

    pr3 = chm.add(Process(3, _nullmsg))
    pr3.post_message(ProcessMessage("金"))
    pr3.post_message(ProcessMessage("土"))
    pr3.post_message(ProcessMessage("日"))

    return chm

def test_handle_messages():
    chm = ten_messages_chamber_zero()
    assert [x.text for x in chm.get_process_messages()] == [
        "A", "B", "C", "い", "ろ", "は"
    ]
    chm.handle_process_messages()
    assert [x.text for x in chm.get_process_messages()] == [
        "A", "B", "C", "い", "ろ", "は", "金", "土", "日"
    ]

def test_drop_process():
    chm = ten_messages_chamber_zero()
    chm.get_process(3)._start_infinite_thread(TempSpirit())
    
    chm.drop_processes()

    # 稼働中のプロセスは停止されない
    assert len(chm.get_processes()) == 1
    chm.handle_process_messages()
    assert [x.text for x in chm.get_process_messages()] == [
        "金", "土", "日"
    ]

def test_drop_process_if():
    chm = ten_messages_chamber_zero()
    chm.get_process(3).finish()
    chm.handle_process_messages()

    chm.drop_processes(pred=lambda x: x.index % 2 == 1) # 奇数IDのプロセスのみ削除する
    
    assert len(chm.get_processes()) == 1
    chm.handle_process_messages()
    assert [x.text for x in chm.get_process_messages()] == [
        "い", "ろ", "は"
    ]




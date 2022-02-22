import pytest

from machaon.core.invocation import instant_context
from machaon.flow.flow import Flow

def test_flow():
    cxt = instant_context()
    f = Flow()
    f.pipe(cxt, "Int:Bin[](6)")
    assert f.influx("1011") == 0b01011
    assert f.reflux(0b010101) == "010101"

    f = Flow()
    f.pipe(cxt, "Int:Locale")
    assert f.influx("123,456") == 123456
    assert f.reflux(123456) == "123,456"

    f = Flow()
    f.pipe(cxt, "Int:Identity")
    assert f.influx(100) == 100
    assert f.reflux(100) == 100

    f = Flow()
    f.pipe(cxt, "Str:Postfixed[](ですぅ)")
    assert f.influx("★ですぅ") == "★"
    assert f.reflux("★") == "★ですぅ"

    f = Flow()
    f.pipe(cxt, "Str:Postfixed[](円)").pipe(cxt, "Int:Locale")
    assert f.influx("102,089円") == 102089
    assert f.reflux(23456) == "23,456円"

@pytest.mark.xfail
def test_postfix_fail():
    cxt = instant_context()
    f = Flow()
    f.pipe(cxt, "Str:Enclosed[](《,》)")
    assert f.influx("《あ") == "あ" # 括弧が足りないので失敗する


def test_enclosure_try():
    cxt = instant_context()
    f = Flow()
    f.pipe(cxt, "Str:Enclosed[](『,』)+Postfixed[](』)+Prefixed[](『)+Identity")
    assert f.influx("『あ』") == "あ"
    assert f.influx("『あ") == "あ"
    assert f.influx("あ』") == "あ"
    assert f.influx("あ") == "あ"

    assert f.reflux("あ") == "『あ』"
    assert f.reflux("『あ") == "『『あ』"


def test_none_functor():
    cxt = instant_context()
    f = Flow()
    f.pipe(cxt, "Int")
    f.pipe_message(cxt, "@ * 10").message_reflux(cxt, "@ / 10 floor")
    f.pipe_none(cxt, "blank")

    assert f.influx("21") == 210
    assert f.reflux(210) == "21"

    assert f.influx("") == None
    assert f.reflux(None) == ""

    f = Flow()
    f.pipe(cxt, "Int")
    f.pipe_message(cxt, "@ * 10").message_reflux(cxt, "@ / 10 floor")
    f.pipe_none(cxt, "blank")




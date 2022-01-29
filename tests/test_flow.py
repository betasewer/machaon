from machaon.core.invocation import instant_context
from machaon.flow.flow import Flow

def test_flow():
    cxt = instant_context()
    f = Flow()
    f.pipe(cxt, "Int:Bin")
    assert f.influx("1011") == 0b01011
    assert f.reflux(0b010101) == "10101"

    f = Flow()
    f.pipe(cxt, "Str:RStrip[](ですぅ)")
    assert f.influx("★ですぅ") == "★"
    assert f.reflux("★") == "★ですぅ"

    f = Flow()
    f.pipe(cxt, "Str:RStrip[](ですぅ)").pipe(cxt, "Int:Bin")
    assert f.influx("01011ですぅ") == 0b01011
    assert f.reflux(0b01011) == "1011ですぅ"

test_flow()
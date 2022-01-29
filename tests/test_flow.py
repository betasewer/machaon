from machaon.core.invocation import instant_context
from machaon.flow.flow import Flow

def test_flow():
    cxt = instant_context()
    f = Flow()
    f.pipe(cxt, "Int:Bin")
    assert f.influx("01011") == 0b01011

    f = Flow()
    f.pipe(cxt, "Str:RStrip[](ですぅ)").pipe(cxt, "Int:Bin")
    assert f.influx("01011ですぅ") == 0b01011

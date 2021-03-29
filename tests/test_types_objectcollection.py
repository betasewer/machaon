from machaon.core.object import ObjectCollection
from machaon.core.invocation import instant_return_test, instant_context


def test_conversion_construct():
    cxt = instant_context()

    # from dict
    col = instant_return_test(cxt, {
        "mackerel" : "さば", 
        "herring" : "にしん",
        "cod" : "たら",
    }, "ObjectCollection")
    assert col.test_truth()
    assert col.value.get("cod").value == "たら"
    assert col.value.get("herring").value == "にしん"



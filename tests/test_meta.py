import datetime

from machaon.types.meta import meta

def test_date_meta():
    d = meta.Date.from_joined("2023/7/31")
    assert isinstance(d, datetime.date)
    assert meta.Date.joined(d) == "20230731"
    assert meta.Date.joined(d,"/") == "2023/07/31"

    d = meta.Date.from_yearlow_date("91.03.24")
    assert isinstance(d, datetime.date)
    assert meta.Date.joined(d,"/") == "1991/03/24"

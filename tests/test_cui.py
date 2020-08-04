import pytest

def test_char_width():
    from machaon.cui import get_char_width
    assert get_char_width("あ") == 2
    assert get_char_width("Ａ") == 2
    assert get_char_width("0") == 1
    assert get_char_width("屋") == 2

    assert get_char_width("「") == 2
    assert get_char_width("┌") == 2
    assert get_char_width("■") == 2

    assert get_char_width("β") == 2
    assert get_char_width("Я") == 2
    assert get_char_width("Я", a=False) == 1

    assert get_char_width("\t") == 4
    assert get_char_width("\t", tab_width=8) == 8
    
    assert get_char_width(" ") == 1
    assert get_char_width("　") == 2
    assert get_char_width("\a") == 0
    assert get_char_width("\r") == 0
    assert get_char_width("\n") == 0


def test_composit():
    from machaon.cui import composit_text
    assert composit_text("aaa", 100) == "aaa"
    assert composit_text("1234567890A", 10) == "1234567890\nA"
    assert composit_text("壱弐参四五六", 11) == "壱弐参四五\n六"
    assert composit_text("1234567890ABCDEFGHIJabcde", 10) == "1234567890\nABCDEFGHIJ\nabcde"
    assert composit_text("1234567890\nABCDE", 10) == "1234567890\nABCDE"
    assert composit_text("あいうえおかきくけこやゆよ\nらりるれろ", 11) == "あいうえお\nかきくけこ\nやゆよ\nらりるれろ"
    assert composit_text("あいうえお\nかきくけこ\nやゆよ\nらりるれろ\n", 11) == "あいうえお\nかきくけこ\nやゆよ\nらりるれろ\n"


def test_composit_rect():
    from machaon.cui import composit_text
    assert composit_text("aaa", 5, fill=True) == "aaa  "
    assert composit_text("AAAAABBB", 5, fill="-") == "AAAAA\nBBB--"
    assert composit_text("AAAAABBB", 5, fill=True) == "AAAAA\nBBB  "
    assert composit_text("XXXZZZ", 5, first_indent=2, fill=True) == "  XXX\nZZZ  "
    assert composit_text("1234567890\nABCDE", 10, fill=True) == "1234567890\nABCDE     "
    assert composit_text("あいうえおかきくけこやゆよ\nらりるれろ", 11, fill=True) == "あいうえお \nかきくけこ \nやゆよ     \nらりるれろ "

def test_parserecord():
    from machaon.cui import parserecord
    assert parserecord("Name : package-name", ":", length=2) == ["Name", "package-name"]
    assert parserecord("", ":", length=2) == ["", ""]
    assert parserecord("mat, neko", ",", length=3, default=("", "", None)) == ["mat", "neko", None]
    assert parserecord("", ",", length=3, default=("", "", None)) == ["", "", None]
    assert parserecord("Name : package-name, waon", (":", ",")) == ["Name", "package-name", "waon"]
    assert parserecord("Name : package-name, waon", ("@", "@")) == ["Name : package-name, waon", "", ""]
    assert parserecord("Name : package-name, waon", ("@", ",")) == ["Name : package-name, waon", "", ""]



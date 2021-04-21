import pytest
import os

from machaon.types.file import TextFile
from machaon.types.shell import Path
from machaon.core.invocation import instant_return_test, instant_context

def test_construct(tmp_path):
    FILEPATH = __file__
    context = instant_context()
    context.new_type(TextFile)
    f = instant_return_test(context, FILEPATH, "TextFile").value
    assert isinstance(f, TextFile)
    assert isinstance(f.path(), Path)
    assert f.pathstr == FILEPATH

    p = tmp_path / "hello.txt"
    f = instant_return_test(context, p, "TextFile").value
    f.set_encoding("utf-8")
    assert f.encoding() == "utf-8"
    with f.open("w") as fi:
        fi.write("HELLO\n")
        fi.write("WORLD")
    assert f.text() == "HELLO\nWORLD"



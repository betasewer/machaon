import pytest
import os

from machaon.types.file import TextFile
from machaon.types.shell import Path
from machaon.core.invocation import instant_return_test, instant_context

def test_construct(tmp_path):
    FILEPATH = Path(__file__)
    context = instant_context()
    context.define_type(TextFile)
    f = instant_return_test(context, FILEPATH, "TextFile").value
    assert isinstance(f, TextFile)
    assert isinstance(f.path(), Path)
    assert f.pathstr == FILEPATH.get()

    p = Path(tmp_path) / "hello.txt"
    f = instant_return_test(context, p, "TextFile").value
    f.set_encoding("utf-8")
    assert f.encoding() == "utf-8"
    with f.open("w"):
        f.stream.write("HELLO\n")
        f.stream.write("WORLD")
    assert f.text() == "HELLO\nWORLD"



import pytest
import os

from machaon.types.file import TextFile
from machaon.types.shell import Path

def test_construct(tmp_path):
    FILEPATH = Path(__file__)
    f = TextFile(FILEPATH)
    assert isinstance(f, TextFile)
    assert isinstance(f.path(), Path)
    assert f.pathstr == FILEPATH.get()

    p = Path(tmp_path) / "hello.txt"
    f = TextFile(p)
    f.set_encoding("utf-8")
    assert f.encoding() == "utf-8"
    with f.open("w"):
        f.stream.write("HELLO\n")
        f.stream.write("WORLD")
    assert f.text() == "HELLO\nWORLD"



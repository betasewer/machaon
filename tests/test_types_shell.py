from doctest import master
import os

import pytest
from machaon.types.shell import Path

def test_path_concatenate():
    a = Path("desktop/folder")
    b = Path("subfolder/file.txt")
    c = a / b
    assert c.path() == os.path.join(a.path(), b.path())

def test_is_relative():
    assert Path("/a/bb/ccc/dddd").is_relative_to(Path("/a/bb/ccc"))
    assert not Path("/a/bb/ccc/dddd").is_relative_to(Path("/a/bb/ccc/eeeee"))
    assert not Path("/a/bb/ccc/dddd").is_relative_to(Path("/a/bb/ffffff"))

def test_path_split():
    assert Path("C:/desktop/folder").split() == ["C:/","desktop","folder"]
    assert Path("C:/desktop/folder/").split() == ["C:/","desktop","folder"]
    assert Path("D:/subfolder/file.txt").split() == ["D:/","subfolder","file.txt"]
    assert Path("/subfolder/file.txt").split() == ["/","subfolder","file.txt"]
    assert Path("subfolder/file.txt").split() == ["subfolder","file.txt"]

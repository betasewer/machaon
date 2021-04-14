import os

import pytest
from machaon.types.shell import Path

def test_path_concatenate():
    a = Path("desktop/folder")
    b = Path("subfolder/file.txt")
    c = a / b
    assert c.path() == os.path.join(a.path(), b.path())


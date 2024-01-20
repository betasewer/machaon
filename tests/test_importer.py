
import pkgutil
import os
import importlib
import sys
from machaon.types.shell import Path

from machaon.core.importer import walk_modules

def onerror(e):
    print(str(e))


def test_walk_modules():
    dir = Path(__file__).up().up()
    assert dir.name() == "machaon"
    
    for loader in walk_modules(dir):
        if loader.module_name == "machaon.types.string":
            break
    else:
        assert False

    # 同じモジュール
    from machaon.types.string import StrType
    loaded = [
        getattr(loader.module, "StrType", None),
        StrType
    ]
    assert loaded[0] is loaded[1]



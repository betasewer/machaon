
import pkgutil
import os
import importlib
import sys

from machaon.core.importer import walk_modules

def onerror(e):
    print(str(e))


def test_walk_modules():
    for loader in walk_modules(r"C:\codes\python\machaon"):
        if loader.module_name == "machaon.types.fundamental":
            break
    else:
        assert False

    # 同じモジュール
    from machaon.types.fundamental import StrType
    loaded = [
        getattr(loader.module, "StrType", None),
        StrType
    ]
    assert loaded[0] is loaded[1]






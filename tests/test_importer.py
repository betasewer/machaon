from machaon.types.shell import Path

from machaon.core.importer import walk_modules

def onerror(e):
    print(str(e))


def test_walk_modules():
    dir = Path(__file__).up().up()
    assert dir.name() == "machaon"
    
    for loader in walk_modules(dir):
        if loader.module_name == "machaon.core.importer":
            break
    else:
        assert False

    # 同一のシンボルを指す
    loaded = [
        getattr(loader.module, "walk_modules", None),
        walk_modules
    ]
    assert loaded[0] is loaded[1]



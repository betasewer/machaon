from machaon.core.importer import attribute_loader
from machaon.core.type.typedef import TypeDefinition, ClassDescriber


def _load_describer(describer):
    if isinstance(describer, str):
        return attribute_loader(describer)()
    else:
        return describer


def construct(type, *args):
    """ コンストラクタを呼び出す """
    t = _load_describer(type)
    return t.constructor(t, *args)

def stringify(type, *args):
    """ 文字列化する """
    t = _load_describer(type)
    return t.stringify(t, *args)

def pprint(type, app, *args):
    """ 表示する """
    t = _load_describer(type)
    return t.pprint(t, app, *args)

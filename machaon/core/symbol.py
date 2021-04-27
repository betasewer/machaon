from typing import Tuple
from collections import namedtuple

#
# 型名
#
#
class PythonBuiltinTypenames:
    literals = { 
        "str", "int", "bool", "float", "complex" 
    }
    dictionaries =  {
        "dict",
    }
    iterables = {
        "list", "tuple", "set", "bytes", 
    }

#
def normalize_typename(name: str) -> str:
    if not name[0].isupper():
        if name in PythonBuiltinTypenames.literals:
            name = name.capitalize() # ドキュメントとしても使うために、Pythonの組み込み型に限り小文字でも可とする
    bracket = name.find("[")
    if bracket != -1:
        name = name[:bracket]
    return name.replace("_","-")

#
def normalize_return_typename(name: str) -> Tuple[str, str]:
    if "[" in name:
        name1, _, name2 = name.partition("[")
        typename = normalize_typename(name1)
        name2 = name2.rstrip("]")
        secondtypename = normalize_typename(name2) if name2 else ""
    else:
        typename = normalize_typename(name)
        secondtypename = ""
    
    return typename, secondtypename


# 型名の間違い
class BadTypename(Exception):
    pass


#
# メソッド名
#
def normalize_method_name(name):
    """ メソッド名ではアンダースコアのかわりにハイフンを使う """
    return name.replace("_","-")

def normalize_method_target(name):
    """ メソッド名からロードする実際の関数名に戻す """
    return name.replace("-","_")

# メソッド名の間違い
class BadMethodName(Exception):
    pass

#
# オブジェクト名
#
def is_valid_object_bind_name(name):
    """ 予約されたオブジェクト名を禁止する """
    if not name:
        return False
    if name == "_":
        return False
    if name.isdigit(): # 予約されている
        return False
    if any(x for x in name if not x.isprintable()):
        return False
    return True

# 不正な名前・予約された名前を使おうとした
class BadObjectBindName(Exception):
    pass

#
def full_qualified_name(t):
    mod = t.__module__
    if mod is None or mod == len.__module__:
        return t.__qualname__
    else:
        return mod + "." + t.__qualname__


#
SIGIL_DEFAULT_RESULT = "-"



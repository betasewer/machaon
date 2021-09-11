from typing import Tuple

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

def normalize_typename(name: str) -> str:
    if not name[0].isupper():
        if name in PythonBuiltinTypenames.literals:
            name = name.capitalize() # ドキュメントとしても使うために、Pythonの組み込み型に限り小文字でも可とする
    bracket = name.find("[")
    if bracket != -1:
        name = name[:bracket]
    return name.replace("_","-")

def is_valid_typename(name: str):
    if not name[0].isupper():
        if name not in PythonBuiltinTypenames.literals:
            return False
    return True

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

# 存在しないメソッド名へのエラー
class BadMethodName(Exception):
    def __str__(self):
        attrname = self.args[0]
        typename = self.args[1]
        return "メソッド {}::{} は存在しません".format(typename, attrname)

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
# メッセージで用いられる記号
#
SIGIL_OBJECT_ID = "@"
SIGIL_OBJECT_LAMBDA_MEMBER = "."
SIGIL_OBJECT_ROOT_MEMBER = "@"
SIGIL_SCOPE_RESOLUTION = "/"
SIGIL_PYMODULE_DOT = "."
SIGIL_END_OF_KEYWORDS = ";"
SIGIL_DISCARD_MESSAGE = "."
SIGIL_DEFAULT_RESULT = "-"

QUOTE_ENDPARENS = {
    "[" : "]",
    "{" : "}",
    "<" : ">",
    "(" : ")",
    "（" : "）",
    "【" : "】",
    "《" : "》",
}

#
# 
#
def summary_escape(s:str):
    return s.translate(SUMMARY_ESCAPE_TRANS)

SUMMARY_ESCAPE_TRANS = str.maketrans({
    0x00 : "\\0",
    0x01 : "[SOH]",
    0x02 : "[STX]",
    0x03 : "[ETX]",
    0x04 : "[EOT]",
    0x05 : "[ENQ]",
    0x06 : "[STX]",
    0x07 : "\\a",
    0x08 : "\\b",
    0x09 : "\\t",
    0x0A : "\\n",
    0x0B : "\\v",
    0x0C : "\\f",
    0x0D : "\\r",
    0x0E : "[SO]",
    0x0F : "[SI]",
    0x10 : "[DLE]",
    0x11 : "[DC1]",
    0x12 : "[DC2]",
    0x13 : "[DC3]",
    0x14 : "[DC4]",
    0x15 : "[NAK]",
    0x16 : "[SYN]",
    0x17 : "[ETB]",
    0x18 : "[CAN]",
    0x19 : "[EM]",
    0x1A : "[SUB]",
    0x1B : "[ESC]",
    0x1C : "[FS]",
    0x1D : "[GS]",
    0x1E : "[RS]",
    0x1F : "[US]",
    0x7F : "[DEL]",
})


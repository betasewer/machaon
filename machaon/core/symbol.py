from select import select
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
    if hasattr(t, "__module__"):
        mod = t.__module__
    else:
        mod = None
    if hasattr(t, "__qualname__"):
        n = t.__qualname__
    elif hasattr(t, "__name__"):
        n = t.__name__
    else:
        raise ValueError("No __qualname__ or __name__ property")
    if mod is None or mod == len.__module__:
        return n
    else:
        return mod + "." + n


# メッセージで用いられる記号
SIGIL_OBJECT_ID = "@"
SIGIL_OBJECT_LAMBDA_MEMBER = "."
SIGIL_OBJECT_ROOT_MEMBER = "@"
SIGIL_SCOPE_RESOLUTION = "/"

SIGIL_SELECTOR_NEGATE_RESULT        = "!"
SIGIL_SELECTOR_REVERSE_ARGS         = "~"
SIGIL_SELECTOR_BASIC_RECIEVER       = "`"
SIGIL_SELECTOR_TRAILING_ARGS        = ":"
SIGIL_SELECTOR_CONSUME_ARGS         = ":>"
SIGIL_SELECTOR_SHOW_HELP            = "?"

SIGIL_END_TRAILING_ARGS = ";"
SIGIL_DISCARD_MESSAGE = "."

SIGIL_TYPE_INDICATOR = "::"
QUOTE_ENDPARENS = {
    "[" : "]",
    "{" : "}",
    "<" : ">",
    "(" : ")",
    "（" : "）",
    "【" : "】",
    "《" : "》",
}


# 型名
SIGIL_PYMODULE_DOT = "."
SIGIL_SUBTYPE_SEPARATOR = ":"
SIGIL_SUBTYPE_UNION = "+"

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

#
# 実行時に読み込まれるモジュール
#
BootModuleNames = (
    "string", "numeric", "dateandtime", "shell", "file"
)

#
# ビットフラグ
#
def display_bitflag(dictionary, prefix, code):
    """ 
    ビットフラグを変数名で表示する
    Params:
        dictionary(Dict[int,Any]): 辞書。globalsを渡す
        prefix(str): 変数名のprefix
        code(int): フラグの値
    """
    names = []
    c = code
    for k, v in dictionary.items():
        if k.startswith(prefix) and v & c:
            names.append(k)
            c = (c & ~v)
    if c != 0:
        names.append("0x{0X}".format(c))
    return names

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


# デスクライバを指定した型名
class QualTypename:
    def __init__(self, typename, describername=None):
        self.typename = typename
        self.describer = describername

    @classmethod
    def parse(cls, s):
        n, sep, d = s.partition(SIGIL_MODULE_INDICATOR)
        if sep:
            return cls(n, d)
        else:
            return cls(s, None)

    def stringify(self):
        if self.describer is not None:
            return self.typename + SIGIL_MODULE_INDICATOR + self.describer
        else:
            return self.typename
        
    def is_qualified(self):
        return self.describer is not None


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
def get_module_attr(t):
    if hasattr(t, "__module__"):
        mod = t.__module__
        if mod != len.__module__:
            return mod
    return None

def get_name_attr(t, fallback=False):
    if hasattr(t, "__qualname__"):
        return t.__qualname__
    elif hasattr(t, "__name__"):
        return t.__name__
    elif not fallback:
        raise ValueError("No __qualname__ or __name__ property in '{}'".format(t))
    else:
        return None

def full_qualified_name(t, fallback=False):
    n = get_name_attr(t, fallback)
    if n is None:
        return None
    mod = get_module_attr(t)
    if mod is None:
        return n
    else:
        return mod + "." + n

def disp_qualified_name(t):
    n = get_name_attr(t, fallback=True)
    if n is None:
        n = repr(t)
    mod = get_module_attr(t)
    if mod is None:
        return n
    else:
        return "{0}:{1}".format(n, mod)


# メッセージで用いられる記号
SIGIL_OBJECT_ID = "@"
SIGIL_OBJECT_LAMBDA_MEMBER = "."
SIGIL_OBJECT_ROOT_MEMBER = "@"
SIGIL_OBJECT_PREVIOUS = "_"
SIGIL_SCOPE_RESOLUTION = "/"

SIGIL_SELECTOR_NEGATE_RESULT        = "!"
SIGIL_SELECTOR_REVERSE_MESSAGE      = "~"
SIGIL_SELECTOR_BASIC_RECIEVER       = "`"
SIGIL_SELECTOR_TRAILING_ARGS        = ":"
SIGIL_SELECTOR_CONSUME_ARGS         = ">"
SIGIL_SELECTOR_SHOW_HELP            = "?"

SIGIL_END_TRAILING_ARGS = ":."
SIGIL_DISCARD_MESSAGE = "."

SIGIL_RETURN_TYPE_INDICATOR = "::"
QUOTE_ENDPARENS = {
    "[" : "]",
    "{" : "}",
    "<" : ">",
    "(" : ")",
    "（" : "）",
    "【" : "】",
    "《" : "》",
}

SIGIL_BEGIN_USER_QUOTER = "--"
SIGIL_LINE_QUOTER = "->"

# 型名
SIGIL_PYMODULE_DOT = "."
SIGIL_MODULE_INDICATOR = ":"
SIGIL_SUBTYPE_SEPARATOR = "+"

# 定義ドキュメント
SIGIL_DEFINITION_DOC = "@"


#
#
#
def is_modifiable_selector(selector):
    # 長さ1以下は不可とする
    if len(selector) < 2:
        return False
    # 端が記号のセレクタはモディファイアとの区別がつかないのでモディファイアを無視する
    # かわりにブロックモディファイアを使用できる
    from string import punctuation
    if selector[0] in punctuation:
        return False
    if selector[-1] in punctuation:
        return False
    return True

def is_triming_control_char(code):
    if 0x00 <= code and code < 0x09:
        return True
    if 0x10 <= code and code < 0x20:
        return True
    if 0x7F == code:
        return True
    return False


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
DefaultModuleNames = (
    "types.string", "types.numeric", "types.dateandtime", 
    "types.shell", "types.file", "types.tuple",
    "flow.flow", "flow.flux",
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


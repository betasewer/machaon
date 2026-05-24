
#
# オブジェクトの名前
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


#
# 制御記号
#
def escape_control_chars(s:str):
    return s.translate(CONTROL_CHARS_ESCAPE_TRANS)

CONTROL_CHARS_ESCAPE_TRANS = str.maketrans({
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
# ビットフラグ
#
class BitFlags:
    def __init__(self, prefix, dictionary):
        """
        Params:
            prefix(str): 変数名のprefix
            dictionary(Dict[int,str]): 辞書。globals()を渡せばよい
        """
        self.prefix = prefix
        self.dict = {}
        for k, v in dictionary.items():
            if k.startswith(prefix):
                self.dict[k] = v
    
    def display(self, code: int) -> list[str]:
        """ ビットフラグを変数名の集合で表示する """
        names = []
        c = code
        for k, v in self.dict.items():
            if (v & c) > 0:
                names.append(k)
                c = (c & ~v)
        if c != 0:
            names.append("0x{0X}".format(c))
        return names



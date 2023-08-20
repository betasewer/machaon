from machaon.core.symbol import (
    SIGIL_MODULE_INDICATOR, SIGIL_SCOPE_RESOLUTION, SIGIL_PYMODULE_DOT, SIGIL_SUBTYPE_SEPARATOR,
    BadTypename, full_qualified_name, disp_qualified_name, PythonBuiltinTypenames
)
from machaon.core.type.decl import TypeDecl

#
class TypeDeclError(Exception):
    """ 構文エラー """
    def __init__(self, itr, err) -> None:
        super().__init__(itr, err)
    
    def __str__(self):
        itr = self.args[0]
        pos = itr.current_preview()
        return "型宣言の構文エラー（{}）: {}".format(self.args[1], pos)


#
# 型宣言パーサコンビネータ 
#
'''
<body> ::= <fulltypename> | <fulltypename> "|" <fulltypename>
<fulltypename> ::= <subtype> | <subtype> ":" <moduleexpr>
<subtype> ::= <expr> | <expr> "+" <expr>
<expr> ::= <type100> | <type110> | <type111> | <type101> | <type100a>
<type100> ::= <name>
<type110> ::= <name> "[" <typeargs> "]"
<type111> ::= <name> "[" <typeargs> "]" "(" <ctorargs> ")"
<type101> ::= <name> "[]"  "(" <ctorargs> ")"
<type100a> ::= <name> "[]"
<typeargs> ::= <body> | <body> "," <typeargs>
<ctorargs> ::= <ctorvalue> | <ctorvalue> "," <ctorargs>
<name> ::= ([a-z] | [A-Z] | [0-9] | "_" | "/" | ".")+
<ctorvalue> ::= ([a-z] | [A-Z] | [0-9] | "_" | "/" | "." | ":")+
<moduleexpr> ::= <name>
'''
def parse_typedecl(decl):
    """ 開始地点 """
    itr = _typedecl_Iterator(decl)
    decl = _typedecl_body(itr)
    if not itr.eos():
        itr.advance()
        raise TypeDeclError(itr, "以降を解釈できません")
    return decl

def _typedecl_body(itr):
    union = []
    while not itr.eos():
        expr = _typedecl_fulltypename(itr)
        union.append(expr)
        ch, pos = itr.advance()
        if itr.eos():
            break
        elif ch == "|":
            continue
        else:
            itr.back(pos)
            break
    if len(union)==1:
        return union[0]
    elif not union:
        raise TypeDeclError(itr, "型がありません")
    else:
        return TypeDecl("Union", union)

def _typedecl_fulltypename(itr):
    targettype = None
    describername = None
    targettype = _typedecl_subtype(itr)

    while not itr.eos():
        ch, pos = itr.advance()
        if itr.eos():
            break
        elif ch == SIGIL_MODULE_INDICATOR:
            describername = _typedecl_name(itr)
        else:
            itr.back(pos)
            break

    if targettype is None:
        raise TypeDeclError(itr, "モジュールに対する型が指定されていません")
    if describername is not None:
        targettype.with_describer_name(describername)
    return targettype

def _typedecl_subtype(itr):
    # サブタイプの記述
    types = []
    while not itr.eos():
        expr = _typedecl_expr(itr)
        types.append(expr) 
        ch, pos = itr.advance()
        if itr.eos():
            break
        elif ch == SIGIL_SUBTYPE_SEPARATOR:
            if len(types) > 1:
                raise TypeDeclError(itr, "サブタイプは1つしか指定できません")
            continue
        else:
            itr.back(pos)
            break
    if len(types)==1:
        return types[0]
    elif not types:
        raise TypeDeclError(itr, "型がありません")
    else:
        return TypeDecl("$Sub", types)

def _typedecl_expr(itr):
    # 型名
    name = _typedecl_name(itr)
    if not name:
        raise TypeDeclError(itr, "型名がありません")

    typeargs = []
    ctorargs = []
    while True:
        # 型引数
        ch, pos = itr.advance()
        if itr.eos():
            break
        elif ch == "[":
            ch2, pos2 = itr.advance()
            if ch2 == "]":
                typeargs = [] # 空かっこを許容
            else:
                itr.back(pos2)
                typeargs = _typedecl_typeargs(itr)
        else:
            itr.back(pos)
            break

        # コンストラクタ引数
        ch, pos = itr.advance()
        if itr.eos():
            break
        elif ch == "(":
            ctorargs = _typedecl_ctorargs(itr)
        else:
            itr.back(pos)

        break
    
    return TypeDecl(name, typeargs, ctorargs)

def _typedecl_typeargs(itr):
    args = []
    while True:
        expr = _typedecl_body(itr)
        args.append(expr)
        ch, pos = itr.advance()
        if ch == ",":
            continue
        elif ch == "]":
            break
        elif itr.eos():
            raise TypeDeclError(itr, "型引数リストで予期せぬ終わりに到達")
        else:
            raise TypeDeclError(itr, "予期せぬ文字です")
    return args

def _typedecl_ctorargs(itr):
    args = []
    while True:
        value = _typedecl_ctorvalue(itr)
        args.append(value)
        ch, pos = itr.advance()
        if ch == ",":
            continue
        elif ch == ")":
            break
        elif itr.eos():
            raise TypeDeclError(itr, "コンストラクタ引数リストで予期せぬ終わりに到達")
        else:
            raise TypeDeclError(itr, "予期せぬ文字です")
    return args

def is_typename_char(ch):
    return ch.isidentifier()

digits = "0123456789"
def is_typename_continue_char(ch):
    return is_typename_char(ch) or ch == SIGIL_SCOPE_RESOLUTION or ch == SIGIL_PYMODULE_DOT or ch in digits

def _typedecl_name(itr):
    # Pythonの識別名で使える文字 + SIGIL_SCOPE_RESOLUTION + SIGIL_PYMODULE_DOT
    name = ""
    while not itr.eos():
        ch, pos = itr.advance()
        if ch and len(name) == 0 and is_typename_char(ch):
            name += ch
        elif ch and len(name) > 0 and is_typename_continue_char(ch):
            name += ch
        else:
            itr.back(pos)
            break
    return name

def _typedecl_ctorvalue(itr):
    # 構文用の文字以外は全て受け入れる
    name = ""
    while not itr.eos():
        ch, pos = itr.advance()
        if ch is None or ch in ("),"): 
            itr.back(pos)
            break
        else:
            name += ch
    return name

class _typedecl_Iterator():
    def __init__(self, s):
        self._s = s
        self._i = -1
    
    def eos(self):
        return self._i is None

    def advance(self):
        # Returns: Tuple[char, lastposition]
        if self.eos(): return None, None # eos
        li = self._i
        while True:
            self._i += 1
            if self._i >= len(self._s):
                self._i = None # reach eos
                return None, li
            ch = self._s[self._i]
            if not ch.isspace(): # 空白は読み捨てる
                return ch, li
    
    def back(self, pos):
        if self.eos(): return # eos
        self._i = pos
    
    def current_preview(self):
        if self.eos(): return self._s + "<<<"
        return self._s[0:self._i] + " >>>" + self._s[self._i] + "<<< " + self._s[self._i+1:]


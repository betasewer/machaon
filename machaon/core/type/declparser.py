from machaon.core.symbol import (
    SIGIL_DESCRIBER_INDICATOR, SIGIL_PYMODULE_DOT
)
from machaon.core.type.decl import TypeDecl, TypeDeclError, ModuleTypeDecl, SpecialTypeDecls, PythonTypeDecl


#
# 型宣言パーサコンビネータ 
#
'''
<body> ::= <fulltypename> | <fulltypename> "|" <fulltypename>
<fulltypename> ::= <expr> | <expr> ":" <name>
<expr> ::= <type0> | <type1> | <type0a>
<type0> ::= <name>
<type0a> ::= <name> "[]"
<type1> ::= <name> "[" <typeargs> "]"
<typeargs> ::= <typearg> | <typearg> "," <typeargs>
<typearg> ::= <typearg0> | <typearg1> | <typearg0a>
<typearg0> ::= <symbol>
<typearg0a> ::= <symbol> "[]"
<typearg1> ::= <symbol> "[" <typeargs> "]"
<name> ::= ([a-z] | [A-Z] | [0-9] | "_" | "/" | ".")+
<symbol> ::= ([a-z] | [A-Z] | [0-9] | "_" | "/" | "." | ":")+
'''
def parse_typedecl(decl, resolver=None):
    """ 開始地点 """
    itr = TypeDecl_ParseIterator(decl, resolver)
    decl = _typedecl_body(itr)
    if not itr.eos():
        itr.advance()
        raise TypeDeclError(itr, "以降を解釈できません")
    return decl


class TypeDecl_ParseIterator:
    def __init__(self, decl, resolver):
        self._s = decl
        self._i = -1
        self.resolver = resolver
    
    def eos(self):
        return self._i is None
    
    def pos(self):
        return self._i

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

    def new_decl(self, typename, children):
        """ 型宣言のインスタンスを作る """
        if typename in SpecialTypeDecls:
            # 特殊型?
            return SpecialTypeDecls[typename].bind(children)
        elif SIGIL_PYMODULE_DOT in typename: 
            # Python型?
            return PythonTypeDecl(typename, children)
        else:
            # 普通の型
            return ModuleTypeDecl(typename, children, self.resolver)


#
#
#
def _typedecl_body(itr:TypeDecl_ParseIterator, *, astypearg=False):
    union = []
    while not itr.eos():
        if astypearg:
            expr = _typedecl_typearg_expr(itr)
        else:
            expr = _typedecl_fullnamed_expr(itr)
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
        return itr.new_decl("Union", union)

def _typedecl_fullnamed_expr(itr:TypeDecl_ParseIterator):
    targettype = None
    describername = None
    targettype = _typedecl_expr(itr)

    while not itr.eos():
        ch, pos = itr.advance()
        if itr.eos():
            break
        elif ch == SIGIL_DESCRIBER_INDICATOR:
            describername = _typedecl_name(itr)
        else:
            itr.back(pos)
            break

    if targettype is None:
        raise TypeDeclError(itr, "モジュールに対する型が指定されていません")
    if describername is not None:
        targettype.with_describer_name(describername)
    return targettype

def _typedecl_expr(itr:TypeDecl_ParseIterator):
    # 型名
    name = _typedecl_name(itr)
    if not name:
        raise TypeDeclError(itr, "型名がありません")
    args = _typedecl_typearglist(itr)
    return itr.new_decl(name, args)

def _typedecl_typearglist(itr:TypeDecl_ParseIterator):
    # []でくくられた型名リスト
    args = []
    while True:
        # 型引数
        ch, pos = itr.advance()
        if itr.eos():
            break
        elif ch == "[":
            ch2, pos2 = itr.advance()
            if ch2 == "]":
                args = [] # 空かっこを許容
            else:
                itr.back(pos2)
                args = _typedecl_typeargs(itr)
        else:
            itr.back(pos)
            break
    return args

def _typedecl_typeargs(itr:TypeDecl_ParseIterator):
    args = []
    while True:
        value = _typedecl_body(itr, astypearg=True)
        if value is not None:
            args.append(value)
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

def _typedecl_typearg_expr(itr:TypeDecl_ParseIterator):  
    # 型引数リストがついている  
    symbol = _typedecl_typearg_symbol(itr)
    if not symbol:
        raise TypeDeclError(itr, "型名がありません")
    args = _typedecl_typearglist(itr)
    return itr.new_decl(symbol, args)

def is_nontypename_char(ch):
    # 非型引数の表現で使える文字
    return ch not in "|[],"

def is_typename_first_char(ch):
    # 型名の先頭に使用可能な文字
    return ch.isidentifier()

def is_typename_continue_char(ch):
    # 型名の先頭以降使える文字 - 識別子文字、数字、ピリオド
    return is_typename_first_char(ch) or (0x30 <= ord(ch) and ord(ch) <= 0x39) or ch in (SIGIL_PYMODULE_DOT,)

def _typedecl_name(itr):
    name = ""
    while not itr.eos():
        ch, pos = itr.advance()
        if ch and len(name) == 0 and is_typename_first_char(ch):
            name += ch
        elif ch and len(name) > 0 and is_typename_continue_char(ch):
            name += ch
        else:
            itr.back(pos)
            break
    return name

def _typedecl_typearg_symbol(itr):
    # 型名、あるいは非型の値
    value = ""
    while True:
        ch, pos = itr.advance()
        if not is_nontypename_char(ch): # 型名に使用できる文字も含まれている
            itr.back(pos)
            break
        value += ch
    return value

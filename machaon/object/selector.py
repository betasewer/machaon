from machaon.object.method import normalize_method_target, Method
from machaon.object.invocation import (
    INVOCATION_NEGATE_RESULT, INVOCATION_REVERSE_ARGS,
    TypeMethodInvocation,
    InstanceMethodInvocation,
    StaticMethodInvocation,
    load_member_from_module
)
from machaon.object.importer import maybe_import_target, import_member

#
#
# セレクタ
#
#
SIGIL_IMPORT_METHOD = "<>"

# 
def parse_invocation_modifier(expression, modifier=0):
    expr = expression
    modbits = modifier

    if expr.startswith("~"):
        modbits |= INVOCATION_REVERSE_ARGS
        expr = expr[1:]
    
    if expr.startswith("!"):
        modbits |= INVOCATION_NEGATE_RESULT
        expr = expr[1:]
    
    if expr.startswith("not-"):
        modbits |= INVOCATION_NEGATE_RESULT
        expr = expr[4:]
        
    if len(expression) == 0:
        modbits = modifier
        expr = expression
    
    return expression, modbits

#
#
#
def select_type_method(name, typetraits, *, modbits=None):
    if modbits is None:
        name, modbits = parse_invocation_modifier(name)

    meth = typetraits.get_method(name)
    if meth is not None:
        return TypeMethodInvocation(meth, modbits)
    
    return None

#
#
#
def select_method(name, typetraits, *, arity=None, return_type=None, modbits=None):
    if modbits is None:
        name, modbits = parse_invocation_modifier(name)

    # 外部関数
    if maybe_import_target(name):
        modname, modbits = parse_invocation_modifier(name)
        modfn = import_member(modname)
        return StaticMethodInvocation(modfn, arity, modbits)

    # 型メソッド
    if typetraits is not None:
        inv = select_type_method(name, typetraits, modbits=modbits)
        if inv is not None:
            return inv
    
    # 演算子の記号を関数に
    if name in operator_selectors:
        name = operator_selectors[name]
    
    # グローバル定義の関数
    from machaon.object.generic import resolve_generic_method
    genfn = resolve_generic_method(name)
    if genfn is not None:
        return StaticMethodInvocation(genfn, arity, modbits)
    
    # インスタンスメソッド
    return InstanceMethodInvocation(name, arity, modbits)


#
# 演算子とセレクタの対応
#
operator_selectors = {
    # operator methods
    "==" : "equal",
    "!=" : "not-equal",
    "<=" : "less-equal",
    "<" : "less",
    ">=" : "greater-equal",
    ">" : "greater",
    "+" : "add",
    "-" : "sub",
    "*" : "mul",
    "**" : "pow",
    "/" : "div",
    "//" : "floordiv",
    "%" : "mod",
    "&" : "bitand",
    "^" : "bitxor",
    "|" : "bitor",
    "~" : "bitinv",
    ">>" : "rshift",
    "<<" : "lshift",
    # generic methods
    "&&" : "and", 
    "||" : "or",  
}

#
#
#
#
#
def select_left_operand():
    pass


def select_right_operand():
    pass


import ast
from typing import Dict, Any, List, Sequence

from machaon.object.variable import variable, variable_defs

#
class BadExpressionError(Exception):
    pass

#
# 1. トークンへの変換
#

TOKEN_TERM = 0x01
TOKEN_BLOCK_BEGIN = 0x02
TOKEN_TERM_END = 0x04
TOKEN_BLOCK_END = 0x10


def tokenize(expression):
    buffer = []
    def _flush(buf):
        if buf:
            yield "".join(buf)
            buf.clear()
    
    yield TOKEN_BLOCK_BEGIN

    for ch in expression:
        if ch == "(":
            yield from _flush(buffer)
            yield TOKEN_BLOCK_BEGIN
        elif ch == ")":
            yield from _flush(buffer)
            yield TOKEN_BLOCK_END
        else:
            buffer.append(ch)

    yield from _flush(buffer)
    yield TOKEN_BLOCK_END


#
# 2. 構文木の構築
#
def build_ast(cxt, tokens):
    blockstack = []
    for token in tokens:
        if token == TOKEN_BLOCK_BEGIN:
            blockstack.append([])

        elif token == TOKEN_BLOCK_END:
            if not blockstack:
                raise BadExpressionError("Could not find beginning of block")

            newblock = blockstack.pop()

            # 式を解析する
            expr = cxt.parse(*newblock)
            if not blockstack:
                # 全体のブロックの解析が終わった
                return expr
            
            # 上位のブロックの要素として追加する
            blockstack[-1].append(expr)
        
        else:
            # 文字部分を解析する
            if not blockstack:
                raise BadExpressionError("Could not find beginning of block")

            blockstack[-1].append(token)
    
    raise BadExpressionError("Could not find end of block")

#
# 2-1. 式を解析する
#
class parser_context:
    def __init__(self, 
            typelib=None, 
            variablelib=None
        ):
        self.typelib = typelib
        self.varlib: variable_defs = variablelib
        self.related_vars = []

    # 2-1. 式の解析
    def parse(self, *tokens):
        operands = []
        for token in tokens:
            if isinstance(token, expression):
                operands.append(token)
            elif isinstance(token, str):
                if len(operands)>=2: # LEFT OP >RIGHT<
                    operands.append(token)
                else:
                    toks = token.split()
                    operands.extend(toks)
        
        if len(operands) == 1:
            args = [operands[0]]
            opr = None
        elif len(operands) == 2:
            args = [operands[0]]
            opr = operands[1]
        elif len(operands) >= 3:
            args = [operands[0], *operands[2:]]
            opr = operands[1]
        else:
            raise BadExpressionError("empty expression")

        if opr is not None:
            opr = self.parse_operator(opr, args[0])

        args = [self.parse_literal(x) for x in args]
        return expression(opr, args)

    # 2-2. リテラルの分析
    def parse_literal(self, s):
        # 1. Pythonのリテラルとみなす
        try:
            return ast.literal_eval(s)
        except ValueError:
            pass
        
        # 2. 述語とみなす
        if self.varlib is not None:
            va = self.varlib.get(s)
            if va is not None:
                self.related_vars.append(va.name)
                return va

        # 3. 型定義リテラル
    
        # 10. 文字列とみなす
        return s

    # 2-3. 演算子の分析
    def parse_operator(self, name, left):
        # 左辺値の型に定義された演算子
        mood = None # type_traits
        if isinstance(left, variable):
            mood = left.get_type()
        elif self.typelib is not None:
            typename = str(left)
            mood = self.typelib.get(typename)
        
        # オペレータ名を取り出す
        name, modbits = parse_operator_name(name)

        # 関数を取得する
        opr = resolve_operator(mood, name)
        if opr is None:
            opr = lhs_method(name)

        # 修飾語を適用する
        opr = modify_operator(opr, modbits)
        return opr
    
    #
    def get_related_variables(self):
        return self.related_vars

#
#
#
class expression():
    def __init__(self, opr, args):
        self.opr = opr
        self.args = args
    
    def eval(self, evalcontext):
        args = []
        for a in self.args:
            if isinstance(a, expression):
                ev = a.eval(evalcontext)
            elif isinstance(a, variable):
                ev = evalcontext.eval_variable(a)
            else:
                ev = a
            args.append(ev)

        ret = self.opr(*args)
        return ret
    
    def S(self, *, debug_operator=False):
        # for debug purpose
        args = []
        for x in self.args:
            if isinstance(x, expression):
                args.append(x.S(debug_operator=debug_operator))
            elif isinstance(x, str):
                args.append("'{}'".format(x))
            else:
                args.append(str(x))
        
        if debug_operator:
            opr = detailed_operator_name(self.opr)
        elif hasattr(self.opr, "__name__"):
            opr = self.opr.__name__
        else:
            opr = str(self.opr)
        return "({})".format(" ".join([opr, *args]))

#
#
#
OPERATION_REVERSE = 0x1
OPERATION_NEGATE = 0x2

# Python標準のオーバーロード可能な演算子
std_operator_names = {
    "==" : "eq",
    "!=" : "ne",
    "<=" : "le",
    "<" : "lt",
    ">=" : "ge",
    ">" : "gt",
    "in" : "~contains",
    "+" : "add",
    "-" : "sub",
    "*" : "mul",
    "**" : "pow",
    "/" : "truediv",
    "%" : "mod",
    "&" : "and_",
    "^" : "xor_",
    "|" : "or_",
    ">>" : "rshift",
    "<<" : "lshift",
    "~" : "invert",
}
# オーバーロード不可能な演算子や、その他の組み込み関数を提供
def logical_and(l, r):
    return l and r

def logical_or(l, r):
    return l or r

def string_slice(s, b=None, e=None):
    return s[b:e]

builtin_operators = {
    "&&" : logical_and,
    "and" : logical_and,
    "||" : logical_or,
    "or" : logical_or,
    "length" : len,
    "slice" : string_slice,
}

#
def parse_operator_name(expression):
    bits = 0

    if len(expression)>1:
        if expression.startswith("~"):
            bits |= OPERATION_REVERSE
            expression = expression[1:]
        
        if expression.startswith("!"):
            bits |= OPERATION_NEGATE
            expression = expression[1:]

    operator_name = expression

    if expression in std_operator_names:
        operator_name = std_operator_names[expression]
    
    operator_name = operator_name.replace("-","_")
    return operator_name, bits

#
def modify_operator(operator, bits):
    opr = operator

    if bits & OPERATION_REVERSE:
        def rev(fn):
            def _rev(*a):
                return fn(*reversed(a))
            return _rev
        opr = rev(opr)

    if bits & OPERATION_NEGATE:
        def neg(fn):
            def _neg(*a):
                return not fn(*a)
            return _neg
        opr = neg(opr)
    
    return opr

#
def resolve_operator(mood, name):
    # 組み込みの演算子
    if name in builtin_operators:
        return builtin_operators[name]

    # 型に定義された演算子
    if mood is not None:
        opr = mood.get_operator(name)
        if opr is not None:
            return opr
    
    # 標準の演算子
    import operator
    opr = getattr(operator, name, None)
    if opr is not None:
        return opr
    opr = getattr(operator, name+"_", None) # "is" で "is_" にマッチさせる
    if opr is not None:
        return opr
    
    return None

# 左辺値に定義されたメソッドを呼び出す
class lhs_method:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "<lhs_method '{}'>".format(self.name)

    def __call__(self, left, *args):
        if not hasattr(left, self.name):
            raise BadExpressionError("value '{}' has no method like '{}'".format(left, self.name))
        return getattr(left, self.name)(*args)

# デバッグ用に演算子の名前を表示する
def detailed_operator_name(opr):
    if isinstance(opr, lhs_method):
        return ".".join(["lhs_method", opr.name])

    mod = opr.__module__
    if mod == "_operator":
        mod = "operator"
    elif not mod:
        mod = "builtin"
    elif mod.startswith("machaon.object.operation"):
        mod = "mbuiltin"

    return ".".join([mod, opr.__name__])
    
#
#
#
class eval_context():
    def eval_variable(self, va: variable):
        raise NotImplementedError()

# 変数を参照されるたびに計算する
class item_eval_context(eval_context):
    def __init__(self, item):
        self.item = item
    
    def eval_variable(self, va: variable):
        value = va.predicate.get_value(self.item)
        return value

# あらかじめ計算された値を取り出す
class valuemap_eval_context(eval_context):
    def __init__(self, valuemap: Dict[str, Any]):
        self.valuemap = valuemap
    
    def eval_variable(self, va: variable):
        if va.name in self.valuemap:
            return self.valuemap[va.name]
        raise BadExpressionError("述語'{}'に対する値がありません".format(va.name))

#
# エントリクラス・関数
#
class operation():
    def __init__(self, expr, related_variables):
        self.expr = expr
        self.related_variables = related_variables
    
    def get_related_variables(self):
        return self.related_variables

    def __call__(self, evalcontext: eval_context):
        return self.expr.eval(evalcontext)

# 式からパースする
def parse_operation(expr: str, type_lib, variable_lib) -> operation:
    tokens = tokenize(expr)
    cxt = parser_context(type_lib, variable_lib)
    expr = build_ast(cxt, tokens)
    return operation(expr, cxt.get_related_variables())

# 実行コンテキストをつくる
class variable_valuerow_def:
    #
    class indices():
        def __init__(self, indicemap):
            self.indicemap = indicemap
        
        def make_context(self, values: List[Any]) -> eval_context:
            valuemap = {k:values[i] for k,i in self.indicemap.items()}
            return valuemap_eval_context(valuemap)

    def __init__(self, variables: Sequence[variable]):
        self.variables: List[variable] = []
        self.variables.extend(variables)
    
    # 登録し、キャッシュのインデックスを返す
    def register_variables(self, vas): # type: (Sequence[variable]) -> variable_valuerow_def.indices
        indicemap: Dict[str, int] = {}
        for va in vas:
            for i, x in enumerate(self.variables):
                if va.name == x.name:
                    index = i
                    break
            else:
                self.variables.append(va)
                index = len(self.variables)-1

            indicemap[va.name] = index

        return variable_valuerow_def.indices(indicemap)

    # 値を計算する
    def make_valuerow(self, item) -> List[Any]:
        row: List[Any] = []
        for va in self.variables:
            value = va.make_value(item)
            row.append(value)
        return row
    
    def get_variables(self):
        return self.variables


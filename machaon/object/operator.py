
#
#
#
class BadOperatorError(Exception):
    pass

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

# オーバーロード不可能な演算子
def logical_and(l, r):
    return l and r

def logical_or(l, r):
    return l or r

builtin_operators = {
    "&&" : logical_and,
    "and" : logical_and,
    "||" : logical_or,
    "or" : logical_or,
}


#
# 演算子への修飾指示
#

OPERATION_REVERSE = 0x1
OPERATION_NEGATE = 0x2

# 文字列から解析
def parse_operator_expression(expression, left_operand_type):
    modbits = 0

    if len(expression)>1:
        if expression.startswith("~"):
            modbits |= OPERATION_REVERSE
            expression = expression[1:]
        
        if expression.startswith("!"):
            modbits |= OPERATION_NEGATE
            expression = expression[1:]

    operator_name = expression

    # 記号から関数名へ 
    if expression in std_operator_names:
        operator_name = std_operator_names[expression]
    
    # 標準化
    operator_name = operator_name.replace("-","_")

    return ObjectOperator(operator_name, left_operand_type, modbits)


#
# 演算子呼び出しをラップしたクラス
#
class ObjectOperator():
    def __init__(self, name, left_operand_type, modifier):
        self.name = name
        self.modifier = modifier
        self.lefttype = left_operand_type
        self._resolved = self._pre_resolve(name)

    # 演算子の作成時に、関数を解決できるならしておく
    def _pre_resolve(self, name):
        opr = None

        for _ in [1]:
            # 型に定義された演算子
            if self.lefttype is not None:
                meth = self.lefttype.get_method(name)
                if meth is not None:
                    opr = meth.resolve(self.lefttype)
                    break
            
            # machaon.object.operatorの演算子
            if name in builtin_operators:
                opr = builtin_operators[name]
                break

            # 標準の演算子
            import operator
            opr = getattr(operator, name, None)
            if opr is not None:
                break

            opr = getattr(operator, name+"_", None) # "is" で "is_" にマッチさせる
            if opr is not None:
                break
        
        return opr

    def __str__(self):
        return "<ObjectOperator '{}'>".format(self.name)

    def __call__(self, *args):
        if self.modifier & OPERATION_REVERSE:
            args = tuple(reversed(args))

        if self._resolved:
            r = self._resolved(*args)
        else:
            # 値に定義された演算子を呼び出す
            left = args[0]
            method = getattr(left, self.name, None)
            if method is None:
                raise BadOperatorError("'{}'に演算子'{}'は存在しません".format(left, self.name))
            r = method(*args[1:])
        
        if self.modifier & OPERATION_NEGATE:
            r = (not r)
        
        return r
    
    # デバッグ表示用
    def resolution(self):
        if self._resolved:
            mod = self._resolved.__module__
            if mod == "_operator": # 標準のoperatorモジュール
                mod = "std_operator"
            elif not mod:
                mod = "builtin"
            elif mod.startswith("machaon.object.operation"):
                mod = "machaon_operator"

            return ".".join([mod, self._resolved.__name__])
        else:
            return ".".join(["left_operand_method", self.name])


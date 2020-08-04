from machaon.object.type import normalize_method_target, TypeMethod

#
#
#
class BadOperatorError(Exception):
    pass

# Python標準のオーバーロード可能な演算子
std_operators = {
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
    "is" : "is_",
    "not" : "not_",
}

# オーバーロード不可能な演算子
def logical_and(l, r):
    return l and r

def logical_or(l, r):
    return l or r

def slice_(seq, start=None, end=None):
    return seq[start:end]

builtin_operators = {
    "&&" : logical_and,
    "and" : logical_and,
    "||" : logical_or,
    "or" : logical_or,
    "slice" : slice_,
}


#
# 演算子への修飾指示
#

OPERATION_REVERSE = 0x1
OPERATION_NEGATE = 0x2

# 文字列から解析
def parse_operator_expression(expression, left_operand_type=None):
    modbits = 0

    if len(expression)>1:
        if expression.startswith("~"):
            modbits |= OPERATION_REVERSE
            expression = expression[1:]
        
        if expression.startswith("!"):
            modbits |= OPERATION_NEGATE
            expression = expression[1:]

    operator_name = expression
    return ObjectOperator(operator_name, left_operand_type, modbits)

#
# 演算子呼び出しをラップしたクラス
#
class ObjectOperator():
    def __init__(self, name, left_operand_type=None, modifier=0):
        self.name = name
        self.lefttype = left_operand_type
        self._resolved, modbits = self._pre_resolve(name, self.lefttype)
        self.modifier = modifier | modbits

    # 演算子の作成時に、関数を解決できるならしておく
    def _pre_resolve(self, name, lefttype):
        opr = None
        mod = 0

        for _ in [1]:
            # 型に定義された演算子
            if lefttype is not None:
                meth = lefttype.get_method(name)
                if meth is not None:
                    opr = meth.resolve(lefttype)
                    break
            
            name = normalize_method_target(name) # Pythonの識別名の形式に適合させる

            # machaon.object.operatorの演算子
            if name in builtin_operators:
                opr = builtin_operators[name]
                break

            # 標準の演算子
            import operator
            opr = getattr(operator, name, None)
            if opr is not None:
                break

            # 演算記号から関数へ
            if name in std_operators:
                o = parse_operator_expression(std_operators[name])
                opr = getattr(operator, o.name)
                mod = o.modifier
                break
    
        return opr, mod

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
            name = normalize_method_target(self.name) # Pythonの識別名の形式に適合させる
            method = getattr(left, name, None)
            if method is None:
                resolved = []
                if self.lefttype:
                    resolved.append(str(self.lefttype)+'のメンバ')
                resolved.append("汎用演算子")
                resolved.append(str(left)+'のメンバ')
                msg = "、".join(resolved) + "を検索しましたが、演算子'{}'は定義されていません".format(name)
                raise BadOperatorError(msg)
            r = method(*args[1:])
        
        if self.modifier & OPERATION_NEGATE:
            r = (not r)
        
        return r
    
    def get_resolved(self):
        return self._resolved
        
    def get_result_typehint(self):
        if self._resolved:
            if isinstance(self._resolved, TypeMethod):
                return self._resolved.get_result_typecode()
        return None
    
    # デバッグ表示用
    def resolution(self):
        if self._resolved:
            mod = self._resolved.__module__
            if mod == "_operator": # 標準のoperatorモジュール
                mod = "std_operator"
            elif not mod:
                mod = "builtin"
            elif mod.startswith("machaon.object.operator"):
                mod = "machaon_operator"

            return ".".join([mod, self._resolved.__name__])
        else:
            return ".".join(["method", self.name])

    def calling(self):
        m = ''
        if self.modifier & OPERATION_REVERSE:
            m += "~"
        if self.modifier & OPERATION_NEGATE:
            m += "!"
        return m + self.name

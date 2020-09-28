from machaon.object.type import Type
from machaon.object.symbol import normalize_method_target

#
# どんな型にも共通のメソッドを提供
#
def resolve_generic_method(name):
    if name in operators:
        name = operators[name]
    truename = "function_" + normalize_method_target(name)
    fn = globals().get(truename, None)
    return fn

#
#
# 実装
#
#

# 比較
def function_equal(left, right) -> bool:
    return left == right
    
def function_not_equal(left, right) -> bool:
    return left != right
    
def function_less_equal(left, right) -> bool:
    return left <= right
    
def function_less(left, right) -> bool:
    return left < right
    
def function_greater_equal(left, right) -> bool:
    return left >= right
    
def function_greater(left, right) -> bool:
    return left > right
    
def function_is(left, right) -> bool:
    return left is right
    
def function_is_not(left, right) -> bool:
    return left is not right

# 論理
def function_and(left, right) -> bool:
    return left and right

def function_or(left, right) -> bool:
    return left or right

def function_not(left) -> bool:
    return not left

def function_truth(left) -> bool:
    return bool(left)

# 数学
def function_add(left, right):
    return left + right

def function_sub(left, right):
    return left - right

def function_mul(left, right):
    return left * right
    
def function_matmul(left, right):
    return left @ right

def function_div(left, right):
    return left / right
    
def function_floordiv(left, right):
    return left // right

def function_mod(left, right):
    return left % right

def function_negative(left):
    return -left

def function_positive(left):
    return +left

def function_abs(left):
    return abs(left)

def function_pow(left, right):
    return pow(left, right)

def function_round(left: float, right: int = None) -> float:
    return round(left, right)

# ビット演算
def function_bitand(left: int, right: int) -> int:
    return left & right

def function_bitor(left: int, right: int) -> int:
    return left | right
    
def function_bitxor(left: int, right: int) -> int:
    return left ^ right
    
def function_bitinv(left: int) -> int:
    return ~left
    
def function_lshift(left: int, right: int) -> int:
    return left << right
    
def function_rshift(left: int, right: int) -> int:
    return left >> right
    
# リスト関数
def function_contain(left, right) -> bool:
    return right in left 

def function_in(left, right) -> bool:
    return left in right

def function_at(left, right: int):
    return left[right]

def function_slice(left, start: int=None, end: int=None):
    return left[start:end]
    
def function_concat(left, right) -> bool:
    return left + right
    
# その他の組み込み関数
def function_length(left) -> int:
    return len(left)

def function_or_greater(left, right):
    if left < right:
        return right
    return left

def function_or_less(left, right):
    if left > right:
        return right
    return left

def function_in_format(left, right: str) -> str:
    fmt = "{0:" + right + "}"
    return fmt.format(left)


#
def function_identical(obj):
    return obj

def function_bind(spirit, left, right: str):
    # spirit: (but not task function)
    # left: Object

    # return spirit.put_object(right, left)
    pass


#
# 演算子と実装の対応
#
operators = {
    "==" : "equal",
    "!=" : "not-equal",
    "<=" : "less-equal",
    "<" : "less",
    ">=" : "greater-equal",
    ">" : "greater",
    "+" : "add",
    "-" : "sub",
    "neg" : "negative",
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
    "&&" : "and", 
    "||" : "or",
    "=" : "identical",
    "=>" : "bind"
}

#
#
#
class GenericTraits:
    """ @no-instance-method
    """

    # 比較
    def equal(self, left, right) -> bool:
        return left == right
        
    def not_equal(self, left, right) -> bool:
        return left != right
        
    def less_equal(self, left, right) -> bool:
        return left <= right
        
    def less(self, left, right) -> bool:
        return left < right
        
    def greater_equal(self, left, right) -> bool:
        return left >= right
        
    def greater(self, left, right) -> bool:
        return left > right
        
    def is_(self, left, right) -> bool:
        return left is right
        
    def is_not(self, left, right) -> bool:
        return left is not right

    # 論理
    def logand(self, left, right) -> bool:
        return left and right

    def logior(self, left, right) -> bool:
        return left or right

    def lognot(self, left) -> bool:
        return not left

    def truth(self, left) -> bool:
        return bool(left)

    # 数学
    def add(self, left, right):
        return left + right

    def sub(self, left, right):
        return left - right

    def mul(self, left, right):
        return left * right
        
    def matmul(self, left, right):
        return left @ right

    def div(self, left, right):
        return left / right
        
    def floordiv(self, left, right):
        return left // right

    def mod(self, left, right):
        return left % right

    def negative(self, left):
        return -left

    def positive(self, left):
        return +left

    def abs(self, left):
        return abs(left)

    def pow(self, left, right):
        return pow(left, right)

    def round(self, left: float, right: int = None) -> float:
        return round(left, right)

    # ビット演算
    def bitand(self, left: int, right: int) -> int:
        return left & right

    def bitor(self, left: int, right: int) -> int:
        return left | right
        
    def bitxor(self, left: int, right: int) -> int:
        return left ^ right
        
    def bitinv(self, left: int) -> int:
        return ~left
        
    def lshift(self, left: int, right: int) -> int:
        return left << right
        
    def rshift(self, left: int, right: int) -> int:
        return left >> right
        
    # リスト関数
    def seqcontain(self, left, right) -> bool:
        return right in left 

    def seqin(self, left, right) -> bool:
        return left in right

    def seqat(self, left, right: int):
        return left[right]

    def seqslice(self, left, start: int=None, end: int=None):
        return left[start:end]
        
    def seqconcat(self, left, right) -> bool:
        return left + right
        
    # その他の組み込み関数
    def length(self, left) -> int:
        return len(left)

    def or_greater(self, left, right):
        if left < right:
            return right
        return left

    def or_less(self, left, right):
        if left > right:
            return right
        return left

    def in_format(self, left, right: str) -> str:
        fmt = "{0:" + right + "}"
        return fmt.format(left)

    # オブジェクト
    def identical(self, obj):
        """
        レシーバオブジェクトと同一のオブジェクトを返す。
        Arguments:
            obj: Object
        Returns:
            Object: レシーバオブジェクト
        """
        return obj

    def bind(self, spirit, left, right: str):
        # spirit: (but not task function)
        # left: Object

        # return spirit.put_
        pass
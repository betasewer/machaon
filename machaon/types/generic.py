from machaon.core.type import Type
from machaon.core.symbol import normalize_method_target
from machaon.core.method import methoddecl_collect
from machaon.core.invocation import TypeMethodInvocation

#
# どんな型にも共通のメソッドを提供
#
def resolve_generic_method_invocation(name, modbits=None):
    if name in operators:
        name = operators[name]

    """
    ほかの型と異なり、一度に全メソッドを読み込まず、要求が来るたびに該当メソッドだけを読み込む。
    メソッドが無い場合は、GenericMethodsのメンバ名のなかから実装を探し出し、読み込みを行う。
    したがって、関数本体でのエイリアス名の指定は無効である。
    """
    method = _GenericMethodsType.select_method(name)
    if method is None:
        # ロードする
        attrname = normalize_method_target(name)
        attr = getattr(GenericMethods, attrname, None)
        if attr is None:
            return None

        method, aliases = methoddecl_collect(attr, attrname)
        if method is None:
            return None
        
        method.load(_GenericMethodsType)

        _GenericMethodsType.add_method(method)
        for aliasname in aliases:
            _GenericMethodsType.add_member_alias(aliasname, name)

    # 呼び出しを作成する
    return TypeMethodInvocation(_GenericMethodsType, method, modbits)

#
#
# 実装
#
#
class GenericMethods:
    """
    エイリアス名はメソッドの設定で指定しても読み込まれません。
    ファイル末尾にあるoperatorsに追加してください。
    """
    @classmethod
    def describe_object(cls, typeobj):
        # メソッドの収集は行わず、型のみを定義する
        typeobj.describe_from_docstring(""" @no-instance-method """)

    # 比較
    def equal(self, left, right):
        """ @method reciever-param
        二項==演算子。（等しい）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left == right
        
    def not_equal(self, left, right):       
        """ @method reciever-param
        二項!=演算子。（等しくない）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left != right
        
    def less_equal(self, left, right):  
        """ @method reciever-param
        二項<=演算子。（以下）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left <= right
        
    def less(self, left, right):
        """ @method reciever-param
        二項<演算子。（より小さい）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left < right
        
    def greater_equal(self, left, right):
        """ @method reciever-param
        二項>=演算子。（以上）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left >= right
        
    def greater(self, left, right):
        """ @method reciever-param
        二項>演算子。（より大きい）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left > right
        
    def is_(self, left, right):
        """ @method reciever-param
        is演算子。（同一オブジェクト）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left is right
        
    def is_not(self, left, right):
        """ @method reciever-param
        is not演算子。（同一オブジェクトでない）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left is not right

    # 論理
    def logand(self, left, right):
        """ @method reciever-param
        A かつ B であるか。
        Arguments:
            left(Bool): 
            right(Bool): 
        Returns:
            Bool:
        """
        return left and right

    def logior(self, left, right):
        """ @method reciever-param
        A または B であるか。
        Arguments:
            left(Bool): 
            right(Bool): 
        Returns:
            Bool:
        """
        return left or right

    def lognot(self, left):
        """ @method reciever-param
        A が偽か。
        Arguments:
            left(Bool): 
        Returns:
            Bool:
        """
        return not left

    def truth(self, left) -> bool:
        """ @method reciever-param
        A が真か。
        Arguments:
            left(Bool): 
        Returns:
            Bool:
        """
        return bool(left)

    # 数学
    def add(self, left, right):
        """ @method reciever-param
        二項+演算子。（加算）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        return left + right

    def sub(self, left, right):
        """ @method reciever-param
        二項-演算子。（減算）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        return left - right

    def mul(self, left, right):
        """ @method reciever-param
        二項*演算子。（乗算）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        return left * right
        
    def matmul(self, left, right):
        """ @method reciever-param
        二項@演算子。（行列乗算）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        return left @ right

    def div(self, left, right):
        """ @method reciever-param
        二項/演算子。（除算）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        return left / right
        
    def floordiv(self, left, right):
        """ @method reciever-param
        二項//演算子。（整数除算）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        return left // right

    def mod(self, left, right):
        """ @method reciever-param
        二項%演算子。（剰余）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        return left % right

    def neg(self, left):
        """ @method reciever-param
        単項-演算子。（符号反転）
        Arguments:
            left(Any): 
        Returns:
            Any:
        """
        return -left

    def positive(self, left):
        """ @method reciever-param
        単項+演算子。（符号そのまま）
        Arguments:
            left(Any):
        Returns:
            Any:
        """
        return +left

    def abs(self, left):
        """ @method reciever-param
        絶対値。
        Arguments:
            left(Any):
        Returns:
            Any:
        """
        return abs(left)

    def pow(self, left, right):
        """ @method reciever-param
        べき乗の計算。
        Arguments:
            left(Any): 底
            right(Any): 指数
        Returns:
            Any: べき
        """
        return pow(left, right)

    def round(self, left, right=None):
        """ @method reciever-param
        小数を丸める。
        Arguments:
            left(Any): 数
            right(Int): 桁数
        Returns:
            Any: 丸められた小数。
        """
        return round(left, right)

    # ビット演算
    def bitand(self, left, right):
        """ @method reciever-param
        二項&演算子。（ビット論理積）
        Arguments:
            left(Any): 
            right(Int): 
        Returns:
            Any:
        """
        return left & right

    def bitor(self, left, right):
        """ @method reciever-param
        二項|演算子。（ビット論理和）
        Arguments:
            left(Any): 
            right(Int): 
        Returns:
            Any:
        """
        return left | right
        
    def bitxor(self, left, right):        
        """ @method reciever-param
        二項^演算子。（ビット排他論理和）
        Arguments:
            left(Any): 
            right(Int): 
        Returns:
            Any:
        """
        return left ^ right
        
    def bitinv(self, left):   
        """ @method reciever-param
        単項~演算子。（ビット否定）
        Arguments:
            left(Any):
        Returns:
            Any:
        """
        return ~left
        
    def lshift(self, left, right): 
        """ @method reciever-param
        二項<<演算子。（ビット左シフト）
        Arguments:
            left(Any):
            right(Any):
        Returns:
            Any:
        """
        return left << right
        
    def rshift(self, left, right):
        """ @method reciever-param
        二項>>演算子。（ビット右シフト）
        Arguments:
            left(Any):
            right(Any):
        Returns:
            Any:
        """
        return left >> right
        
    # リスト関数
    def exists_in(self, left, right):
        """ @method reciever-param
        二項in演算子の逆。（集合に含まれるか）
        Arguments:
            left(Any): 対象
            right(Any): 母集団
        Returns:
            Any:
        """
        return right in left 

    def contains(self, left, right):
        """ @method reciever-param
        二項in演算子。（集合に含まれるか）
        Arguments:
            left(Any): 母集団
            right(Any): 対象
        Returns:
            Any:
        """
        return left in right

    def at(self, left, right):
        """ @method reciever-param
        添え字演算子。（要素アクセス）
        Arguments:
            left(Any): 配列
            right(Any): 添え字
        Returns:
            Any:
        """
        return left[right]

    def slice(self, left, start, end):
        """ @method reciever-param
        スライス演算子。（要素アクセス）
        Arguments:
            left(Any): 配列
            start(Any): 始まり
            end(Any): 終わり
        Returns:
            Any:
        """
        return left[start:end]
        
    # その他の組み込み関数
    def length(self, left):
        """ @method reciever-param
        長さを求める。
        Arguments:
            left(Any): 
        Returns:
            Any:
        """
        return len(left)

    def or_greater(self, left, right):
        """ @method reciever-param
        大きい方を取る。
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        if left < right:
            return right
        return left

    def or_less(self, left, right):
        """ @method reciever-param
        小さい方を取る。
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        if left > right:
            return right
        return left

    def in_format(self, left, right):
        """ @method reciever-param
        書式化文字列を作成。
        Arguments:
            left(Any): 値
            right(Str): 値の書式
        Returns:
            Str: 文字列
        """
        fmt = "{0:" + right + "}"
        return fmt.format(left)

    # オブジェクト
    def identical(self, obj):
        """ @method reciever-param
        同一のオブジェクトを返す。
        Arguments:
            obj(Object): 対象
        Returns:
            Object: 対象オブジェクト
        """
        return obj
    
    def pretty(self, obj):
        """ @method reciever-param
        オブジェクトの詳細表示を返す。
        Arguments:
            obj(Object): 対象
        Returns:
            Object: 
        """
        if obj.is_pretty_view():
            return obj
        return obj.pretty_view()

    def type(self, obj):
        """ @method reciever-param
        オブジェクトの型を返す。
        Arguments:
            obj(Object): 対象
        Returns:
            Type: オブジェクトの型
        """
        return obj.type
    
    def convertas(self, obj, context, type):
        """ @method reciever-param context
        型を変換する。
        Arguments:
            obj(Object): オブジェクト
            type(Type): 型
        Returns:
            Object: 変換されたオブジェクト
        """
        v = type.conversion_construct(context, obj.value)
        return type.new_object(v)

    def bind(self, left, context, right):
        """ @method reciever-param context
        オブジェクトを変数に束縛する。
        Arguments:
            left(Object): オブジェクト
            right(str): 名前
        Returns:
            Object: 左辺オブジェクト
        """
        context.bind_object(right, left)
        return left

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
    "and" : "logand",
    "or" : "logior",
    "not" : "lognot",
    "&&" : "logand", 
    "||" : "logior",
    "=" : "identical",
    "?" : "pretty",
    "=>" : "bind",
    "in" : "contains",
    "as" : "convertas",
}

class GenericMethodValue():
    def __init__(self):
        raise TypeError("Should not be constructed")

# メソッドオブジェクトのキャッシュ
_GenericMethodsType = Type(GenericMethods, name="GenericMethods", value_type=GenericMethodValue)
_GenericMethodsType.load()


from machaon.core.type.type import TYPE_DELAY_LOAD_METHODS, Type
from machaon.core.symbol import normalize_method_name, normalize_method_target
from machaon.core.method import make_method_prototype_from_doc, parse_doc_declaration
from machaon.core.invocation import TypeMethodInvocation
from machaon.core.type.describer import TypeDescriberClass

#
# どんな型にも共通のメソッドを提供
#
class GenericMethodResovler:
    def __init__(self) -> None:
        self.describer = TypeDescriberClass(GenericMethods)
        self.describer.set_full_qualname("machaon.core")
        _GenericMethodsType = Type(self.describer)
        _GenericMethodsType.load(nodescribe=True, typename="Generic", value_type=self.TypeValue)
        self._t = _GenericMethodsType

    @property
    def type(self):
        return self._t

    class TypeValue:
        def __init__(self):
            raise TypeError("Should not be constructed")
        
    def resolve(self, name):
        """
        ほかの型と異なり、一度に全メソッドを読み込まず、要求が来るたびに該当メソッドだけを読み込む。
        メソッドが無い場合は、GenericMethodsのメンバ名のなかから実装を探し出し、読み込みを行う。
        したがって、関数本体でのエイリアス名の指定は無効である。
        """
        method = self.type.select_method(name)
        if method is None:
            # ロードする
            attrname = normalize_method_target(name)
            attr = self.describer.get_method_attribute(attrname)
            if attr is None:
                return None

            decl = parse_doc_declaration(attr, ("method", "task"))
            if decl is None:
                return None
            
            method, _aliases = make_method_prototype_from_doc(decl, attrname)
            if method is None:
                return None
            
            method.load_from_type(self.type)
            self.type.add_method(method)

        return method


def resolve_generic_method(name):
    if name in operators:
        name = operators[name]
    return _GenericMethodResolver.resolve(name)

def resolve_generic_method_invocation(name, modbits=None):
    method = resolve_generic_method(name)
    if method is None:
        return None
    return TypeMethodInvocation(_GenericMethodResolver.type, method, modbits)


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
    "<=>" : "compare",
    "+" : "add",
    "-" : "sub",
    "*" : "mul",
    "@" : "matmul",
    "**" : "pow",
    "/" : "div",
    "//" : "floordiv",
    "%" : "mod",
    "-=" : "negative",
    "+=" : "positive",
    "&" : "bitand",
    "^" : "bitxor",
    "|" : "bitor",
    "~" : "bitinv",
    ">>" : "rshift",
    "<<" : "lshift",
    "in" : "is-in",
    "#" : "at",
    "#>" : "attrat",
    "=" : "identical",
    "?" : "pretty",
    "=>" : "bind",
    "/+" : "tuplepush",
}

#
#
# 実装
#
#
class GenericMethods:
    """
    エイリアス名はメソッドの設定で指定しても読み込まれません。
    operatorsに追加してください。
    """

    # 比較
    def equal(self, left, right):
        """ @method external
        二項==演算子。（等しい）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left == right

    def not_equal(self, left, right):
        """ @method external
        二項!=演算子。（等しくない）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left != right
    
    def less_equal(self, left, right):  
        """ @method external
        二項<=演算子。（以下）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left <= right
        
    def less(self, left, right):
        """ @method external
        二項<演算子。（より小さい）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left < right
        
    def greater_equal(self, left, right):
        """ @method external
        二項>=演算子。（以上）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left >= right
        
    def greater(self, left, right):
        """ @method external
        二項>演算子。（より大きい）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left > right
    
    def compare(self, left, right):
        """ @method external
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Int:
        """
        if left == right:
            return 0
        elif left < right:
            return 1
        else:
            return -1
    
    def is_between(self, left, min, max):
        """ @method external
        Params:
            left(Any):
            min(Any): 下端（含む）
            max(Any): 上端（含む）
        Returns:
            Bool:
        """
        return min <= left and left <= max
    
    def is_(self, left, right):
        """ @method external
        is演算子。（同一オブジェクト）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left is right
        
    def is_not(self, left, right):
        """ @method external
        is not演算子。（同一オブジェクトでない）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Bool:
        """
        return left is not right

    def is_none(self, left) -> bool:
        """ @method external
        Noneである。
        Arguments:
            left(Any): 
        Returns:
            Bool:
        """
        return left is None

    def truth(self, left) -> bool:
        """ @method external
        A が真か。
        Arguments:
            left(Any): 
        Returns:
            Bool:
        """
        return bool(left)
    
    def falsy(self, left) -> bool:
        """ @method external
        A が偽か。
        Arguments:
            left(Any): 
        Returns:
            Bool:
        """
        return not left

    # 数学
    def add(self, left, right):
        """ @method external
        二項+演算子。（加算）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        return left + right

    def sub(self, left, right):
        """ @method external
        二項-演算子。（減算）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        return left - right

    def mul(self, left, right):
        """ @method external
        二項*演算子。（乗算）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        return left * right
        
    def matmul(self, left, right):
        """ @method external
        二項@演算子。（行列乗算）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        return left @ right

    def div(self, left, right):
        """ @method external
        二項/演算子。（除算）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        return left / right
        
    def floordiv(self, left, right):
        """ @method external
        二項//演算子。（整数除算）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        return left // right

    def mod(self, left, right):
        """ @method external
        二項%演算子。（剰余）
        Arguments:
            left(Any): 
            right(Any): 
        Returns:
            Any:
        """
        return left % right

    def negative(self, left): 
        """ @method external
        単項-演算子。（符号反転）
        Arguments:
            left(Any): 
        Returns:
            Any:
        """
        return -left

    def positive(self, left):
        """ @method external
        単項+演算子。（符号そのまま）
        Arguments:
            left(Any):
        Returns:
            Any:
        """
        return +left

    def pow(self, left, right):
        """ @method external
        べき乗の計算。
        Arguments:
            left(Any): 底
            right(Any): 指数
        Returns:
            Any:
        """
        return left ** right

    # ビット演算
    def bitand(self, left, right):
        """ @method external
        二項&演算子。（ビット論理積）
        Arguments:
            left(Any): 
            right(Int): 
        Returns:
            Any:
        """
        return left & right

    def bitor(self, left, right):
        """ @method external
        二項|演算子。（ビット論理和）
        Arguments:
            left(Any): 
            right(Int): 
        Returns:
            Any:
        """
        return left | right
        
    def bitxor(self, left, right):        
        """ @method external
        二項^演算子。（ビット排他論理和）
        Arguments:
            left(Any): 
            right(Int): 
        Returns:
            Any:
        """
        return left ^ right
        
    def bitinv(self, left):   
        """ @method external
        単項~演算子。（ビット否定）
        Arguments:
            left(Any):
        Returns:
            Any:
        """
        return ~left
        
    def lshift(self, left, right): 
        """ @method external
        二項<<演算子。（ビット左シフト）
        Arguments:
            left(Any):
            right(Any):
        Returns:
            Any:
        """
        return left << right
        
    def rshift(self, left, right):
        """ @method external
        二項>>演算子。（ビット右シフト）
        Arguments:
            left(Any):
            right(Any):
        Returns:
            Any:
        """
        return left >> right
        
    # リスト関数
    def is_in(self, left, right):
        """ @method external
        二項in演算子。（集合に含まれるか）
        Arguments:
            left(Any): 対象
            right(Any): 母集団
        Returns:
            Any:
        """
        return left in right

    def contains(self, left, right):
        """ @method external
        二項in演算子の逆。（集合が含むか）
        Arguments:
            left(Any): 母集団
            right(Any): 対象
        Returns:
            Any:
        """
        return right in left 

    def at(self, left, index):
        """ @method external
        添え字演算子。（要素アクセス）
        Arguments:
            left(Any): 配列
            index(Any): 添え字
        Returns:
            Any:
        """
        return left[index]
        
    def attrat(self, left, key):
        """ @method external
        属性にアクセスする。
        Arguments:
            left(Any): 配列
            key(str): 属性名
        Returns:
            Any:
        """
        key = normalize_method_target(key)
        return getattr(left, key)
    
    def slice(self, left, start, stop):
        """ @method external
        添え字演算子。（要素アクセス）
        Arguments:
            left(Any): 配列
            start(Any): 開始位置
            stop(Any): 終了位置
        Returns:
            Any:
        """
        return left[start:stop]
    
    # その他の組み込み関数
    def length(self, left):
        """ @method external
        長さを求める。
        Arguments:
            left(Any):
        Returns:
            Any:
        """
        return len(left)

    def truth_then(self, left, context, if_, else_):
        """ @method external context 
        leftを真理値として評価して真であればif_を、偽であればelse_を実行する。
        Arguments:
            left(Object): 
            if_(Function):
            else_(Function):
        Returns:
            Any:
        """
        body = if_ if left.test_truth() else else_
        return body.run(left, context)

    def falsy_then(self, left, context, if_, else_):
        """ @method external context 
        leftを真理値として評価して偽であればif_を、真であればelse_を実行する。
        Arguments:
            left(Object): 
            if_(Function):
            else_(Function):
        Returns:
            Any:
        """
        body = if_ if not left.test_truth() else else_
        return body.run(left, context)
        
    def test_then(self, left, context, cond, if_, else_):
        """ @method external context 
        値を条件式で判定し、その結果でif節またはelse節を実行する。
        Arguments:
            left(Object): 
            cond(Function):
            if_(Function):
            else_(Function):
        Returns:
            Any:
        """
        if cond.run(left, context).test_truth():
            return if_.run(left, context)
        else:
            return else_.run(left, context)

    # オブジェクト
    def identical(self, obj):
        """ @method external
        同一のオブジェクトを返す。
        Arguments:
            obj(Object): 対象
        Returns:
            Any: 対象オブジェクト
        """
        return obj
    
    def pretty(self, obj):
        """ @method external
        オブジェクトの詳細表示を返す。
        Arguments:
            obj(Object): 対象
        Returns:
            Any: 
        """
        if obj.is_pretty():
            return obj
        return obj.to_pretty()

    def type(self, obj):
        """ @method external
        オブジェクトの型を返す。
        Arguments:
            obj(Object): 対象
        Returns:
            Type: オブジェクトの型
        """
        return obj.type
        
    def help(self, obj, context):
        """ @method external context
        オブジェクトの説明、メソッドを表示する。
        Arguments:
            obj(Object): 対象
        """
        from machaon.types.fundamental import TypeType
        return TypeType().help(obj.type, context, context.spirit, obj.value)
    
    def stringify(self, obj):
        """ @method external
        stringifyメソッドで文字列に変換する。
        Arguments:
            obj(Object): オブジェクト
        Returns:
            Str:
        """
        return obj.stringify()

    def bind(self, left, context, right):
        """ @method external context
        オブジェクトを変数に束縛する。
        Arguments:
            left(Object): オブジェクト
            right(str): 名前
        Returns:
            Any: 左辺オブジェクト
        """
        context.bind_object(right, left)
        return left
        
    def cast(self, left, right):
        """ @method external
        コンストラクタを介さずに型を変更する。
        Arguments:
            left(Any): 値
            right(Type): 型オブジェクト
        Returns:
            Any: 新しいオブジェクト
        """
        from machaon.core.object import Object
        o = Object(right, left)
        return o
        
    def cast_raw(self, left, context):
        """ @method external context
        オブジェクトの型をPythonTypeに変える。
        Arguments:
            left(Any): 値
        Returns:
            Any: 新しいオブジェクト
        """
        from machaon.core.object import Object
        pytype = context.get_py_type(type(left))
        o = Object(pytype, left)
        return o
        
    def tuplepush(self, left, right):
        """ @method external
        タプルに追加する。
        Arguments:
            left(Object): タプルもしくは要素
            right(Object): 追加する要素
        Returns:
            Any: 左辺オブジェクト
        """
        from machaon.types.tuple import ObjectTuple
        if left.get_typename() == "Tuple":
            return ObjectTuple(left.value.objects + [right])
        else:
            return ObjectTuple([left, right])
    
    def void(self, left):
        """ @method external
        セレクタを引数無しの呼び出しに変換する。
        Params:
            left(Any): 任意のセレクタオブジェクト
        Returns:
            Any:
        """
        from machaon.core.invocation import BasicInvocation, FunctionInvocation
        if isinstance(left, BasicInvocation):
            left.set_modifier("IGNORE_ARGS")
            return left
        else:
            return FunctionInvocation(left, {"IGNORE_ARGS"}, 0, 0)

_GenericMethodResolver = GenericMethodResovler()


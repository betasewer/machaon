
from machaon.core.type.type import TYPE_DELAY_LOAD_METHODS, Type
from machaon.core.symbol import normalize_method_name, normalize_method_target, SIGIL_OPERATOR_MEMBER_AT
from machaon.core.method import make_method_prototype_from_doc, parse_doc_declaration
from machaon.core.invocation import TypeMethodInvocation
from machaon.core.type.describer import TypeDescriberClass

#
# どんな型にも共通のメソッドを提供
#
class GenericMethodResolver:
    def __init__(self) -> None:
        self.describer = TypeDescriberClass(GenericMethods)

    def is_resolvable(self, name):
        return name in self.operators
        
    def resolve(self, name):
        fnname = self.operators.get(name)
        return fnname
        
    def get_attribute(self, fnname):
        return self.describer.get_method_attribute(fnname)
    
    def enum_attributes(self):
        # 演算子名を復元するマップ
        operators_rev = {}
        for k,v in self.operators.items():
            operators_rev.setdefault(v, []).append(k)
        # 属性をすべて辿る
        from machaon.core.importer import enum_attributes
        for name, val in enum_attributes(self.describer.get_value()):
            if not name in operators_rev:
                continue
            yield operators_rev[name], name, val
    
    def get_describer(self):
        return self.describer

    operators = {}

    @classmethod
    def operator(cls, *operators):
        def _deco(fn):
            for opr in operators:
                cls.operators[normalize_method_name(opr)] = fn.__name__ 
            return fn
        return _deco



def resolve_generic_method(name):
    return _GenericMethodResolver.resolve(name)

def is_resolvable_generic_method(name):
    return _GenericMethodResolver.is_resolvable(name)

def resolve_generic_method_invocation(name, modbits=None):
    method = resolve_generic_method(name)
    if method is None:
        return None
    return TypeMethodInvocation(_GenericMethodResolver.type, method, modbits)


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
    resolver = GenericMethodResolver

    # 比較
    @resolver.operator("==", "eq")
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

    @resolver.operator("!=", "ne")
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
    
    @resolver.operator("<=", "le")
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
        
    @resolver.operator("<", "lt")
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
        
    @resolver.operator(">=", "ge")
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
        
    @resolver.operator(">", "gt")
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
    
    @resolver.operator("<=>", "compare")
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
    
    @resolver.operator("between")
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

    @resolver.operator("is")
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
        
    @resolver.operator("is-not")
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

    @resolver.operator("is-none")
    def is_none(self, left) -> bool:
        """ @method external
        Noneである。
        Arguments:
            left(Any): 
        Returns:
            Bool:
        """
        return left is None

    @resolver.operator("truthy")
    def truth(self, left) -> bool:
        """ @method external
        A が真か。
        Arguments:
            left(Any): 
        Returns:
            Bool:
        """
        return bool(left)
    
    @resolver.operator("falsy", "not")
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
    @resolver.operator("+", "add")
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

    @resolver.operator("-", "sub")
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

    @resolver.operator("*", "mul")
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
        
    @resolver.operator("@", "matmul")
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

    @resolver.operator("/", "div")
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
        
    @resolver.operator("//", "floordiv")
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

    @resolver.operator("%", "mod")
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

    @resolver.operator("-=", "neg")
    def negative(self, left): 
        """ @method external
        単項-演算子。（符号反転）
        Arguments:
            left(Any): 
        Returns:
            Any:
        """
        return -left

    @resolver.operator("+=", "pos")
    def positive(self, left):
        """ @method external
        単項+演算子。（符号そのまま）
        Arguments:
            left(Any):
        Returns:
            Any:
        """
        return +left

    @resolver.operator("**", "pow")
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
    @resolver.operator("&", "bitand")
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

    @resolver.operator("|", "bitor")
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
        
    @resolver.operator("^", "bitxor")
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
    
    @resolver.operator("~", "bitinv")
    def bitinv(self, left):   
        """ @method external
        単項~演算子。（ビット否定）
        Arguments:
            left(Any):
        Returns:
            Any:
        """
        return ~left
    
    @resolver.operator(">>", "lshift")
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
    
    @resolver.operator("<<", "rshift")
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
    @resolver.operator("in")
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

    @resolver.operator("contains")
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

    @resolver.operator(SIGIL_OPERATOR_MEMBER_AT, "at")
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
        
    @resolver.operator(SIGIL_OPERATOR_MEMBER_AT+">", "attrat")
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
    
    @resolver.operator("["+SIGIL_OPERATOR_MEMBER_AT+"]", "slice") # 
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
    @resolver.operator("length", "len")
    def length(self, left):
        """ @method external
        長さを求める。
        Arguments:
            left(Any):
        Returns:
            Any:
        """
        return len(left)

    @resolver.operator("if-true")
    def truthy_then(self, context, left, if_, else_):
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

    @resolver.operator("if-false")
    def falsy_then(self, context, left, if_, else_):
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

    @resolver.operator("test-then")
    def test_then(self, context, left, cond, if_, else_):
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
    @resolver.operator("=", "identity")
    def identity(self, obj):
        """ @method external
        同一のオブジェクトを返す。
        Arguments:
            obj(Object): 対象
        Returns:
            Any: 対象オブジェクト
        """
        return obj
    
    @resolver.operator("?", "pretty")
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

    @resolver.operator("type")
    def type(self, obj):
        """ @method external
        オブジェクトの型を返す。
        Arguments:
            obj(Object): 対象
        Returns:
            Type: オブジェクトの型
        """
        return obj.type
        
    @resolver.operator("help")
    def help(self, context, obj):
        """ @method external context
        オブジェクトの型の説明、メソッドを表示する。
        Arguments:
            obj(Object): 対象
        """
        from machaon.types.fundamental import TypeType
        return TypeType().help(obj.type, context, context.spirit, obj.value)
    
    @resolver.operator("=>", "bind")
    def bind(self, context, left, right):
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
        
    @resolver.operator("cast")
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
        
    @resolver.operator("pycast")
    def pycast(self, context, left):
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
        
    @resolver.operator("/+", "tuplepush")
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


_GenericMethodResolver = GenericMethodResolver()
def get_resolver():
    return _GenericMethodResolver


import re

from machaon.core.type import Type, TypeModule, TypeDelayLoader, UnsupportedMethod, TYPE_ANYTYPE, TYPE_OBJCOLTYPE
from machaon.core.object import Object

fundamental_type = TypeModule()


# ----------------------------------------------------------
#
#  基本型
#
# ----------------------------------------------------------
@fundamental_type.definition(typename="Type", doc="""
オブジェクトの型。
""")
class TypeType():
    """@type
    ValueType: machaon.core.type.Type
    """

    def stringify(self, v):
        return "<{}>".format(v.typename)

    #
    # メソッド
    #
    def new(self, type, args=()):
        '''@method
        インスタンスを生成する。
        Params:
            args (Any): 1つか0個の引数
        Returns:
            Object: オブジェクト
        '''
        if isinstance(args, tuple) and len(args)==0:
            value = type.get_value_type()()
        else:
            value = type.get_value_type()(args)
        return Object(type, value)
    
    def parse(self, type, str):
        ''' @method
        文字列からインスタンスを生成する。
        Params:
            str(Str): 文字列
        Returns:
            Object: オブジェクト
        '''
        v = type.construct_from_string(str)
        return Object(type, v)

    def methods(self, type, context):
        '''@method context
        使用可能なメソッドを列挙する。
        Params:
        Returns:
            Sheet[Method]: (name,doc,signature) メソッドのリスト
        '''
        helps = []

        from machaon.core.message import enum_selectable_method
        for meth in enum_selectable_method(type):
            helps.append(meth)

        return helps
    
    def method(self, type, name):
        """ @method
        メソッドを取得する。
        Params:
            name(Str): メソッド名
        Returns:
            Method: メソッド
        """
        return type.select_method(name)
    
    def name(self, type):
        ''' @method
        型名。
        Returns:
            Str:
        '''
        return type.typename
    
    def doc(self, type):
        ''' @method
        型の説明。
        Returns:
            Str:
        '''
        return type.doc
    
    def scope(self, type):
        ''' @method
        スコープ名。
        Returns:
            Str:
        '''
        return type.scope

    def qualname(self, type):
        ''' @method
        スコープを含めた型名。
        Returns:
            Str:
        '''
        return type.fulltypename
    
    def describer(self, type):
        ''' @method
        実装の場所を示す文字列。
        Returns:
            Str:
        '''
        return type.get_describer_qualname()
    
    def set(self, type, context):
        ''' @method context
        空のSetを作成する。
        Returns:
            Object:
        '''
        from machaon.types.sheet import Sheet
        return Object(context.get_type("Sheet"), Sheet([], type))


@fundamental_type.definition(typename="Any", bits=TYPE_ANYTYPE, doc="""
あらゆる型を受け入れる型。
""")
class AnyType():
    """@type trait
    """

    def construct(self, s):
        raise UnsupportedMethod()

    def conversion_construct(self, _context, value):
        return value # そのままの値を返す


@fundamental_type.definition(typename="Function", doc="""
一つの引数をとるメッセージ。
""")
class FunctionType():
    """@type
    ValueType: machaon.core.message.MessageEngine
    """
    def construct(self, s):
        return self.value_type(s)

    def stringify(self, f):
        return f.get_expression()
    
    #
    #
    #
    def eval(self, f, context, subject=None):
        """ @method context
        関数を実行する。
        Params:
            subject(Object): *引数
        Returns:
            Object: 返り値
        """
        return f.run_function(subject, context)


# ----------------------------------------------------------
#
#  Pythonのビルトイン型
#
# ----------------------------------------------------------
@fundamental_type.definition(typename="Str", doc="""
Python.str 文字列。
""")
class StrType():
    """ @type use-instance-method
    ValueType: str
    """
    def construct(self, s):
        return s
    
    def stringify(self, v):
        return v

    #
    # メソッド
    #
    def convertas(self, s, type):
        '''@method alias-name [as]
        指定の型の値へと変換する。
        stringfyメソッドを使用。
        Params:
            type (Type): 型
        Returns:
            Object: 新たな型の値
        '''
        value = type.construct_from_string(s)
        return Object(type, value)
    
    def convertas_literals(self, s, context):
        """ @method context alias-name [as-literal]
        すべての値を適当な型に変換する。
        Params:
        Returns:
            Object: 新たな型の値
        """
        from machaon.core.message import select_literal
        return select_literal(context, s)

    def reg_match(self, s, pattern):
        '''@method
        正規表現に先頭から一致するかを調べる。
        Params:
            pattern (str): 正規表現
        Returns:
            bool: 一致するか
        '''
        m = re.match(pattern, s)
        if m:
            return True
        return False
    
    def reg_search(self, s, pattern):
        '''@method
        正規表現にいずれかの部分が一致するかを調べる。
        Params:
            pattern (str): 正規表現
        Returns:
            bool: 一致するか
        '''
        m = re.search(pattern, s)
        if m:
            return True
        return False
    
    def format(self, s, *args):
        """@method
        引数から書式にしたがって文字列を作成する。
        Params:
            *args: 任意の引数
        Returns:
            str: 文字列
        """
        return s.format(*args)

    def split(self, s, sep=None, maxsplit=-1):
        """@method
        文字を区切る。
        Params:
            sep(Str): *区切り文字
            maxsplit(Int): *区切り回数
        Returns:
            Tuple: データ
        """
        return s.split(sep, maxsplit=maxsplit)
    
    # 
    # 制御構文
    #
    def eval(self, s, context, subject=None):
        """ @method context
        文字列を関数として評価する。
        Params:
            subject(Object): *引数
        Returns:
            Object: 返り値
        """
        from machaon.core.message import run_function
        return run_function(s, subject, context)
    
    def pyvalue(self, symbol, context):
        """ @method context
        外部モジュールの変数あるいは引数無し関数を評価する。
        Returns:
            Any:
        """
        from machaon.core.importer import attribute_loader
        loader = attribute_loader(symbol)
        imported = loader(fallback=False)
        if not callable(imported):
            return imported # 変数
        else:
            return imported() # 関数実行
    
    #
    # その他
    #
    def path(self, s):
        """ @method
        フォルダ・ファイルを名前で指定してパスを得る。
        名前でなければパスと見なす。
        Params:
        Returns:
            machaon.shell.Path: パス
        """
        from machaon.types.shell import Path
        try:
            return Path.from_location_name(s)
        except Exception as e:
            p = Path(s)
            if not p.exists():
                raise e
            return p

@fundamental_type.definition(typename="Bool", doc="""
Python.bool 真偽値。
""")
class BoolType():
    """@type use-instance-method
    ValueType: bool
    """

    def construct(self, s):
        if s == "True":
            return True
        elif s == "False":
            return False
        elif not s:
            return False
        else:
            raise ValueError(s)
    
    #
    # 論理
    #
    def logical_and(self, left, right):
        """ @method alias-name [and &&]
        A かつ B であるか。
        Arguments:
            right(Bool): 
        Returns:
            Bool:
        """
        return left and right

    def logical_or(self, left, right):
        """ @method alias-name [or ||]
        A または B であるか。
        Arguments:
            right(Bool): 
        Returns:
            Bool:
        """
        return left or right

    def logical_not(self, left):
        """ @method alias-name [not]
        A が偽か。
        Returns:
            Bool:
        """
        return not left

    #
    # if
    #
    def if_true(self, b, context, if_, else_):
        """ @method context [if]
        文字列を評価し、真なら実行する。
        @ == 32 if-true: "nekkedo" "hekkeo"
        Params:
            if(Function): true 節
            else(Function): false 節 
        Returns:
            Object: 返り値
        """
        from machaon.core.message import run_function
        if b:
            body = if_
        else:
            body = else_
        return run_function(body, None, context)

#
#
# 数学型
#
#
class NumericType():   
    def abs(self, n):
        """ @method
        絶対値。
        Returns:
            Any:
        """
        return abs(n)
    
    def round(self, n, digits=None):
        """ @method
        小数を丸める。
        Arguments:
            right(Int): 桁数
        Returns:
            Any: 丸められた小数。
        """
        return round(n, digits)
    


@fundamental_type.definition(typename="Int", doc="""
整数型。
""")
class IntType(NumericType):
    """@type use-instance-method
    ValueType: int
    """

    def construct(self, s):
        return int(s, 0)
        
    #
    def hex(self, n):
        """ @method
        16進表記を得る。
        Returns:
            Str:
        """
        return hex(n)
    
    def oct(self, n):
        """ @method
        8進表記を得る。
        Returns:
            Str:
        """
        return oct(n)
    
    def bin(self, n):
        """ @method
        2進表記を得る。
        Returns:
            Str:
        """
        return bin(n)
    
    #
    def pow(self, n, exp):
        """ @method
        べき乗を計算する。
        Params:
            exp(Int):
        Returns:
            Int:
        """
        return pow(n, exp)


@fundamental_type.definition(typename="Float", doc="""
浮動小数点型。
""")
class FloatType(NumericType):
    """@type use-instance-method
    ValueType: float
    """

    def construct(self, s):
        return float(s)
    
    # math
    def pow(self, n, exp):
        """ @method
        べき乗を計算する。
        Params:
            exp(Float):
        Returns:
            Int:
        """
        import math
        return math.pow(n, exp)


@fundamental_type.definition(typename="Complex", doc="""
複素数型。
""")
class ComplexType():
    """@type use-instance-method
    ValueType: complex
    """

    def construct(self, s):
        return complex(s)
    

@fundamental_type.definition(typename="Datetime", doc="""
日付時刻型。
""")
class DatetimeType():
    """@type use-instance-method
    ValueType:
        datetime.datetime
    """

    def construct(self, s):
        pass
    
    def stringify(self, date):
        return date.strftime("%y/%m/%d (%a) %H:%M.%S")


# ----------------------------------------------------------
#
#  その他のデータ型
#
# ----------------------------------------------------------
fundamental_type.definition(typename="Tuple")(
    "machaon.types.tuple.ObjectTuple"
)
fundamental_type.definition(typename="Sheet")(
    "machaon.types.sheet.Sheet"
)
fundamental_type.definition(typename="ObjectCollection", bits=TYPE_OBJCOLTYPE)(
    "machaon.core.object.ObjectCollection"
)
fundamental_type.definition(typename="Method")(
    "machaon.core.method.Method"
)
fundamental_type.definition(typename="ProcessError")(
    "machaon.process.ProcessError"
)
fundamental_type.definition(typename="Package")(
    "machaon.types.package.AppPackageType"
)
fundamental_type.definition(typename="RootObject")(
    "machaon.types.app.RootObject"
)
fundamental_type.definition(typename="AppChamber")(
    "machaon.types.app.AppChamber"
)

#
#
# エラーオブジェクト
#
#
class NotFound(Exception):
    """
    検索したが見つからなかった
    """




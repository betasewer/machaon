import re

from machaon.core.type import Type, TypeModule, TypeDelayLoader, UnsupportedMethod
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
            Set[Method]: (name,doc,signature) メソッドのリスト
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
    

@fundamental_type.definition(typename="Any", doc="""
あらゆる型を受け入れる型。
""")
class AnyType():
    """@type
    ValueType: machaon.Any
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
    ValueType: machaon.core.message.Function
    """

    def construct(self, s):
        from machaon.core.message import Function
        return Function(s)

    def stringify(self, f):
        return f.get_expr()
    
    #
    #
    #
    def eval(self, f, context, subject):
        """ @method context
        関数を実行する。
        Params:
            subject(Object): 引数
        Returns:
            Object: 返り値
        """
        rets = f.run(subject, context)
        return rets[0]

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
        '''@method [as]
        指定の型の値へと変換する。
        stringfyメソッドを使用。
        Params:
            type (Type): 型
        Returns:
            Object: 新たな型の値
        '''
        value = type.construct_from_string(s)
        return Object(type, value)

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
    def eval(self, s, context, subject):
        """ @method context
        文字列を関数として評価する。
        Params:
            subject(Object): 引数
        Returns:
            Object: 返り値
        """
        from machaon.core.message import Function
        f = Function(s)
        return f.run_return(subject, context)
    
    def if_then(self, s, context, if_, else_):
        """ @method context
        文字列を評価し、真なら実行する。
        "@ == 32" if-then: "nekkedo" :else "hekkeo"
        Params:
            if(Function): true 節
            else(Function): false 節 
        Returns:
            Object: 返り値
        """
        from machaon.core.message import Function
        f = Function(s)
        if f.run_return(None, context).value:
            body = Function(if_)
        else:
            body = Function(else_)
        return body.run_return(None, context)
    
    #
    # その他
    #
    def location(self, s):
        """ @method
        特別なフォルダ・ファイルを名前で指定してパスを得る。
        Params:
        Returns:
            machaon.shell.Path: パス
        """
        from machaon.types.shell import special_name_to_path
        return special_name_to_path(s)

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

@fundamental_type.definition(typename="Int", doc="""
整数型。
""")
class IntType():
    """@type use-instance-method
    ValueType: int
    """

    def construct(self, s):
        return int(s, 0)

@fundamental_type.definition(typename="Float", doc="""
浮動小数点型。
""")
class FloatType():
    """@type use-instance-method
    ValueType: float
    """

    def construct(self, s):
        return float(s)

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
fundamental_type.definition(typename="Set")(
    "machaon.types.objectset.ObjectSet"
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

# ----------------------------------------------------------
#
#  実行コンテキストの参照
#
# ----------------------------------------------------------



# Desktop new glob *.docx |> add-target Xuthus.Genko new => $genko 
# | Xuthus.GenkoProcess new indent 2 => $setting 
# | $genko process $setting 
# | $genko report $genko commonpath sameext output 
#

# Desktop new glob *.docx => $file Xuthus.Genko new => $genko
# $genko add-target $file
# $genko process
# $genko inspect

# glob *.docx new Desktop => $files Genko::xuthus new => $genko
# $genko add-target $files
# $genko process
# $genko inspect

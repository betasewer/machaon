import re
import datetime

from machaon.core.type import Type, TypeModule, TypeDelayLoader, UnsupportedMethod, TYPE_ANYTYPE, TYPE_OBJCOLTYPE
from machaon.core.object import Object

fundamental_type = TypeModule()

# ----------------------------------------------------------
#
#  基本型
#
# ----------------------------------------------------------
@fundamental_type.definition(typename="Type", value_type=Type, doc="""
オブジェクトの型。
""")
class TypeType():
    """@type
    """

    def stringify(self, v):
        return "<{}>".format(v.typename)

    #
    # メソッド
    #
    def new(self, type):
        '''@method
        引数無しでコンストラクタを実行する。
        Returns:
            Object: オブジェクト
        '''
        vt = type.get_value_type()
        value = vt()
        return Object(type, value)
    
    def ctor(self, type, context, s):
        '''@method context
        文字列からインスタンスを作成する。
        Params:
            s(Str):
        Returns:
            Object: オブジェクト
        '''
        value = type.construct_from_string(context, s)
        return Object(type, value)

    def help(self, type, context):
        """ @method context
        型の説明、メソッド一覧を表示する。
        """
        docs = []
        docs.append(type.fulltypename)
        docs.extend(type.doc.splitlines())
        docs.append("［実装］\n{}".format(type.get_describer_qualname()))
        docs.append("［引数］")
        docs.extend(type.ctordoc.splitlines())
        docs.append("［メソッド］")
        context.spirit.post("message", "\n".join(docs))
        # メソッドの表示
        meths = self.methods(type, context)
        meths_sheet = context.new_object(meths, conversion="Sheet[ObjectCollection]: (names,doc,signature)")
        meths_sheet.pprint(context.spirit)

    def methods(self, type, context):
        '''@method context
        使用可能なメソッドを列挙する。
        Params:
        Returns:
            Sheet[ObjectCollection]: (names,doc,signature) メソッドのリスト
        '''
        helps = []
        from machaon.core.message import enum_selectable_method
        for meth in enum_selectable_method(type):
            names = type.get_member_identical_names(meth.get_name())
            helps.append({
                "names" : context.new_object(names),
                "#delegate" : context.new_object(meth, type="Method")
            })
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
        if type.scope is None:
            return ""
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
    
    def sheet(self, type, context):
        ''' @method context
        この型の空のSheetを作成する。
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
        from machaon.core.message import MessageEngine
        return MessageEngine(s)

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
@fundamental_type.definition(typename="Str", value_type=str, doc="""
Python.str 文字列。
""")
class StrType():
    """ @type use-instance-method
    """
    def construct(self, s):
        return s
    
    def stringify(self, v):
        return v

    #
    # メソッド
    #
    def convertas(self, s, context, type):
        '''@method context alias-name [as]
        指定の型の値へと変換する。
        stringfyメソッドを使用。
        Params:
            type (Type): 型
        Returns:
            Object: 新たな型の値
        '''
        value = type.construct_from_string(context, s)
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
        外部モジュールの変数あるいは引数無し関数呼び出しとして評価する。
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


@fundamental_type.definition(typename="Bool", value_type=bool, doc="""
Python.bool 真偽値。
""")
class BoolType():
    """@type use-instance-method
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
            if_(Function): true 節
            else_(Function): false 節 
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
            digits(Int): 桁数
        Returns:
            Any: 丸められた小数。
        """
        return round(n, digits)
    


@fundamental_type.definition(typename="Int", value_type=int, doc="""
整数型。
""")
class IntType(NumericType):
    """@type use-instance-method
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


@fundamental_type.definition(typename="Float", value_type=float, doc="""
浮動小数点型。
""")
class FloatType(NumericType):
    """@type use-instance-method
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


@fundamental_type.definition(typename="Complex", value_type=complex, doc="""
複素数型。
""")
class ComplexType():
    """@type use-instance-method
    """

    def construct(self, s):
        return complex(s)
    

@fundamental_type.definition(typename="Datetime", value_type=datetime.datetime, doc="""
日付時刻型。
""")
class DatetimeType():
    """@type use-instance-method
    """

    def construct(self, s):
        pass
    
    def stringify(self, date):
        return date.strftime("%y/%m/%d (%a) %H:%M.%S")

#
#
#
class BasicStream():
    """ ストリームの基底クラス """
    def __init__(self, source):
        self._source = source
        self._stream = None
    
    def get_path(self):
        if isinstance(self._source, str):
            return self._source
        elif hasattr(self._source, "__fspath__"):
            return self._source.__fspath__()
        import io
        if isinstance(self._source, io.FileIO):
            return self._source.name
        if hasattr(self._source, "path"): # Pathオブジェクトが返される
            return self._source.path().get()
        
        return None

    def __enter__(self):
        return self
    
    def __exit__(self, et, ev, tb):
        self.close()

    def _open_stream(self, rw, binary, encoding):
        source = self._source

        # ファイルパスから開く
        fpath = None
        if isinstance(source, str):
            fpath = source
        elif hasattr(source, "__fspath__"):
            fpath = source.__fspath__()
        if fpath:
            mode = rw[0] + ("b" if binary else "")
            return open(fpath, mode, encoding=encoding)
        
        # オブジェクトから開く
        if hasattr(source, "{}_stream".format(rw)):
            opener = getattr(source, "{}_stream".format(rw))
            return opener()
        
        # 開かれたストリームである
        import io
        if isinstance(source, io.IOBase):
            if source.closed:
                raise ValueError("Stream has already been closed")
            return source
        
        raise TypeError("'{}'からストリームを取り出せません".format(repr(source)))

    def _must_be_opened(self):
        if self._stream is None:
            raise ValueError("Stream is not opened")
    
    def close(self):
        self._must_be_opened()
        self._stream.close()
    
    
@fundamental_type.definition(typename="InputStream", doc="""
入力ストリーム
""")
class InputStream(BasicStream):
    def open(self, binary=False, encoding=None):
        self._stream = self._open_stream("read", binary=binary, encoding=encoding)
        return self
    
    def lines(self):
        self._must_be_opened()
        for l in self._stream:
            yield l
    
    def conversion_construct(self, context, value):
        return InputStream(value)
    
    def stringify(self, _v):
        return "<InputStream>"


@fundamental_type.definition(typename="OutputStream", doc="""
出力ストリーム
""")
class OutputStream(BasicStream):
    def open(self, binary=False, encoding=None):
        self._stream = self._open_stream("write", binary=binary, encoding=encoding)
        return self
    
    def write(self, v):
        self._must_be_opened()
        return self._stream.write(v)

    def conversion_construct(self, context, value):
        return OutputStream(value)
    
    def stringify(self, _v):
        return "<OutputStream>"
    
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




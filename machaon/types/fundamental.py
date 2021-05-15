import re
import datetime

from machaon.core.type import Type, TypeModule, TypeDefinition, TYPE_ANYTYPE, TYPE_OBJCOLTYPE, TYPE_USE_INSTANCE_METHOD
from machaon.core.object import Object
from machaon.core.symbol import full_qualified_name


# ----------------------------------------------------------
#
#  基本型
#
# ----------------------------------------------------------
class TypeType():
    def constructor(self, context, value):
        """ @meta 
        Params:
            Str: 型名 / クラスの完全な名前(qualname)
        """
        if isinstance(value, str):
            if "." in value:
                from machaon.core.importer import attribute_loader
                d = TypeDefinition(attribute_loader(value))
                if not d.load_declaration_docstring():
                    raise ValueError("型定義ドキュメントの解析中にエラーが発生")
                return d.define(context.type_module) # 即座にロードする
            else:
                return context.select_type(value)
        else:
            raise TypeError("value")

    def stringify(self, v):
        """ @meta """
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
        value = type.construct(context, s)
        return Object(type, value)

    def help(self, type, context, value=None):
        """ @method context
        型の説明、メソッド一覧を表示する。
        """
        docs = []
        docs.append(type.fulltypename)
        docs.extend(type.doc.splitlines())
        docs.append("［実装］\n{}".format(type.get_describer_qualname()))
        docs.append("［メソッド］")
        context.spirit.post("message", "\n".join(docs))
        # メソッドの表示
        meths = self.methods(type, context, value)
        meths_sheet = context.new_object(meths, conversion="Sheet[ObjectCollection]: (names,doc,signature)")
        meths_sheet.pprint(context.spirit)

    def methods(self, type, context, instance=None):
        '''@method context
        使用可能なメソッドを列挙する。
        Params:
        Returns:
            Sheet[ObjectCollection]: (names,doc,signature) メソッドのリスト
        '''
        helps = []
        from machaon.core.message import enum_selectable_method
        for meth in enum_selectable_method(type, instance):
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

class AnyType():
    def vars(self, v):
        """ @method
        属性の一覧を返す。
        Returns:
            Sheet[ObjectCollection]: (name, type)
        """
        return [{
            "name" : k,
            "type" : full_qualified_name(type(v))
        } for (k,v) in vars(v).items()]
    
    def pick(self, v, name):
        """ @method alias-name [#]
        属性にアクセスする。
        Params:
            name(str):
        Returns:
            Any:
        """
        return getattr(v, name)
    
    def call(self, v, *args):
        """ @method
        この値を実行する。
        Params:
            *args(Any):
        Returns:
            Any:
        """
        return v(*args)

    def constructor(self, _context, value):
        """ @meta """
        return value # そのままの値を返す
    
    def summarize(self, v):
        """ @meta """
        return "<AnyObject: {}>".format(full_qualified_name(type(v)))
    
    def stringify(self, v):
        """ @meta """
        if type(v).__repr__ is object.__repr__:
            return "<Object {:0X}({})>".format(id(v), full_qualified_name(type(v)))
        else:
            return "{}({})".format(v, full_qualified_name(type(v)))

class FunctionType():
    def constructor(self, _context, s):
        """ @meta """
        from machaon.core.message import MessageEngine
        return MessageEngine(s)

    def stringify(self, f):
        """ @meta """
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


class StoredObject():
    def __init__(self, object):
        self.object = object

    def get_object(self):
        """ @method alias-name [object obj]
        オブジェクトを取得する。
        Returns:
            Object:
        """
        return self.object
    
    def bind(self, context, name):
        """ @method context [=>]
        オブジェクトを名前に束縛する。
        Params:
            name(Str):
        """
        context.push_object(name, self.object)

    def constructor(self, context, value):
        """ @meta """
        # 外部ファイルからロードする
        from machaon.core.persistence import get_persistent_path, load_persistent_file
        from machaon.types.shell import Path
        if isinstance(value, str):
            path = get_persistent_path(context.root, value)
            o = load_persistent_file(context, path)
            name = value
        elif isinstance(value, Path):
            path = value
            o = load_persistent_file(context, path)
            name = None
        else:
            raise TypeError("")
        
        if name is not None:
            context.push_object(name, o)
            context.spirit.post("message", "'{}'よりオブジェクト'{}'をロード".format(path, name))
        else:
            context.spirit.post("message", "'{}'より無名オブジェクトをロード".format(path))
        
        return StoredObject(o)



# ----------------------------------------------------------
#
#  Pythonのビルトイン型
#
# ----------------------------------------------------------
class StrType():
    def constructor(self, _context, v):
        """ @meta """
        return str(v)
    
    def stringify(self, v):
        """ @meta """
        return v
    
    #
    # メソッド
    #
    def convertas_literals(self, s, context):
        """ @method context alias-name [as-literal]
        値を適当な型に変換する。
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


class BoolType():
    def constructor(self, _context, s):
        """ @meta """
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
    
class IntType(NumericType):
    def constructor(self, _context, s):
        """ @meta """
        return int(s, 0)
    
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
    
    def pow(self, n, exp):
        """ @method
        べき乗を計算する。
        Params:
            exp(Int):
        Returns:
            Int:
        """
        return pow(n, exp)

class FloatType(NumericType):
    def constructor(self, _context, s):
        """ @meta """
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

class ComplexType():
    def constructor(self, _context, s):
        """ @meta """
        return complex(s)

class DatetimeType():
    def constructor(self, _context, s):
        """ @meta """
    
    def stringify(self, date):
        """ @meta """
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
    

class InputStream(BasicStream):
    def open(self, binary=False, encoding=None):
        self._stream = self._open_stream("read", binary=binary, encoding=encoding)
        return self
    
    def lines(self):
        self._must_be_opened()
        for l in self._stream:
            yield l
    
    def constructor(self, _context, value):
        """ @meta """
        return InputStream(value)
    
    def stringify(self, _v):
        """ @meta """
        return "<InputStream>"


class OutputStream(BasicStream):
    def open(self, binary=False, encoding=None):
        self._stream = self._open_stream("write", binary=binary, encoding=encoding)
        return self
    
    def write(self, v):
        self._must_be_opened()
        return self._stream.write(v)

    def constructor(self, _context, value):
        """ @meta """
        return OutputStream(value)

    def stringify(self, _v):
        """ @meta """
        return "<OutputStream>"
    
# ----------------------------------------------------------
#
#  データ型登録
#
# ----------------------------------------------------------
fundamental_type = TypeModule()
typedef = fundamental_type.definitions()
typedef.Type("""
    オブジェクトの型。
    """,
    value_type=Type, 
    describer="machaon.types.fundamental.TypeType", 
)
typedef.Any(
    """
    あらゆるオブジェクトを受け入れる型。
    """,
    describer="machaon.types.fundamental.AnyType",
    bits=TYPE_ANYTYPE|TYPE_USE_INSTANCE_METHOD,
)
typedef.Function( # Message
    """
    1引数をとるメッセージ。
    """,
    value_type="machaon.core.message.MessageEngine",
    describer="machaon.types.fundamental.FunctionType",
)
typedef.Str(
    """
    文字列。
    """,
    value_type=str, 
    describer="machaon.types.fundamental.StrType",
    bits=TYPE_USE_INSTANCE_METHOD
)
typedef.Bool(
    """
    真偽値。
    """,
    value_type=bool, 
    describer="machaon.types.fundamental.BoolType",
    bits=TYPE_USE_INSTANCE_METHOD
)
typedef.Int(
    """
    整数。
    """,
    value_type=int,
    describer="machaon.types.fundamental.IntType",
    bits=TYPE_USE_INSTANCE_METHOD
)
typedef.Float(
    """
    浮動小数点数。
    """,
    value_type=float, 
    describer="machaon.types.fundamental.FloatType",
    bits=TYPE_USE_INSTANCE_METHOD
)
typedef.Complex(
    """
    複素数。
    """,
    value_type=complex, 
    describer="machaon.types.fundamental.ComplexType",
    bits=TYPE_USE_INSTANCE_METHOD
)
typedef.Datetime(
    """
    日付時刻。
    """,
    value_type=datetime.datetime, 
    describer="machaon.types.fundamental.DatetimeType",
    bits=TYPE_USE_INSTANCE_METHOD
)
typedef.Tuple(
    """
    任意の型のタプル。
    """,
    value_type="machaon.types.tuple.ObjectTuple",
)
typedef.Sheet(
    """
    同型の配列から作られる表。
    """,
    value_type="machaon.types.sheet.Sheet",
)
typedef.ObjectCollection(
    """
    辞書。
    """,
    value_type="machaon.core.object.ObjectCollection",
    bits=TYPE_OBJCOLTYPE
)
typedef.Method(
    """
    メソッド。
    """,
    value_type="machaon.core.method.Method"
)
typedef.InvocationContext(
    """
    メソッドの呼び出しコンテキスト。
    """,
    value_type="machaon.core.invocation.InvocationContext"
)
typedef.Process(
    """
    メッセージを実行するプロセス。
    """,
    value_type="machaon.process.Process"
)
typedef.ProcessChamber(
    """
    プロセスのリスト。
    """,
    value_type="machaon.process.ProcessChamber",
    describer="machaon.types.app.AppChamber"
)
typedef.Error( # Error
    """
    発生したエラー。
    """,
    value_type="machaon.process.ProcessError"
)
typedef.Package(
    """
    パッケージ。
    """,
    value_type="machaon.package.package.Package",
    describer="machaon.types.package.AppPackageType"
)
typedef.Stored(
    """
    外部ファイルのオブジェクトを操作する。
    """,
    value_type="machaon.types.fundamental.StoredObject",
)
typedef.RootObject(
    """
    アプリのインスタンス。
    """,
    value_type="machaon.types.app.RootObject"
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




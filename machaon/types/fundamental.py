import re
import datetime

from machaon.core.type import (
    BadTypeDeclaration, BadTypename, Type, TypeModule, TypeDefinition, 
    TYPE_ANYTYPE, TYPE_NONETYPE, TYPE_OBJCOLTYPE, TYPE_USE_INSTANCE_METHOD
)
from machaon.core.typedecl import PythonType, TypeProxy, parse_type_declaration
from machaon.core.object import Object
from machaon.core.symbol import SIGIL_PYMODULE_DOT, full_qualified_name


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
        decl = parse_type_declaration(value)
        return decl.instance(context)

    def stringify(self, v):
        """ @meta """
        prefix = ""
        if isinstance(v, PythonType):
            prefix = "*"
        return "<{}{}>".format(prefix, v.get_conversion())

    #
    # メソッド
    #
    def load(self, type, context):
        '''@method context
        値がクラスであれば型定義として読み込む。
        Returns:
            Type: 読み込まれた型
        '''
        if isinstance(type, PythonType):
            raise ValueError("既にロード済みです")
        d = TypeDefinition(type.type)
        if not d.load_declaration_docstring():
            raise BadTypeDeclaration()
        return d.define(context.type_module) # 即座にロードする

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

    def help(self, typ, context, value=None):
        """ @method context
        型の説明、メソッド一覧を表示する。
        """
        docs = []
        docs.append("{} [{}]".format(typ.get_conversion(), type(typ).__name__))
        docs.extend(typ.get_document().splitlines())
        docs.append("［実装］\n{}".format(typ.get_describer_qualname()))
        docs.append("［メソッド］")
        context.spirit.post("message", "\n".join(docs))
        # メソッドの表示
        meths = self.methods(typ, context, value)
        meths_sheet = context.new_object(meths, conversion="Sheet[ObjectCollection](names,doc,signature,source)")
        meths_sheet.pprint(context.spirit)

    def methods(self, typ, context, instance=None):
        '''@method context
        使用可能なメソッドを列挙する。
        Returns:
            Sheet[ObjectCollection](names,doc,signature,source): メソッドのリスト
        '''
        helps = []
        from machaon.core.message import enum_selectable_method
        for names, meth in enum_selectable_method(typ, instance):
            if isinstance(meth, Exception):
                helps.append({
                    "names" : context.new_object(names),
                    "doc" : "!{}: {}".format(type(meth).__name__, meth),
                    "signature" : "",
                    "source" : ""
                })
            else:
                source = "user"
                if meth.is_from_class_member():
                    source = "class"
                elif meth.is_from_instance_member():
                    source = "instance"
                helps.append({
                    "names" : context.new_object(names),
                    "source" : context.new_object(source),
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
        return type.get_typename()
    
    def doc(self, type):
        ''' @method
        型の説明。
        Returns:
            Str:
        '''
        return type.get_document()
    
    def scope(self, type):
        ''' @method
        スコープ名。
        Returns:
            Str:
        '''
        t = type.get_typedef()
        if t:
            if type.scope is None:
                return ""
            return type.scope

    def conversion(self, type):
        ''' @method
        完全な型名。
        Returns:
            Str:
        '''
        return type.get_conversion()
    
    def describer(self, type):
        ''' @method
        実装の場所を示す文字列。
        Returns:
            Str:
        '''
        return type.get_describer_qualname()

    def is_python_type(self, type):
        ''' @method
        Pythonの型から直接作られたインスタンスか。
        Returns:
            bool:
        '''
        return isinstance(type, PythonType)
    

class AnyType():
    def vars(self, v):
        """ @method
        属性の一覧を返す。
        Returns:
            Sheet[ObjectCollection](name, type, value):
        """
        from machaon.core.importer import enum_attributes
        items = []
        for name in enum_attributes(type(v), v):
            value = getattr(v, name, None)
            items.append({
                "name" : name,
                "type" : full_qualified_name(type(value)),
                "value" : str(value),
            })
        return items
    
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
        return "<{} object>".format(full_qualified_name(type(v)))
    
    def stringify(self, v):
        """ @meta """
        tn = full_qualified_name(type(v))
        if type(v).__repr__ is object.__repr__:
            return "<{} id={:0X}>".format(tn, id(v))
        else:
            return "{}({})".format(v, tn)


class NoneType():
    def constructor(self, _context, _s):
        """ @meta 
        いかなる引数もNoneに変換する
        """
        return None

    def stringify(self, f):
        """ @meta """
        return "<None>"


class FunctionType():
    def constructor(self, context, s, qualifier=None):
        """ @meta 
        Params:
            Str:
            qualifier(Str): None|(seq)uential
        """
        from machaon.core.message import parse_function, parse_sequential_function
        if qualifier is None:
            f = parse_function(s)
        elif qualifier == "sequential" or qualifier == "seq":
            f = parse_sequential_function(s, context)
        return f

    def stringify(self, f):
        """ @meta """
        return f.get_expression()
    
    #
    #
    #
    def do(self, f, context, _app, subject=None):
        """ @task context
        関数を実行する。
        Params:
            subject(Object): *引数
        Returns:
            Any: 返り値
        """
        r = f.run(subject, context)
        return r
        
    def apply_clipboard(self, f, context, app):
        """ @task context
        クリップボードのテキストを引数として関数を実行する。
        """
        text = app.clipboard_paste()
        newtext = f.run(context.new_object(text), context).value
        app.clipboard_copy(newtext, silent=True)
        app.root.post_stray_message("message", "クリップボード上で変換: {} -> {}".format(text, newtext))
    

# ----------------------------------------------------------
#
#  Pythonのビルトイン型
#
# ----------------------------------------------------------
class StrType():
    def constructor(self, _context, v):
        """ @meta 
        Params:
            Any:
        """
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

    def join(self, s, values):
        """@method
        文字を結合する。
        Params:
            values(Tuple):
        Returns:
            Str:
        """
        return s.join(values)
        
    def normalize(self, s, form):
        """
        Unicode正規化を行う。
        Params:
            form(str): NFD, NFC, NFKD, NFKCのいずれか
        Returns:
            Str:
        """
        import unicodedata
        return unicodedata.normalize(form, s) # 全角と半角など
    
    # 
    # コード実行
    #
    def do(self, s, context, _app, subject=None):
        """ @task context
        文字列をメッセージとして評価する。例外を発生させる。
        Params:
            subject(Object): *引数
        Returns:
            Object: 返り値
        """
        from machaon.core.message import run_function
        r = run_function(s, subject, context, raiseerror=True)
        return r
    
    def do_external(self, s, context, app):
        """ @task context [doex do-ex]
        文字列を外部ファイルの名前として評価し、実行して返す。
        Returns:
            Object: 返り値
        """
        o = context.new_object(s, type="Stored")
        ret = o.value.do(context, app)
        return ret

    def do_python(self, expr, _app):
        """ @task [dopy do-py]
        Pythonの式として評価し、実行して返す。
        式の前に{name1 name2...}と書いてモジュールをインポートできる。
        Returns:
            Any:
        """
        expr = expr.strip()
        if expr.startswith("{"):
            from machaon.core.importer import module_loader
            rparen = expr.find("}")
            if rparen == -1:
                raise ValueError("モジュール指定の括弧が閉じていません")
            imports = expr[1:rparen].split()
            body = expr[rparen+1:]
        else:
            imports = []
            body = expr

        glob = {}
        for impname in imports:
            loader = module_loader(impname)
            glob[impname] = loader.load_module()
        
        return eval(body, glob, {})
    
    def call_python(self, expr, _app, *params):
        """ @task alias-name [call]
        Pythonの関数または定数を評価する。
        Params:
            *params(Any): 引数
        Returns:
            Any:
        """
        from machaon.core.importer import attribute_loader
        loader = attribute_loader(expr)
        value = loader()
        if callable(value):
            return value(*params)
        else:
            # 引数は無視される
            return value
    
    def run_command(self, string, app, *params):
        """ @task
        コマンドを実行し、終わるまで待つ。入出力をキャプチャする。
        Params:
            *params(Any): コマンド引数
        """
        if not string:
            return
        from machaon.types.shell import run_command_capturing
        pa = [string, *params]
        run_command_capturing(app, pa)

    # 
    # その他
    #
    def copy(self, string, spirit):
        """ @task
        クリップボードに文字列をコピーする。
        """
        spirit.clipboard_copy(string)


class BoolType():
    def constructor(self, _context, s):
        """ @meta 
        Params:
            Any:
        """
        if s == "True":
            return True
        elif s == "False":
            return False
        else:
            return bool(s)
    
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
        if b:
            body = if_
        else:
            body = else_
        return body.run_here(context) # コンテキストを引き継ぐ

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
        """ @meta 
        Params:
            Any:
        """
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
        """ @meta 
        Params:
            Any:
        """
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
        """ @meta 
        Params:
            Any:
        """
        return complex(s)

class DatetimeType():
    def constructor(self, _context, s):
        """ @meta 
        Params:
            Str
        """
        return datetime.datetime.fromisoformat(s)
    
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
    value_type=TypeProxy, 
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
    value_type="machaon.core.message.FunctionExpression",
    describer="machaon.types.fundamental.FunctionType",
)
typedef["None"](
    """
    None。
    """,
    value_type=type(None), 
    describer="machaon.types.fundamental.NoneType",
    bits=TYPE_NONETYPE,
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
typedef.Context(
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
    value_type="machaon.types.stacktrace.ErrorObject"
)
typedef.TracebackObject(
    """
    トレースバック。
    """,
    value_type="machaon.types.stacktrace.TracebackObject"
)
typedef.FrameObject(
    """
    フレームオブジェクト。
    """,
    value_type="machaon.types.stacktrace.FrameObject"
)
typedef.Package(
    """
    パッケージ。
    """,
    value_type="machaon.package.package.Package",
    describer="machaon.types.package.AppPackageType"
)
typedef.PyModule(
    """
    Pythonのモジュール。
    """,
    value_type="machaon.types.package.Module",
)
typedef.Stored(
    """
    外部ファイルのオブジェクトを操作する。
    """,
    value_type="machaon.core.persistence.StoredMessage",
)
typedef.RootObject(
    """
    アプリのインスタンス。
    """,
    value_type="machaon.types.app.RootObject"
)
typedef.AppTestObject(
    """
    アプリのテストインスタンス。
    """,
    value_type="machaon.types.app.AppTestObject"
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





from machaon.core.type import (
    BadTypeDeclaration, TypeModule, TypeDefinition, 
    TYPE_NONETYPE, TYPE_OBJCOLTYPE, TYPE_USE_INSTANCE_METHOD
)
from machaon.core.typedecl import PythonType, TypeProxy, parse_type_declaration
from machaon.core.object import Object

#
#
#  言語の基本機能に関する型
#
#
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
    

class NoneType():
    """ PythonのNone型。 """
    def constructor(self, _context, _s):
        """ @meta 
        いかなる引数もNoneに変換する
        """
        return None

    def stringify(self, f):
        """ @meta """
        return "<None>"


class BoolType():
    """ PythonのBool型。 """
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
    

#
#
# エラーオブジェクト
#
#
class NotFound(Exception):
    """
    検索したが見つからなかった
    """
    
# ----------------------------------------------------------
#
#  データ型登録
#
# ----------------------------------------------------------
def fundamental_types():
    module = TypeModule()
    typedef = module.definitions()
    typedef.Type("""
        オブジェクトの型。
        """,
        value_type=TypeProxy, 
        describer="machaon.types.fundamental.TypeType", 
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
    typedef.Bool(
        """
        真偽値。
        """,
        value_type=bool, 
        describer="machaon.types.fundamental.BoolType",
    )
    typedef.Str(
        """
        文字列。
        """,
        value_type=str, 
        describer="machaon.types.string.StrType"
    )
    typedef.Int(
        """
        整数。
        """,
        value_type=int,
        describer="machaon.types.numeric.IntType",
    )
    typedef.Float(
        """
        浮動小数点数。
        """,
        value_type=float, 
        describer="machaon.types.numeric.FloatType",
    )
    typedef.Complex(
        """
        複素数。
        """,
        value_type=complex, 
        describer="machaon.types.numeric.ComplexType",
    )
    typedef.Datetime(
        """
        日付時刻。
        """,
        value_type="datetime.datetime", 
        describer="machaon.types.dateandtime.DatetimeType",
        bits=TYPE_USE_INSTANCE_METHOD
    )
    typedef.Date(
        """
        日付。
        """,
        value_type="datetime.date", 
        describer="machaon.types.dateandtime.DateType",
        bits=TYPE_USE_INSTANCE_METHOD
    )
    typedef.Time(
        """
        時刻。
        """,
        value_type="datetime.time", 
        describer="machaon.types.dateandtime.TimeType",
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
    return module





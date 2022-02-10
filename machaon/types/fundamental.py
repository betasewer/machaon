
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
    """ @type [Type]
    型そのものを表す。
    ValueType:
        machaon.core.typedecl.TypeProxy
    """
    def constructor(self, context, value):
        """ @meta context
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
    """ @type [None]
    PythonのNone型。 
    """
    def constructor(self, _s):
        """ @meta 
        いかなる引数もNoneに変換する
        """
        return None

    def stringify(self, f):
        """ @meta """
        return "<None>"

class BoolType():
    """ @type [Bool]
    PythonのBool型。 
    ValueType:
        bool
    """
    def constructor(self, s):
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
    """ @type [Function]
    1引数をとるメッセージ。
    ValueType:
        machaon.core.message.FunctionExpression
    Params:
        qualifier(Str): None|(seq)uential
    """
    def constructor(self, context, s, qualifier=None):
        """ @meta context
        Params:
            Str:
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
# ジェネリックなサブタイプ
#
#
class Identity:
    """ @type subtype 
    元の値に変更を加えない。Flow用。
    BaseType:
        Any:
    """
    def constructor(self, value):
        """ @meta """
        return value
    
    def reflux(self, value):
        """ @meta """
        return value


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
    for qualname in [
        "machaon.types.fundamental.TypeType",       # Type
        "machaon.types.fundamental.FunctionType",   # Function
        "machaon.types.fundamental.BoolType",       # Bool
        "machaon.types.string.StrType",             # Str
        "machaon.types.numeric.IntType",            # Int
        "machaon.types.numeric.FloatType",          # Float
        "machaon.types.numeric.ComplexType",        # Complex
        "machaon.types.tuple.ObjectTuple",          # Tuple
        "machaon.types.sheet.Sheet",                # Sheet
        "machaon.types.fundamental.Identity",       # T:Identity
        # エラー型
        "machaon.core.method.Method",               # Method
        "machaon.core.invocation.InvocationContext",# Context
        "machaon.process.Process",                  # Process
        "machaon.types.stacktrace.ErrorObject",     # Error
        "machaon.types.stacktrace.TracebackObject", # TracebackObject
        "machaon.types.stacktrace.FrameObject",     # FrameObject
        "machaon.types.package.AppPackageType",     # Package
        "machaon.types.package.Module",             # PyModule
        # システム型
        "machaon.core.persistence.StoredMessage",   # Stored
        "machaon.types.app.RootObject",             # RootObject
    ]:
        module.load_definition(qualname)

    # None
    td = module.load_definition("machaon.types.fundamental.NoneType")
    td.value_type = type(None)
    td.bits |= TYPE_NONETYPE

    # ObjectCollection
    td = module.load_definition("machaon.core.object.ObjectCollection")
    td.bits |= TYPE_OBJCOLTYPE

    return module





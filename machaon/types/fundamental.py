
from machaon.core.type.type import TYPE_NONETYPE, TYPE_OBJCOLTYPE, TYPE_USE_INSTANCE_METHOD
from machaon.core.type.typemodule import TypeModule
from machaon.core.type.decl import parse_type_declaration, TypeDecl
from machaon.core.type.pytype import PythonType

from machaon.core.symbol import QualTypename

from machaon.core.object import Object

#
#
#  言語の基本機能に関する型
#
#
class TypeType:
    """ @type [Type]
    型そのものを表す。
    ValueType:
        machaon.core.type.decl.TypeProxy
    """
    def constructor(self, context, value):
        """ @meta context
        Params:
            value(Any): 型表現 / 型の完全な名前(qualname) / パース済みの型宣言
        """
        if isinstance(value, str):
            decl = parse_type_declaration(value)
            return decl.instance(context)
        elif isinstance(value, QualTypename):
            return context.select_type(value)
        elif isinstance(value, TypeDecl):
            return value.instance(context)
        else:
            raise TypeError("型の表現あるいは完全な型名が必要です")

    def stringify(self, v):
        """ @meta """
        prefix = ""
        if isinstance(v, PythonType):
            prefix = "*"
        return "<{}{}>".format(prefix, v.get_conversion())

    #
    # メソッド
    #
    def new(self, type, context, *args):
        '''@method context
        コンストラクタを実行する。
        Params:
            *args(Any): 引数
        Returns:
            Object: オブジェクト
        '''
        if not args:
            vt = type.get_value_type()
            value = vt()
            return Object(type, value)
        else:
            value = type.construct(context, *args)
            return Object(type, value)
    
    def instance(self, type, context, *args):
        """ @method context
        型引数を束縛した型インスタンスを作成する。
        Params:
            *args(Any):
        Returns:
            Type:
        """
        return type.instantiate(context, args)

    def help(self, typ, context, app, value=None):
        """ @task context
        型の説明、メソッド一覧を表示する。
        """
        docs = []
        docs.append("{} [{}]".format(typ.get_conversion(), type(typ).__name__))
        docs.extend(typ.get_document().splitlines())
        docs.append("［実装］\n{}".format(typ.get_describer_qualname()))
        docs.append("［メソッド］")
        app.post("message", "\n".join(docs))
        # メソッドの表示
        meths = self.methods(typ, context, app, value)
        meths_sheet = context.new_object(meths, conversion="Sheet[Method]")
        meths_sheet.value.view(context, "names", "signature", "doc")
        meths_sheet.pprint(app)

    def methods(self, typ, context, app, instance=None):
        '''@task context
        使用可能なメソッドを列挙する。
        Returns:
            Sheet[Method]: メソッドのリスト
        Decorates:
            @ view: names doc signature source
        '''
        helps = []
        from machaon.core.message import enum_selectable_method
        with app.progress_display():
            for names, meth in enum_selectable_method(typ, instance):       
                app.interruption_point(progress=1)
                if isinstance(meth, Exception):
                    helps.append({
                        "#extend" : None,
                        "names" : context.new_object(names),
                        "doc" : "!{}: {}".format(type(meth).__name__, meth),
                        "signature" : "",
                    })
                else:
                    helps.append({
                        "#extend" : context.new_object(meth, type="Method"),
                        "names" : context.new_object(names),
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

    def describers(self, type):
        ''' @method
        mixinを含めたすべての実装場所を示す文字列を返す。
        Returns:
            Sheet[]:
        Decorates:
            @ view: name describer:
        '''
        return [{"name": x.get_full_qualname(), "describer": x} for x in type.get_all_describers()]

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
        """ @method context
        文字列を評価し、真なら実行する。コンテキストを引き継ぐ。
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
    for fulltypename in [
        "Type:machaon.types.fundamental.TypeType",       # Type
        "Bool:machaon.types.fundamental.BoolType",       # Bool
        "Str:machaon.types.string.StrType",              # Str
        "Int:machaon.types.numeric.IntType",             # Int
        "Float:machaon.types.numeric.FloatType",         # Float
        "Complex:machaon.types.numeric.ComplexType",     # Complex
        "Function:machaon.core.function.FunctionType",   # Function
        "Tuple:machaon.types.tuple.ObjectTuple",         # Tuple
        "Sheet:machaon.types.sheet.Sheet",               # Sheet
        # エラー型
        "Error:machaon.types.stacktrace.ErrorObject",      # Error
        "TracebackObject:machaon.types.stacktrace.TracebackObject", # TracebackObject
        "FrameObject:machaon.types.stacktrace.FrameObject",         # FrameObject
        "Context:machaon.core.context.InvocationContext",  # Context
        "Process:machaon.process.Process",                 # Process
        "PyModule:machaon.types.package.Module",           # PyModule
        # システム型
        "Method:machaon.core.method.Method",               # Method
        "Package:machaon.types.package.AppPackageType",    # Package
        "Stored:machaon.core.persistence.StoredMessage",   # Stored
        "ShellTheme:machaon.ui.theme.ShellTheme",          # ShellTheme
        "RootObject:machaon.types.app.RootObject",         # RootObject
    ]:
        module.define(fulltypename, describername="machaon.core")

    # None
    module.define("None:machaon.types.fundamental.NoneType", value_type=type(None), bits=TYPE_NONETYPE)

    # ObjectCollection
    from machaon.core.type.fundamental import ObjectCollectionType
    module.define("ObjectCollection:machaon.core.object.ObjectCollection", bits=TYPE_OBJCOLTYPE, typeclass=ObjectCollectionType)

    return module






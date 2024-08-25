

from machaon.core.type.decl import parse_type_declaration, TypeDecl
from machaon.core.type.pytype import PythonType

from machaon.core.symbol import QualTypename, full_qualified_name

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

        special = typ is context.type_module.ObjectType or typ is context.type_module.AnyType
        tdef = typ.get_typedef()
        if special:
            pass
        elif tdef is not None:
            docs.append("［実装］")
            docs.extend([x.get_value_full_qualname() for x in tdef.get_all_describers()])
            docs.append("")
        else:
            vt = typ.get_value_type()
            if vt:
                docs.append("［値型］")
                docs.append(full_qualified_name(vt))
                docs.append("")
        app.post("message", "\n".join(docs))

        # 型引数の表示
        if tdef and len(tdef.get_type_params()) > 0:
            app.post("message", "［型引数］")
            from machaon.core.method import Method, METHOD_EXTERNAL
            meth = Method(tdef.get_typename(), params=tdef.get_type_params(), flags=METHOD_EXTERNAL)
            meth.add_result_self(tdef)
            app.post("message", meth.get_signature() + "\n")

        # コンストラクタの表示
        if tdef:
            app.post("message", "［コンストラクタ］")
            meth = tdef.get_constructor()
            app.post("message", meth.get_signature() + "\n")

        # メソッドの表示
        app.post("message", "［メソッド］")
        meths = self.methods(typ, context, app, value)
        intr = []
        extr = []
        for meth in meths:
            if meth["#extend"] and meth["#extend"].value.is_external():
                extr.append(meth)
            else:
                intr.append(meth)
    
        # 通常メソッド
        if intr:
            meths_sheet = context.new_object(intr, conversion="Sheet[Method]")
            meths_sheet.value.view(context, "names", "signature", "doc")
            app.instant_pprint(meths_sheet)

        # 外部メソッド
        if extr:
            app.post("message", "［外部メソッド］")
            meths_sheet = context.new_object(extr, conversion="Sheet[Method]")
            meths_sheet.value.view(context, "names", "signature", "doc")
            app.instant_pprint(meths_sheet)

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
                    meth.resolve_type(context) # 型をすべてロードする
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
    
    def mixin(self, type, context, *describers):
        ''' @method context
        スコープ名。
        Params:
            +describers(Str): デスクライバ名
        '''
        for desc in describers:
            context.type_module.mixin(type, desc)


class BoolType:
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
fundamental_typenames = [QualTypename.parse(x) for x in [
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
    # 特殊
    "ObjectCollection:machaon.core.object.ObjectCollection", # ObjectCollection
]]

fundamental_describer_name = "machaon.core"

def fundamental_types():
    from machaon.core.type.typemodule import TypeModule
    module = TypeModule()
    for fulltypename in fundamental_typenames:
        module.define(fulltypename, describername=fundamental_describer_name)
    from machaon.core.type.fundamental import NoneType
    module.add_special_type(NoneType(), describername=fundamental_describer_name)
    return module



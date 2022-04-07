from machaon.core.symbol import (
    SIGIL_SCOPE_RESOLUTION, SIGIL_PYMODULE_DOT, SIGIL_SUBTYPE_SEPARATOR,
    BadTypename, full_qualified_name, disp_qualified_name, PythonBuiltinTypenames
)

METHODS_BOUND_TYPE_TRAIT_INSTANCE = 1
METHODS_BOUND_TYPE_INSTANCE = 2



def instantiate_args(thistype, params, context, argvals):
    """ 引数を型チェックし生成する """
    from machaon.core.method import Method
    method = Method(params=params)
    if not method.check_param_count(len(argvals)):
        raise TypeError("引数より多くの型引数が与えられました: {} ({})".format(str(thistype), ",".join([str(x) for x in argvals])))

    if argvals:
        argvals = method.make_argument_row(context, argvals, construct=True)
    return argvals



#
# 型パラメータを与えられたインスタンス。
# ・オブジェクトの生成
# ・代入可能性の判定
#
class TypeProxy:
    def get_typedef(self):
        """ 型定義オブジェクトを返す
        Returns:
            Type: 
        """
        raise NotImplementedError()
    
    def get_value_type(self):
        """ 値型を返す
        Returns:
            type:
        """
        raise NotImplementedError()
    
    def get_typename(self):
        """ 型名を返す
        Returns:
            Str: 
        """
        raise NotImplementedError()

    def get_conversion(self):
        """ 型宣言を返す 
        Returns:
            Str:
        """
        raise NotImplementedError()

    def get_describer(self, mixin):
        """ 実装定義オブジェクトを返す
        Params:
            mixin(Int): ミキシン実装のインデックス
        Returns:
            Any:
        """
        raise NotImplementedError()

    def get_describer_qualname(self, mixin=None):
        """ 実装定義オブジェクトの名前を返す
        Returns:
            Str:
        """
        describer = self.get_describer(mixin)
        if isinstance(describer, type):
            return full_qualified_name(describer)
        else:
            return str(describer)
    
    def get_document(self):
        """
        Returns:
            Str:
        """
        raise NotImplementedError()
    
    def check_type_instance(self, type):
        """ 互換性のあるTypeインスタンスか """
        raise NotImplementedError()

    def check_value_type(self, valtype):
        """ 互換性のある値型か """
        raise NotImplementedError()
    
    def instantiate(self, context, args):
        """ 型引数を型変換し、束縛したインスタンスを生成する """
        raise NotImplementedError()

    def instantiate_params(self):
        raise NotImplementedError()

    # メソッド関連
    def select_method(self, name):
        """ メソッドを名前で検索する
        Returns:
            Optional[Method]:
        """
        raise NotImplementedError()
        
    def is_selectable_method(self, name):
        """ メソッドが存在するか確認する
        Returns:
            Bool:
        """
        raise NotImplementedError()

    def enum_methods(self):
        """ メソッドを列挙する
        Yields:
            Tuple[List[str], Method]: メソッド名のリスト、メソッドオブジェクト
        """
        raise NotImplementedError()
    
    def get_methods_bound_type(self):
        """ メソッドへのインスタンスの紐づけ方のタイプを返す
        Returns:
            Int: METHODS_BOUND_TYPE_XXX
        """
        raise NotImplementedError()

    def is_selectable_instance_method(self):
        """ インスタンスメソッドを参照可能か        
        """
        raise NotImplementedError()

    # 特殊メソッド
    def constructor(self, context, value):
        """ オブジェクトを構築する """
        raise NotImplementedError()
    
    def construct(self, context, value):
        """ オブジェクトを構築して値を返す """
        if self.check_value_type(type(value)):
            return value # 変換の必要なし
        ret = self.constructor(context, value)
        if not self.check_value_type(type(ret)):
            raise ConstructorReturnTypeError(self, type(ret))
        return ret

    def construct_obj(self, context, value):
        """ Objectのインスタンスを返す """
        convval = self.construct(context, value)
        return self.new_object(convval)
    
    def new_object(self, value, *, object_type=None):
        """ この型のオブジェクトを作る。型変換は行わない """
        from machaon.core.object import Object
        if isinstance(value, Object):
            if value.type.check_type_instance(self):
                raise ValueError("'{}' -> '{}' 違う型のオブジェクトです".format(value.get_typename(), self.typename))
            return value
        else:
            if not self.check_value_type(type(value)):
                raise ValueError("'{}' -> '{}' 値の型に互換性がありません".format(type(value).__name__, self.typename))
            if object_type is None:
                return Object(self, value)
            else:
                return object_type(self, value)

    def rebind_constructor(self, args):
        """ コンストラクタ引数を新たに束縛しなおしたインスタンスを作成する """
        t = self.get_typedef()
        if t is None:
            raise ValueError("No typedef is available")
        return TypeInstance(t, args)

    def stringify_value(self, value):
        raise NotImplementedError()
    
    def summarize_value(self, value):
        raise NotImplementedError()

    def pprint_value(self, app, value):
        raise NotImplementedError()

    def reflux_value(self, value):
        raise NotImplementedError()
    
    # 基本型の判定
    def is_none_type(self):
        raise NotImplementedError()

    def is_object_collection_type(self):
        raise NotImplementedError()
        
    def is_type_type(self):
        raise NotImplementedError()
    
    def is_function_type(self):
        raise NotImplementedError()


class RedirectProxy(TypeProxy):
    # typedef の先の実装に転送する
    def redirect(self):
        raise NotImplementedError()
    
    def get_value_type(self):
        return self.redirect().get_value_type()
    
    def get_typename(self):
        return self.redirect().get_typename()

    def get_conversion(self):
        return self.redirect().get_conversion()

    def get_describer(self, mixin):
        return self.redirect().get_describer(mixin)

    def get_describer_qualname(self, mixin=None):
        return self.redirect().get_describer_qualname(mixin)
        
    def get_document(self):
        return self.redirect().get_document()
    
    def check_type_instance(self, type):
        return self.redirect().check_type_instance(type)

    def check_value_type(self, valtype):
        return self.redirect().check_value_type(valtype)
        
    def instantiate(self, context, args):
        return self.redirect().instantiate(context, args)

    def instantiate_params(self):
        return self.redirect().instantiate_params()

    def select_method(self, name):
        return self.redirect().select_method(name)

    def is_selectable_method(self, name):
        return self.redirect().is_selectable_method(name)

    def enum_methods(self):
        return self.redirect().enum_methods()
    
    def get_methods_bound_type(self):
        return self.redirect().get_methods_bound_type()

    def is_selectable_instance_method(self):
        return self.redirect().is_selectable_instance_method()

    def constructor(self, context, value):
        return self.redirect().constructor(context, value)

    def stringify_value(self, value):
        return self.redirect().stringify_value(value)
    
    def summarize_value(self, value):
        return self.redirect().summarize_value(value)

    def pprint_value(self, spirit, value):
        return self.redirect().pprint_value(spirit, value)
    
    def reflux_value(self, value):
        return self.redirect().reflux_value(value)
    
    def is_none_type(self):
        return self.redirect().is_none_type()

    def is_object_collection_type(self):
        return self.redirect().is_object_collection_type()
        
    def is_type_type(self):
        return self.redirect().is_type_type()

    def is_function_type(self):
        return self.redirect().is_function_type()


class DefaultProxy(TypeProxy):
    # デフォルト値を提供する
    def get_typedef(self):
        return None
    
    def get_document(self):
        return "<no document>"

    def get_methods_bound_type(self):
        return METHODS_BOUND_TYPE_INSTANCE

    def is_selectable_instance_method(self):
        return False

    def is_none_type(self):
        return False

    def is_object_collection_type(self):
        return False
        
    def is_type_type(self):
        return False

    def is_function_type(self):
        return False

#
#
#
class TypeInstance(RedirectProxy):
    """
    引数を含むインスタンス
    """
    def __init__(self, type, args=None):
        self.type = type
        self._args = args or []

    def get_typedef(self):
        return self.type

    def redirect(self):
        return self.type
    
    def check_type_instance(self, type):
        return self.type is type

    def check_value_type(self, valtype):
        return issubclass(valtype, self.type.value_type)
    
    def instantiate(self, context, args):
        """ 引数を付け足す """
        moreargs = instantiate_args(self, self.instantiate_params(), context, args)
        newargs = []
        # UnspecifiedTypeParamを埋める
        i = 0
        for a in self._args:
            if a is UnspecifiedTypeParam and i < len(moreargs):
                newargs.append(moreargs[i])
                i += 1
            else:
                newargs.append(a)
        newargs.extend(moreargs[i:])

        return TypeInstance(self.type, newargs)

    def instantiate_params(self):
        """ UnspecifiedTypeParamを埋める """
        ps = self.type.instantiate_params()
        params = []
        for i, p in enumerate(ps):
            if i < len(self._args):
                if self._args[i] is UnspecifiedTypeParam:
                    params.append(p)
            else:
                params.append(p)

        if not params:
            if ps and ps[-1].is_variable():
                params.append(ps[-1])
        return params        

    def get_conversion(self):
        n = ""
        n += self.type.typename
        if self._args:
            strs = []
            for a in self._args:
                if isinstance(a, TypeProxy):
                    x = a.get_conversion()
                    if " " in x:
                        x = "({})".format(x)
                else:
                    x = str(a)
                strs.append(x)
            n += ": " + " ".join(strs)
        return n

    def constructor(self, context, value):
        return self.type.constructor(context, value, self._args)

    def stringify_value(self, value):
        return self.type.stringify_value(value, self._args)
    
    def summarize_value(self, value):
        return self.type.summarize_value(value, self._args)

    def pprint_value(self, spirit, value):
        return self.type.pprint_value(spirit, value, self._args)
    
    def reflux_value(self, value):
        return self.type.reflux_value(value, self._args)

    def get_args(self):
        return self._args


class PythonType(DefaultProxy):
    """
    Pythonの型
    """
    def __init__(self, type, expression=None, ctorargs=None):
        self.type = type
        self.expr = expression or full_qualified_name(type)
        self.ctorargs = ctorargs or []
    
    @classmethod
    def load_from_name(cls, name, ctorargs=None):
        from machaon.core.importer import attribute_loader
        loader = attribute_loader(name)
        t = loader()
        if not isinstance(t, type):
            raise TypeError("'{}'はtypeのインスタンスではありません".format(name))
        return cls(t, name, ctorargs)

    def get_typename(self):
        return self.expr.rpartition(".")[2] # 最下位のシンボルのみ

    def get_conversion(self):
        return self.expr
    
    def get_value_type(self):
        return self.type
    
    def get_describer(self, _mixin):
        return self.type
    
    def get_document(self):
        doc = getattr(self.type, "__doc__", None)
        return doc if doc else ""
    
    def check_type_instance(self, type):
        return isinstance(type, PythonType) and type.type is self.type
    
    def check_value_type(self, valtype):
        return issubclass(valtype, self.type)

    def instantiate(self, context, args):
        """ 引数を付け足す """
        moreargs = instantiate_args(self, self.instantiate_params(), context, args)
        return PythonType(self.type, self.expr, self._ctorargs + moreargs)

    def instantiate_params(self):
        """ 引数の制限なし """
        from machaon.core.method import MethodParameter
        p = MethodParameter("params", "Any")
        p.set_variable()
        return [p]

    def select_method(self, name):
        from machaon.core.method import select_method_from_type_and_instance
        meth = select_method_from_type_and_instance(self.type, self.type, name)
        return meth

    def is_selectable_method(self, name):
        from machaon.core.method import is_method_selectable_from_type_and_instance
        return is_method_selectable_from_type_and_instance(self.type, self.type, name)

    def enum_methods(self):
        from machaon.core.method import enum_methods_from_type_and_instance
        for name, meth in enum_methods_from_type_and_instance(self.type, self.type):
            yield [name], meth 

    def is_selectable_instance_method(self):
        return True 
    
    def constructor(self, _context, value):
        return self.type(value, *self.ctorargs)

    def stringify_value(self, value):
        tn = disp_qualified_name(type(value))
        if type(value).__repr__ is object.__repr__:
            return "<{} id={:0X}>".format(tn, id(value))
        else:
            return "{}({})".format(value, tn)
    
    def summarize_value(self, value):
        if type(value).__str__ is object.__str__:
            return "<{} object>".format(disp_qualified_name(type(value)))
        else:
            return str(value)

    def pprint_value(self, app, value):
        app.post("message", self.summarize_value(value))

    def reflux_value(self, value):
        raise ValueError("reflux実装はPythonTypeでは提供されません")


class TypeAny(DefaultProxy):
    """
    全ての型を受け入れる
    """
    def get_typename(self):
        return "Any"

    def get_conversion(self):
        return "Any"
    
    def get_document(self):
        return "Any type"
    
    def check_type_instance(self, _type):
        return True
    
    def check_value_type(self, valtype):
        return True

    def instantiate(self, context, args):
        raise TypeAnyInstantiateError()

    def instantiate_params(self):
        raise TypeAnyInstantiateError()

    def get_methods_bound_type(self):
        raise TypeAnyInstantiateError()

    def constructor(self, context, value):
        raise TypeAnyInstantiateError()

    def stringify_value(self, value):
        raise TypeAnyInstantiateError()
    
    def summarize_value(self, value):
        raise TypeAnyInstantiateError()

    def pprint_value(self, app, value):
        raise TypeAnyInstantiateError()

    def reflux_value(self, value):
        raise TypeAnyInstantiateError()
    

class TypeAnyInstantiateError(Exception):
    def __str__(self) -> str:
        return "Any type cannot be instantiated"


class TypeUnion(DefaultProxy):
    """
    共和型
    """
    def __init__(self, types):
        self.types = types
    
    def get_typename(self):
        return "Union"
    
    def get_conversion(self):
        return "|".join([x.get_typename() for x in self.types])
    
    def get_document(self):
        return "Union type of {}".format(", ".join(["'{}'".format(x.get_typename()) for x in self.types]))
    
    def check_type_instance(self, type):
        return any(x is type for x in self.types)
    
    def check_value_type(self, valtype):
        for t in self.types:
            if t.check_value_type(valtype):
                return True
        return False

    def select_value_type(self, valtype, *, fallback=False):
        for t in self.types:
            if t.check_value_type(valtype):
                return t
        if fallback:
            return None
        raise TypeError(valtype)

    def instantiate(self, context, args):
        """ 型引数を追加する """
        moretypes = instantiate_args(self, self.instantiate_params(), context, args)
        return TypeUnion(self.types + moretypes)

    def instantiate_params(self):
        """ 可変長の型引数を取れる """
        from machaon.core.method import MethodParameter
        p = MethodParameter("params", "Type")
        p.set_variable()
        return [p]
    
    def constructor(self, context, value):
        firsttype = self.types[0]
        return firsttype.constructor(context, value)

    def stringify_value(self, value):
        t = self.select_value_type(type(value))
        return t.stringify_value(value)
    
    def summarize_value(self, value):
        t = self.select_value_type(type(value))
        return t.summarize_value(value)

    def pprint_value(self, app, value):
        t = self.select_value_type(type(value))
        return t.pprint_value(app, value)

    def reflux_value(self, value):
        t = self.select_value_type(type(value))
        return t.reflux_value(value)
        
        
class SubType(RedirectProxy):
    """
    サブタイプ型
    """
    def __init__(self, basetype, meta):
        super().__init__()
        self.basetype = basetype
        self.meta = meta

    def redirect(self):
        return self.basetype

    def get_typename(self):
        return self.meta.get_typename()

    def get_typedef(self):
        return self.meta.get_typedef()
        
    def get_conversion(self):
        convs = [x.get_conversion() for x in (self.basetype, self.meta)]
        return "{}:{}".format(convs[0], convs[1])
    
    def instantiate(self, context, args):
        """ 転送する """
        newmeta = self.meta.instantiate(context, args)
        return SubType(self.basetype, newmeta)

    def instantiate_params(self):
        """ 転送する """
        return self.meta.instantiate_params()
    
    def construct(self, context, value):
        """ オブジェクトを構築して値を返す """
        # 値型と同一でもコンストラクタを呼び出す
        if self.get_value_type() is not str and self.check_value_type(type(value)):
            return value 
        ret = self.constructor(context, value)
        if not self.check_value_type(type(ret)):
            raise ConstructorReturnTypeError(self, type(ret))
        return ret

    def constructor(self, context, value):
        return self.meta.constructor(context, value)

    def stringify_value(self, value):
        return self.meta.stringify_value(value)
    
    def summarize_value(self, value):
        return self.meta.summarize_value(value)

    def pprint_value(self, app, value):
        return self.meta.pprint_value(app, value)

    def reflux_value(self, value):
        return self.meta.reflux_value(value)
    
#
def make_conversion_from_value_type(value_type):
    n = full_qualified_name(value_type)
    if SIGIL_PYMODULE_DOT not in n:
        if PythonBuiltinTypenames.literals:
            return n.capitalize()
        elif PythonBuiltinTypenames.dictionaries:
            return "ObjectCollection"
        elif PythonBuiltinTypenames.iterables:
            return "Tuple"
        elif n not in __builtins__:
            raise ValueError("'{}'の型名を作成できません".format(n))
        n = "builtins.{}".format(n)
    return n


#
# エラー
#
class ConstructorReturnTypeError(Exception):
    """ コンストラクタの返り値を検証する """
    def __str__(self):
        t, vt = self.args
        return "'{}.constructor'の返り値型'{}'は値型'{}'と互換性がありません".format(
            t.get_conversion(), 
            full_qualified_name(vt),
            full_qualified_name(t.get_value_type())
        )

class TypeConversionError(Exception):
    """ 引数での型チェックの失敗 """
    def __init__(self, srctype, desttype):
        if not isinstance(srctype, type) or not isinstance(desttype, str):
            raise TypeError("TypeConversionError requires args (type, str), but: ({}, {})".format(srctype, desttype))
        super().__init__(srctype, desttype)

    def __str__(self):
        srctype, desttype = self.args
        return "'{}'型の引数に'{}'型の値を代入できません".format(desttype, full_qualified_name(srctype))


# 型引数のデフォルト値
UnspecifiedTypeParam = TypeAny()

#
# 型宣言
# Typename[Typeparam1, param2...](ctorparam1, param2...)
#
class TypeDecl:
    def __init__(self, typename=None, declargs=None, ctorargs=None):
        self.typename = typename
        self.declargs = declargs or []
        self.ctorargs = ctorargs or []
    
    def __str__(self):
        return self.to_string()
    
    def to_string(self):
        """ 型宣言を復元する 
        Returns:
            Str:
        """
        if self.typename is None:
            return "Any"
        elif isinstance(self.typename, TypeProxy):
            return self.typename.get_conversion()

        elems = ""
        elems += self.typename
        if self.declargs:
            elems += "["
            elems += ",".join([x.to_string() for x in self.declargs])
            elems += "]"
        elif self.ctorargs:
            elems += "[]"
        if self.ctorargs:
            elems += "("
            elems += ",".join([x for x in self.ctorargs])
            elems += ")"
        return elems

    def instantiate_type(self, typedef, context, args=None) -> TypeProxy:
        """ Typeから型のインスタンスを作る """
        def collect_args(params, typeargs, valueargs, moreargs):
            i, j, k = 0, 0, 0
            for tp in params:
                if tp.is_type():
                    if i < len(typeargs):
                        yield typeargs[i].instance(context)
                        i += 1
                    elif k < len(moreargs):
                        yield moreargs[k]
                        k += 1
                    elif tp.is_required():
                        raise ValueError("必須の型引数'{}'が指定されていません".format(tp.name))
                    else:
                        from machaon.core.method import MethodParameterDefault
                        yield MethodParameterDefault
                elif tp.is_variable():
                    yield from valueargs[j:]
                    j += len(valueargs)-j
                else:
                    if j < len(valueargs):
                        yield valueargs[j]
                        j += 1
                    elif k < len(moreargs):
                        yield moreargs[k]
                        k += 1

            # 残り
            yield from moreargs[k:]
                
        
        params = typedef.get_type_params()
        if args:
            # Sheet | Int c1 c2
            if self.declargs:
                # デフォルト型変数を埋めていく
                argvals = list(collect_args(params, self.declargs, self.ctorargs, args))  
            else:
                argvals = [*self.ctorargs, *args] # 非型引数を結合 
        else:
            argvals = list(collect_args(params, self.declargs, self.ctorargs, []))
        
        if argvals:
            args = instantiate_args(self, params, context, argvals)
            if args:
                return TypeInstance(typedef, args)
        
        return typedef # 引数がなければそのまま
    
    def instance(self, context, args=None) -> TypeProxy:
        """
        値を構築する
        """
        if self.typename is None:
            # Any型を指す
            return TypeAny()
        elif isinstance(self.typename, TypeProxy):
            return self.typename
        elif self.typename == "Any":
            # 型制約
            return TypeAny()
        elif self.typename == "Union":
            # 型制約
            typeargs = [x.instance(context) for x in self.declargs]
            return TypeUnion(typeargs)
        elif self.typename == "$Sub":
            # サブタイプを解決する
            if len(self.declargs) < 2:
                raise ValueError("not enough type args for $Sub")
            baset = self.declargs[0].instance(context) # 基底型
            subtypes = []
            metadecl = self.declargs[1]
            td = context.get_subtype(baset.typename, metadecl.typename)
            meta = metadecl.instantiate_type(td, context, args)
            return SubType(baset, meta)
        elif SIGIL_PYMODULE_DOT in self.typename: 
            # machaonで未定義のPythonの型: ビルトイン型はbuiltins.***でアクセス
            ctorargs = [*self.ctorargs, *(args or [])]
            return PythonType.load_from_name(self.typename, ctorargs)
        else:
            # 型名を置換する
            typename = type_anon_redirection.get(self.typename.lower(), self.typename)
            # 型オブジェクトを取得
            td = context.select_type(typename)
            if td is None:
                raise BadTypename(typename)
            return self.instantiate_type(td, context, args)


class TypeInstanceDecl(TypeDecl):
    """ 型インスタンスを保持し、TypeDeclと同じ振る舞いをする """
    def __init__(self, inst):
        super().__init__()
        self.inst = inst

    def to_string(self):
        return self.inst.get_conversion()

    def instance(self, context, args=None) -> TypeProxy:
        if args is None or not args:
            return self.inst
        else:
            return self.inst.instantiate(context, args)
    
    def instance_constructor_params(self):
        """ 再束縛する引数の型情報を提供する """
        return self.inst.instantiate_params()
    

class TypeDeclError(Exception):
    def __init__(self, itr, err) -> None:
        super().__init__(itr, err)
    
    def __str__(self):
        itr = self.args[0]
        pos = itr.current_preview()
        return "型宣言の構文エラー（{}）: {}".format(self.args[1], pos)


def parse_type_declaration(decl):
    """ 型宣言をパースする
    Params:
        decl(str):
    Returns:
        TypeDecl:
    """
    if isinstance(decl, TypeProxy):
        return TypeInstanceDecl(decl)
    if not decl:
        raise BadTypename("<emtpy string>")    
    return _parse_typedecl(decl)

#
# 型宣言パーサコンビネータ 
# <body> ::= <subtype> | <subtype> "|" <subtype>
# <subtype> ::= <expr> | <expr> ":" <expr>
# <expr> ::= <type100> | <type110> | <type111> | <type101> | <type100a>
# <type100> ::= <name>
# <type110> ::= <name> "[" <typeargs> "]"
# <type111> ::= <name> "[" <typeargs> "]" "(" <ctorargs> ")"
# <type101> ::= <name> "[]"  "(" <ctorargs> ")"
# <type100a> ::= <name> "[]"
# <typeargs> ::= <body> | <body> "," <typeargs>
# <ctorargs> ::= <ctorvalue> | <ctorvalue> "," <ctorargs>
# <name> ::= ([a-z] | [A-Z] | [0-9] | '_' | '/' | '.')+
# <ctorvalue> ::= [^,\[\]\(\)\|]+  
#
def _parse_typedecl(decl):
    """ 開始地点 """
    itr = _typedecl_Iterator(decl)
    decl = _typedecl_body(itr)
    if not itr.eos():
        itr.advance()
        raise TypeDeclError(itr, "以降を解釈できません")
    return decl

def _typedecl_body(itr):
    union = []
    while not itr.eos():
        expr = _typedecl_subtype(itr)
        union.append(expr)
        ch, pos = itr.advance()
        if itr.eos():
            break
        elif ch == "|":
            continue
        else:
            itr.back(pos)
            break
    if len(union)==1:
        return union[0]
    elif not union:
        raise TypeDeclError(itr, "型がありません")
    else:
        return TypeDecl("Union", union)

def _typedecl_subtype(itr):
    # サブタイプの記述
    types = []
    while not itr.eos():
        expr = _typedecl_expr(itr)
        types.append(expr) 
        ch, pos = itr.advance()
        if itr.eos():
            break
        elif ch == SIGIL_SUBTYPE_SEPARATOR:
            if len(types) > 1:
                raise TypeDeclError(itr, "サブタイプは1つしか指定できません")
            continue
        else:
            itr.back(pos)
            break
    if len(types)==1:
        return types[0]
    elif not types:
        raise TypeDeclError(itr, "型がありません")
    else:
        return TypeDecl("$Sub", types)

def _typedecl_expr(itr):
    # 型名
    name = _typedecl_name(itr)
    if not name:
        raise TypeDeclError(itr, "型名がありません")

    typeargs = []
    ctorargs = []
    while True:
        # 型引数
        ch, pos = itr.advance()
        if itr.eos():
            break
        elif ch == "[":
            ch2, pos2 = itr.advance()
            if ch2 == "]":
                typeargs = [] # 空かっこを許容
            else:
                itr.back(pos2)
                typeargs = _typedecl_typeargs(itr)
        else:
            itr.back(pos)
            break

        # コンストラクタ引数
        ch, pos = itr.advance()
        if itr.eos():
            break
        elif ch == "(":
            ctorargs = _typedecl_ctorargs(itr)
        else:
            itr.back(pos)

        break
    
    return TypeDecl(name, typeargs, ctorargs)

def _typedecl_typeargs(itr):
    args = []
    while True:
        expr = _typedecl_body(itr)
        args.append(expr)
        ch, pos = itr.advance()
        if ch == ",":
            continue
        elif ch == "]":
            break
        elif itr.eos():
            raise TypeDeclError(itr, "型引数リストで予期せぬ終わりに到達")
        else:
            raise TypeDeclError(itr, "予期せぬ文字です")
    return args

def _typedecl_ctorargs(itr):
    args = []
    while True:
        value = _typedecl_ctorvalue(itr)
        args.append(value)
        ch, pos = itr.advance()
        if ch == ",":
            continue
        elif ch == ")":
            break
        elif itr.eos():
            raise TypeDeclError(itr, "コンストラクタ引数リストで予期せぬ終わりに到達")
        else:
            raise TypeDeclError(itr, "予期せぬ文字です")
    return args

def is_typename_char(ch):
    return ch.isidentifier()

digits = "0123456789"
def is_typename_continue_char(ch):
    return is_typename_char(ch) or ch == SIGIL_SCOPE_RESOLUTION or ch == SIGIL_PYMODULE_DOT or ch in digits

def _typedecl_name(itr):
    # Pythonの識別名で使える文字 + SIGIL_SCOPE_RESOLUTION + SIGIL_PYMODULE_DOT
    name = ""
    while not itr.eos():
        ch, pos = itr.advance()
        if ch and len(name) == 0 and is_typename_char(ch):
            name += ch
        elif ch and len(name) > 0 and is_typename_continue_char(ch):
            name += ch
        else:
            itr.back(pos)
            break
    return name

def _typedecl_ctorvalue(itr):
    # 構文用の文字以外は全て受け入れる
    name = ""
    while not itr.eos():
        ch, pos = itr.advance()
        if ch is None or ch in ("),"): 
            itr.back(pos)
            break
        else:
            name += ch
    return name

class _typedecl_Iterator():
    def __init__(self, s):
        self._s = s
        self._i = -1
    
    def eos(self):
        return self._i is None

    def advance(self):
        # Returns: Tuple[char, lastposition]
        if self.eos(): return None, None # eos
        li = self._i
        while True:
            self._i += 1
            if self._i >= len(self._s):
                self._i = None # reach eos
                return None, li
            ch = self._s[self._i]
            if not ch.isspace(): # 空白は読み捨てる
                return ch, li
    
    def back(self, pos):
        if self.eos(): return # eos
        self._i = pos
    
    def current_preview(self):
        if self.eos(): return self._s + "<<<"
        return self._s[0:self._i] + " >>>" + self._s[self._i] + "<<< " + self._s[self._i+1:]


# Python標準の型注釈に対応
type_anon_redirection = {
    "list" : "Tuple",
    "sequence" : "Tuple",
    "set" : "Tuple",
    "mapping" : "ObjectCollection",
    "dict" : "ObjectCollection",
}

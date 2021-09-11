from machaon.core.symbol import (
    SIGIL_SCOPE_RESOLUTION, SIGIL_PYMODULE_DOT, BadTypename, full_qualified_name,
    PythonBuiltinTypenames
)

METHODS_BOUND_TYPE_TRAIT_INSTANCE = 1
METHODS_BOUND_TYPE_INSTANCE = 2

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

    # メソッド関連
    def select_invocation(self, name):
        """ メソッド呼び出しを返す
        Returns:
            Optional[BasicInvocation]:
        """
        raise NotImplementedError()

    def select_method(self, name):
        """ メソッドを名前で検索する
        Returns:
            Optional[Method]:
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
            raise TypeError("'{}.constructor'の返り値型'{}'は値型'{}'と互換性がありません".format(
                self.get_conversion(), 
                full_qualified_name(type(ret)),
                full_qualified_name(self.get_value_type())
            ))
        return ret

    def construct_obj(self, context, value):
        """ Objectのインスタンスを返す """
        convval = self.construct(context, value)
        return self.new_object(convval)
    
    def new_object(self, value):
        """ この型のオブジェクトを作る。型変換は行わない """
        from machaon.core.object import Object
        if isinstance(value, Object):
            if value.type.check_type_instance(self):
                raise ValueError("'{}' -> '{}' 違う型のオブジェクトです".format(value.get_typename(), self.typename))
            return value
        else:
            if not self.check_value_type(type(value)):
                raise ValueError("'{}' -> '{}' 値の型に互換性がありません".format(type(value).__name__, self.typename))
            return Object(self, value)
    
    def stringify_value(self, value):
        raise NotImplementedError()
    
    def summarize_value(self, value):
        raise NotImplementedError()

    def pprint_value(self, app, value):
        raise NotImplementedError()
    
    # 基本型の判定
    def is_any_type(self):
        raise NotImplementedError()

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
    def get_value_type(self):
        return self.get_typedef().get_value_type()
    
    def get_typename(self):
        return self.get_typedef().get_typename()

    def get_conversion(self):
        return self.get_typedef().get_conversion()

    def get_describer(self, mixin):
        return self.get_typedef().get_describer(mixin)

    def get_document(self):
        return self.get_typedef().get_document()
    
    def select_invocation(self, name):
        return self.get_typedef().select_invocation(name)

    def select_method(self, name):
        return self.get_typedef().select_method(name)

    def enum_methods(self):
        return self.get_typedef().enum_methods()
    
    def get_methods_bound_type(self):
        return self.get_typedef().get_methods_bound_type()

    def is_selectable_instance_method(self):
        return self.get_typedef().is_selectable_instance_method()

    def constructor(self, context, value):
        return self.get_typedef().constructor(context, value)

    def stringify_value(self, value):
        return self.get_typedef().stringify_value(value)
    
    def summarize_value(self, value):
        return self.get_typedef().summarize_value(value)

    def pprint_value(self, spirit, value):
        return self.get_typedef().pprint_value(spirit, value)
    
    def is_any_type(self):
        return self.get_typedef().is_any_type()

    def is_none_type(self):
        return self.get_typedef().is_none_type()

    def is_object_collection_type(self):
        return self.get_typedef().is_object_collection_type()
        
    def is_type_type(self):
        return self.get_typedef().is_type_type()

    def is_function_type(self):
        return self.get_typedef().is_function_type()


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

    def is_any_type(self):
        return False

    def is_none_type(self):
        return False

    def is_object_collection_type(self):
        return False
        
    def is_type_type(self):
        return False

    def is_function_type(self):
        return False


class TypeInstance(RedirectProxy):
    """
    引数を含むインスタンス
    """
    def __init__(self, type, typeargs=None, ctorargs=None):
        self.type = type
        self.typeargs = typeargs or [] # TypeInstance
        self.ctorargs = ctorargs or []
    
    def get_typedef(self):
        return self.type
    
    def check_type_instance(self, type):
        return self.type is type

    def check_value_type(self, valtype):
        if self.type.is_any_type():
            return True # 制限なし
        return issubclass(valtype, self.type.value_type)
    
    def get_conversion(self):
        n = ""
        n += self.type.typename
        if self.typeargs:
            n += "["
            n += ", ".join([x.get_conversion() for x in self.typeargs])
            n += "]"
        if self.ctorargs:
            if not self.typeargs:
                n += "[]"
            n += "("
            n += ", ".join(self.ctorargs)
            n += ")"
        return n

    def constructor(self, context, value):
        return self.type.constructor(context, value, self)

    @property
    def type_args(self):
        return self.typeargs
    
    @property
    def constructor_args(self):
        return self.ctorargs
    
    @property
    def args(self):
        return [*self.typeargs, *self.ctorargs]


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

    def select_method(self, name):
        inv = self.select_invocation(name)
        if inv:
            return inv.get_method()
        return None

    def select_invocation(self, name):
        from machaon.core.invocation import FunctionInvocation, select_method_attr
        value = select_method_attr(self.type, name)
        if value:
            return FunctionInvocation(value)
        return None

    def enum_methods(self):
        from machaon.core.message import enum_selectable_attributes
        from machaon.core.invocation import FunctionInvocation, select_method_attr
        for name in enum_selectable_attributes(self.type):
            value = select_method_attr(self.type, name)
            if value:
                inv = FunctionInvocation(value)
                meth = inv.get_method()
                if meth is not None:
                    yield [name], meth 

    def is_selectable_instance_method(self):
        return True 
    
    def constructor(self, _context, value):
        return self.type(value, *self.ctorargs)

    def stringify_value(self, value):
        tn = full_qualified_name(type(value))
        if type(value).__repr__ is object.__repr__:
            return "<{} id={:0X}>".format(tn, id(value))
        else:
            return "{}({})".format(value, tn)
    
    def summarize_value(self, value):
        if type(value).__str__ is object.__str__:
            return "<{} object>".format(full_qualified_name(type(value)))
        else:
            return str(value)

    def pprint_value(self, app, value):
        app.post("message", self.summarize_value(value))
    

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

    def match_value_type(self, valtype):
        for t in self.types:
            if t.check_value_type(valtype):
                return t
        return None
    
    def constructor(self, context, value):
        firsttype = self.types[0]
        return firsttype.constructor(context, value)

    def stringify_value(self, value):
        t = self.match_value_type(type(value))
        if t is None:
            raise TypeError(type(value))
        return t.stringify_value(value)
    
    def summarize_value(self, value):
        t = self.match_value_type(type(value))
        if t is None:
            raise TypeError(type(value))
        return t.summarize_value(value)

    def pprint_value(self, app, value):
        t = self.match_value_type(type(value))
        if t is None:
            raise TypeError(type(value))
        return t.pprint_value(app, value)
    
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
#
#
class TypeConversionError(Exception):
    def __init__(self, srctype, desttype):
        if not isinstance(srctype, type) or not isinstance(desttype, TypeProxy):
            raise TypeError("TypeConversionError(type, TypeProxy)")
        super().__init__(srctype, desttype)

    def __str__(self):
        srctype = self.args[0]
        desttype = self.args[1]
        return "'{}'型の引数に'{}'型の値を代入できません".format(desttype.get_typename(), full_qualified_name(srctype))

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
        return self.display()
    
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
    
    def instance(self, context, args=None):
        """
        値を構築する
        """
        if self.typename is None:
            # Any型を指す
            return context.get_type("Any")
        elif isinstance(self.typename, TypeProxy):
            return self.typename
        elif self.typename == "Union":
            # 型制約
            typeargs = [x.instance(context) for x in self.declargs]
            return TypeUnion(typeargs)
        elif SIGIL_PYMODULE_DOT in self.typename:
            # machaonで未定義のPythonの型
            ctorargs = [*self.ctorargs, *(args or [])]
            return PythonType.load_from_name(self.typename, ctorargs)
        else:
            # 型名を置換する
            typename = type_anon_redirection.get(self.typename.lower(), self.typename)
            # 型オブジェクトを取得
            td = context.select_type(typename)
            if td is None:
                raise BadTypename(typename)
            typeargs = [x.instance(context) for x in self.declargs]
            ctorargs = [*self.ctorargs, *(args or [])]
            if not typeargs and not ctorargs:
                return td
            else:
                return TypeInstance(td, typeargs, ctorargs)


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
    itr = _typedecl_Iterator(decl)
    decl = _typedecl_body(itr)
    if not itr.eos():
        itr.advance()
        raise TypeDeclError(itr, "以降を解釈できません")
    return decl

#
# 型宣言パーサコンビネータ
#
# <body> ::= <expr> | <expr> "|" <body>
# <expr> ::= <type100> | <type110> | <type111> | <type101> | <type100a>
# <type100> ::= <name>
# <type110> ::= <name> "[" <typeargs> "]"
# <type111> ::= <name> "[" <typeargs> "]" "(" <ctorargs> ")"
# <type101> ::= <name> "[]"  "(" <ctorargs> ")"
# <type100a> ::= <name> "[]"
# <typeargs> ::= <body> | <body> "," <typeargs>
# <ctorargs> ::= <value> | <value> "," <ctorargs>
# <name> ::= ([a-z] | [A-Z] | [0-9] | '_' | '/' | '.')+
# <value> ::= [^,\[\]\(\)\|]+  
#
def _typedecl_body(itr):
    union = []
    while not itr.eos():
        expr = _typedecl_expr(itr)
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
        value = _typedecl_value(itr)
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

def _typedecl_name(itr):
    name = ""
    while not itr.eos():
        ch, pos = itr.advance()
        if ch and ch.isidentifier() or ch == SIGIL_SCOPE_RESOLUTION or ch == SIGIL_PYMODULE_DOT:
            name += ch
        else:
            itr.back(pos)
            break
    return name

def _typedecl_value(itr):
    # 構文用の文字以外は全て受け入れる
    name = ""
    while not itr.eos():
        ch, pos = itr.advance()
        if ch is None or ch in ("[]()|,"): 
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

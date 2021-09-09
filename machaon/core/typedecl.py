from machaon.core.symbol import SIGIL_SCOPE_RESOLUTION, SIGIL_PYMODULE_DOT, BadTypename, full_qualified_name

#
# 型パラメータを与えられたインスタンス。
# ・オブジェクトの生成
# ・代入可能性の判定
#
class TypeProxy:
    def get_typedef(self):
        """ 型定義オブジェクトを返す """
        raise NotImplementedError()
    
    def get_typename(self):
        """ 型名を返す """
        raise NotImplementedError()

    def get_conversion(self):
        """ 型宣言を返す """
        raise NotImplementedError()

    def is_any(self):
        """ Any型か """
        raise NotImplementedError()
    
    def check_type_instance(self, type):
        """ 互換性のあるTypeインスタンスか """
        raise NotImplementedError()

    def check_value_type(self, valtype):
        """ 互換性のある値型か """
        raise NotImplementedError()

    def constructor(self, context, value):
        """ オブジェクトを構築する """
        raise NotImplementedError()
    
    def construct(self, context, value):
        if self.check_value_type(type(value)):
            return value # 変換の必要なし
        return self.constructor(context, value)
    
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


class TypeInstance(TypeProxy):
    """
    引数を含むインスタンス
    """
    def __init__(self, type, typeargs=None, ctorargs=None):
        self.type = type
        self.typeargs = typeargs or [] # TypeInstance
        self.ctorargs = ctorargs or []
    
    def get_typedef(self):
        return self.type
    
    def get_typename(self):
        return self.type.get_typename()
    
    def is_any(self):
        return self.type.is_any()

    def check_type_instance(self, type):
        return self.type is type

    def check_value_type(self, valtype):
        if self.type.is_any():
            return True # 制限なし
        return self.type.value_type is valtype
    
    def is_supertype(self, other):
        """ 対象の型の基底タイプであるか 
        if self.is_any():
            return True
        if self is other:
            return True
        return False
        """
    
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

    def stringify_value(self, value):
        return self.type.stringify_value(value)
    
    def summarize_value(self, value):
        return self.type.summarize_value(value)

    def pprint_value(self, value):
        return self.type.pprint_value(value)
    
    @property
    def type_args(self):
        return self.typeargs
    
    @property
    def constructor_args(self):
        return self.ctorargs
    
    @property
    def args(self):
        return [*self.typeargs, *self.ctorargs]


class TypeUnion(TypeProxy):
    """
    共和型
    """
    def __init__(self, types):
        self.types = types
    
    def get_conversion(self):
        return "|".join([x.get_typename() for x in self.types])
    
    def check_type_instance(self, type):
        return any(x is type for x in self.types)
    
    def check_value_type(self, valtype):
        for t in self.types:
            if t.check_value_type(valtype):
                return True
        return False

    def constructor(self, context, value):
        firsttype = self.types[0]
        return firsttype.constructor(context, value)

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
        elif self.typename == "Union":
            # 型制約
            typeargs = [x.instance(context) for x in self.declargs]
            return TypeUnion(typeargs)
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

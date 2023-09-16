from typing import Any, Tuple

from machaon.core.object import Object
from machaon.core.symbol import (
    SIGIL_PYMODULE_DOT,
    BadTypename, full_qualified_name, disp_qualified_name, PythonBuiltinTypenames,
    normalize_typename, QualTypename
)
from machaon.core.type.basic import TypeProxy


class TypeDeclError(Exception):
    """ 構文エラー """
    def __init__(self, itr, err) -> None:
        super().__init__(itr, err)
    
    def __str__(self):
        itr = self.args[0]
        pos = itr.current_preview()
        return "型宣言の構文エラー（{}）: {}".format(self.args[1], pos)


#
# 型宣言
# Typename[Typeparam1, param2...]
#
class TypeDecl:
    def __str__(self):
        return self.to_string()

    def to_string(self):
        raise NotImplementedError()
        
    def instance(self, context, args=None) -> TypeProxy:
        raise NotImplementedError()


class ModuleTypeDecl(TypeDecl):
    """
    モジュールに定義された型を示す宣言
    """
    def __init__(self, typename, args=None, resolver=None):
        if isinstance(typename, str):
            self.typename = normalize_typename(typename)
            self.describername = None
        elif isinstance(typename, QualTypename):
            self.typename = typename.typename
            self.describername = typename.describer
        else:
            raise TypeError("TypeDecl(str|QualTypename): {}".format(typename))
        self.declargs = args or []
        self.resolver = resolver
    
    def with_describer_name(self, name):
        """ 実装名を指示する """
        self.describername = name
        return self
    
    def to_string(self):
        """ 型宣言を復元する 
        Returns:
            Str:
        """
        if isinstance(self.typename, TypeProxy):
            return self.typename.get_conversion()

        elems = ""
        if self.describername is None:
            elems += self.typename
        else:
            elems += QualTypename(self.typename, self.describername).stringify()
        if self.declargs:
            elems += "["
            elems += ",".join([x.to_string() for x in self.declargs])
            elems += "]"
        return elems
    
    def instance(self, context, args=None) -> TypeProxy:
        """
        値を構築する
        """
        if isinstance(self.typename, TypeProxy):
            return self.typename
        
        # 型名を解決する
        if self.resolver is not None:
            tn, dn = self.resolver.resolve(self.typename, self.describername)
        else:
            tn, dn = self.typename, self.describername
        
        # 型オブジェクトを取得
        td: TypeProxy = context.select_type(tn, dn) # モジュールから型を読み込む
        if td is None:
            raise BadTypename("{}({})".format(self.typename, tn))
        
        # 引数を束縛する
        argvals = self.declargs
        if args:
            argvals += list(args)
        targs = td.instantiate_args(context, argvals)
        if targs:
            from machaon.core.type.instance import TypeInstance
            return TypeInstance(td, targs)
        else:
            return td
            
    def resolve(self, context):
        """
        型宣言を解決する
        """
        try:
            ti = self.instance(context)
        except Exception as e:
            from machaon.core.type.instance import UnresolvableType
            ti = UnresolvableType(self.to_string(), e)
        return TypeInstanceDecl(ti) # 型を実体化する


class SpecialTypeDecl(TypeDecl):
    """
    特殊型と一対一で対応する型宣言
    """
    def __init__(self, target, arity):
        self.target = target
        self.arity = arity
    
    def __str__(self):
        return self.to_string()
    
    def to_string(self):
        """ 型宣言を復元する 
        Returns:
            Str:
        """
        return self.target
    
    def instance(self, context, _args=None):
        """ モジュールから定数を取得する """
        return getattr(context.type_module, self.target+"Type")
    
    def resolve(self, _context):
        """ すでに解決済み """
        return self

    def bind(self, args):
        """ 特殊型の宣言に引数を束縛する """
        if self.arity == 0:
            if len(args) > 0:
                raise TypeDeclError("{}は型引数をとりません".format(self.target))
            return self
        elif self.arity == -1:
            return SpecialTypeFunctionDecl(self.target, args)
        else:
            if len(args) != self.arity:
                raise TypeDeclError("{}には{}個の型引数が必要ですが、{}個が渡されました".format(self.target, self.arity, len(args)))
            return SpecialTypeFunctionDecl(self.target, args)


class SpecialTypeFunctionDecl(TypeDecl):
    """
    型引数をもつ特殊型と一対一で対応する型宣言
    """
    def __init__(self, target, args):
        self.target = target
        self.declargs = args

    def to_string(self):
        elems = self.target
        elems += "["
        elems += ",".join([x.to_string() for x in self.declargs])
        elems += "]"
        return "".join(elems)

    def instance(self, context, _args=None):
        """ モジュールから型関数を取得する """
        typefn = getattr(context.type_module, self.target+"Type")
        typeargs = [x.instance(context) for x in self.declargs]
        return typefn(typeargs)

    def resolve(self, context):
        """ 引数を解決する """
        typeargs = [x.resolve(context) for x in self.declargs]
        return SpecialTypeFunctionDecl(self.target, typeargs)


AnyType = SpecialTypeDecl("Any", 0)
ObjectType = SpecialTypeDecl("Object", 0)
UnionType = SpecialTypeDecl("Union", -1)
SpecialTypeDecls = {x.target:x for x in (AnyType, ObjectType, UnionType)}


class PythonTypeDecl(TypeDecl):
    """
    Python型を示す宣言
    """
    def __init__(self, target, args=None):
        if args is not None and len(args) > 0:
            raise TypeDeclError("Python型には型引数を束縛できません")
        self.target = target

    def to_string(self):
        """ """
        return self.target
    
    def instance(self, _context, _args=None):
        from machaon.core.type.pytype import PythonType
        return PythonType.load_from_name(self.target)

    def resolve(self, _context):
        return self # 解決済み

#
#
#
def make_conversion_from_value_type(value_type: type) -> str:
    """ Pythonの型からmachaonの型名を生成する """
    n = full_qualified_name(value_type)
    if SIGIL_PYMODULE_DOT in n:
        return n # PythonTypeとしてそのまま読み込む
    else:
        # ビルトイン型
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

def split_typename_and_value(value: Any) -> Tuple[str, Any]:
    """ 値から、machaonの型名と値を分離する """
    if isinstance(value, Object):
        return value.get_conversion(), value.value
    else:
        return make_conversion_from_value_type(type(value)), value


#
#
#
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

    def resolve(self, _context):
        return self

    

#
# 型宣言のパーサ
#
def parse_type_declaration(decl, resolver=None):
    """ 型宣言をパースする
    Params:
        decl(str):
        resolver():
    Returns:
        TypeDecl|TypeInstanceDecl:
    """
    if isinstance(decl, TypeProxy):
        return TypeInstanceDecl(decl)
    elif isinstance(decl, str):
        if not decl:
            raise BadTypename("<emtpy string>")        
        from machaon.core.type.declparser import parse_typedecl
        d = parse_typedecl(decl, resolver)
        return d
    else:
        raise TypeError("parse_type_declaration")
    
def instantiate_type(decl, context, *args, resolver=None):
    """ 型宣言をインスタンス化する
    Params:
        decl(str):
    Returns:
        TypeDecl:
    """
    d = parse_type_declaration(decl, resolver)
    return d.instance(context, args)

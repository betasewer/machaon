from typing import Any, Tuple

from machaon.core.object import Object
from machaon.core.symbol import (
    SIGIL_PYMODULE_DOT,
    BadTypename, full_qualified_name, disp_qualified_name, PythonBuiltinTypenames,
    QualTypename
)
from machaon.core.type.basic import TypeProxy, instantiate_args

#
# 型宣言
# Typename[Typeparam1, param2...](ctorparam1, param2...)
#
class TypeDecl:
    def __init__(self, typename=None, declargs=None, ctorargs=None):
        self.typename = typename
        self.declargs = declargs or []
        self.ctorargs = ctorargs or []
        self.describername = None
    
    def __str__(self):
        return self.to_string()

    def with_describer_name(self, name):
        """ 実装名を指示する """
        self.describername = name
        return self
    
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
        elems += QualTypename(self.typename, self.describername).stringify()
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

    def instantiate_args(self, parameters, context, args=None) -> TypeProxy:
        """ Typeから型に渡す引数の並びを作る """
        def collect_args(params, typeargs, valueargs, moreargs):
            i, j, k = 0, 0, 0
            for tp in params:
                if tp.is_type():
                    if tp.is_variable():
                        for x in range(i,len(typeargs)):
                            yield typeargs[x].instance(context)
                        i = len(typeargs)
                    elif i < len(typeargs):
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
                else:
                    if tp.is_variable():
                        yield from valueargs[j:]
                        j = len(valueargs)
                        yield from moreargs[k:]
                        k = len(moreargs)
                    else:
                        if j < len(valueargs):
                            yield valueargs[j]
                            j += 1
                        elif k < len(moreargs):
                            yield moreargs[k]
                            k += 1

            # 残りの処理
            restargs = (*typeargs[i:], *valueargs[j:], *moreargs[k:])
            if restargs:
                line = ",".join(str(x) for x in restargs)
                raise TypeError("{}個の引数に対して、実引数に余りが出ます:{}".format(len(parameters), line))
    
        if args:
            # Sheet | Int c1 c2
            if self.declargs:
                # デフォルト型変数を埋めていく
                argvals = list(collect_args(parameters, self.declargs, self.ctorargs, args))  
            else:
                argvals = [*self.ctorargs, *args] # 非型引数を結合 
        else:
            argvals = list(collect_args(parameters, self.declargs, self.ctorargs, []))
        
        if argvals:
            args = instantiate_args(self, parameters, context, argvals)
            return args
        return ()
    
    def instance(self, context, args=None) -> TypeProxy:
        """
        値を構築する
        """
        if self.typename is None:
            # Any型を指す
            from machaon.core.type.instance import TypeAny
            return TypeAny()
        elif isinstance(self.typename, TypeProxy):
            return self.typename
        elif self.typename == "Any":
            # 型制約
            from machaon.core.type.instance import TypeAny
            return TypeAny()
        elif self.typename == "Union":
            # 型制約
            from machaon.core.type.instance import TypeUnion
            typeargs = [x.instance(context) for x in self.declargs]
            return TypeUnion(typeargs)
        elif self.typename == "$Sub":
            # サブタイプを解決する
            from machaon.core.type.extend import SubType
            from machaon.core.type.instance import TypeInstance
            if len(self.declargs) < 2:
                raise ValueError("not enough type args for $Sub")
            basetype = self.declargs[0].instance(context) # 基底型
            metadecl = self.declargs[1]
            td = context.get_subtype(basetype.get_typename(), metadecl.typename)
            targs = metadecl.instantiate_args(td.get_type_params(), context, args)
            if targs:
                return SubType(basetype, TypeInstance(td, targs))
            else:
                return SubType(basetype, td)
        elif SIGIL_PYMODULE_DOT in self.typename: 
            # machaonで未定義のPythonの型: ビルトイン型はbuiltins.***でアクセス
            from machaon.core.type.pytype import PythonType
            ctorargs = [*self.ctorargs, *(args or [])]
            return PythonType.load_from_name(self.typename, ctorargs)
        else:
            from machaon.core.type.instance import TypeInstance
            # 型名を置換する
            typename = py_anon_redirection.get(self.typename.lower(), self.typename)
            # 型オブジェクトを取得
            td = context.select_type(typename, self.describername) # モジュールから型を読み込む
            if td is None:
                raise BadTypename(typename)
            targs = self.instantiate_args(td.get_type_params(), context, args)
            if targs:
                return TypeInstance(td, targs)
            else:
                return td


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
    
    def instance_constructor_params(self):
        """ 再束縛する引数の型情報を提供する """
        return self.inst.instantiate_params()
    
#
# Python標準の型注釈に対応
#
py_anon_redirection = {
    "list" : "Tuple",
    "sequence" : "Tuple",
    "set" : "Tuple",
    "mapping" : "ObjectCollection",
    "dict" : "ObjectCollection",
}

#
# 型宣言のパーサ
#
def parse_type_declaration(decl, inst_context=None, *inst_args):
    """ 型宣言をパースする
    Params:
        decl(str):
    Returns:
        TypeDecl|TypeInstanceDecl:
    """
    if isinstance(decl, TypeProxy):
        return TypeInstanceDecl(decl)
    if not decl:
        raise BadTypename("<emtpy string>")
    
    from machaon.core.type.declparser import parse_typedecl
    d = parse_typedecl(decl)
    
    if inst_args:
        return TypeInstanceDecl(d.instance(inst_context, inst_args))
    return d
    
def instantiate_type(decl, context, *args):
    """ 型宣言をインスタンス化する
    Params:
        decl(str):
    Returns:
        TypeDecl:
    """
    d = parse_type_declaration(decl)
    return d.instance(context, args)

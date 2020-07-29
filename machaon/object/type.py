import os
import re
from inspect import signature

from typing import Any, Sequence, List, Dict, Union, Callable, ItemsView, Optional

#
#
#
#
#

#
class BadTypename(Exception):
    pass
#
class BadMethodName(Exception):
    pass
#
class BadMethodDelegation(Exception):
    pass

#
#
#
class TypeMethod():
    class PRINTER():
        pass
    class UNDEFINED():
        pass

    def __init__(self, name, arity, return_typecode, help="", target=None):
        self.name: str = name
        self.arity: int = arity
        self.return_typecode: Union[str, TypeMethod.PRINTER] = return_typecode
        self.help: str = help
        self.target: str = normalize_method_target(target or self.name)
    
    def get_name(self):
        return self.name
        
    def get_result_typecode(self):
        return self.return_typecode
    
    def get_help(self):
        return self.help

    def is_printer(self):
        return self.return_typecode is TypeMethod.PRINTER
    
    def resolve(self, this_type):
        return this_type.get_method_delegation(self.target)

#
class TypeMethodAlias:
    def __init__(self, name, dest):
        self.name = name
        self.dest = dest
    
    def get_name(self):
        return self.name
    
    def get_destination(self):
        return self.dest

#
#
#
class TypeTraits():
    __mark = True
    value_type: Callable = str
    class NONAME:
        pass

    def __init__(self, typename=NONAME, description="", flags=0, value_type=None):
        self.typename: str = typename
        self.description: str = description
        self.flags = flags
        self.value_type = value_type
        self._methods: Dict[str, TypeMethod] = {}
        self._methodalias: Dict[str, TypeMethodAlias] = {}
    
    def __str__(self):
        return "<TypeTraits '{}'>".format(self.typename)

    def get_value_type(self):
        if self.value_type is None:
            return str # デフォルトでは文字列型とする
        return self.value_type
    
    def copy(self):
        t = TypeTraits(self.typename, self.description, self.flags)
        t._methods = self._methods.copy()
        t._methodalias = self._methodalias.copy()
        return t

    #
    #
    #
    def convert_from_string(self, arg: str):
        m = self.get_method_delegation("from_string")
        return m(arg)

    def convert_to_string(self, v: Any):
        m = self.get_method_delegation("to_string")
        return m(v)

    def from_string(self, arg: str):
        return self.get_value_type()(arg)

    def to_string(self, v: Any):
        if v is None:
            return ""
        else:
            return str(v)
    
    # 
    # メソッド呼び出し
    #
    def get_method(self, name) -> Optional[TypeMethod]:
        resolved = self.get_method_alias(name)
        if resolved is None:
            resolved = name
        return self._methods.get(resolved, None)

    def enum_methods(self, arity=None):
        for meth in self._methods.values():
            if arity is not None and meth.arity != arity:
                continue
            yield meth
    
    def new_method(self, 
        names, 
        arity, 
        return_type=None, 
        help="", 
        target=None
    ):
        top, *aliass = names
        self._methods[top] = TypeMethod(top, arity, return_type, help, target)
        for a in aliass:
            self.new_method_alias(a, top)
    
    # メソッドの実装を解決する
    def get_method_delegation(self, attrname):
        m = getattr(self, attrname, None)
        if m is None:
            import builtins
            m = getattr(builtins, attrname, None)
            if m is None:
                raise BadMethodDelegation(attrname)
        return m

    #
    # メソッド名のエイリアスを取得する
    #
    def get_method_alias(self, name) -> Optional[str]:
        a = self._methodalias.get(name, None)
        if a:
            return a.get_destination()
        return None

    def enum_method_alias(self):
        for meth in self._methodalias.values():
            yield meth
    
    def new_method_alias(self, name, dest):
        self._methodalias[name] = TypeMethodAlias(name, dest)

    #
    # 型定義構文用のメソッド
    #
    def describe(self, 
        typename = "",
        description = "",
        value_type = None,
    ):
        if typename:
            self.typename = typename
        if description:
            self.description = description
        if value_type:
            self.value_type = value_type
        return self 
    
    def __getitem__(self, declaration):
        if not isinstance(declaration, str):
            raise TypeError("declaration")
        
        head, _, tail = [x.strip() for x in declaration.partition(" ")]
        if not tail:
            tail = head
            head = "member"

        if head == "member":
            names = tail.split()
            def member_(**kwargs):
                self.new_method(names, 1, **kwargs)
                return self
            return member_

        elif head == "operator":
            names = tail.split()
            def opr_(**kwargs):
                self.new_method(names, 2, **kwargs)
                return self
            return opr_

        elif head == "alias":
            origname = tail.strip()
            def alias_(*names):
                self.new_method_alias(origname, names)
                return self
            return alias_

        else:
            raise ValueError("不明な宣言型です：'{}'".format(head))
    
    def make_described(self, describer):
        if not hasattr(describer, "describe_type"):
            raise ValueError("クラスメソッド 'describe_type' が型定義のために必要です")
        describer.describe_type(self) # type: ignore
        setattr(describer, "type_traits_typename", self.typename) # getで使用可能にする
        return self

#
#
class TypeTraitsDelegation(TypeTraits):
    def __init__(self, klass: Any):
        typename = klass.__name__
        super().__init__(typename, typename)
        self.klass = klass
        self._inst = None
        
    def copy(self):
        t = super().copy()
        t.klass = self.klass
        # _inst は自分で生成させる
        return t
    
    def get_value_type(self):
        if self.value_type is None:
            return self.klass
        return self.value_type
    
    def get_method_delegation(self, attrname):
        fn = getattr(self.klass, attrname, None)
        if fn is None:
            # TypeTraitsクラスのデフォルト定義を用いる
            fn = getattr(super(), attrname)
        
        if fn is None:
            raise BadMethodDelegation(attrname)
        return fn

#
def normalize_method_target(name):
    return name.replace("-","_") # ハイフンはアンダースコア扱いにする

#
# 型取得インターフェース
#
class TypeModule():
    def __init__(self):
        self._typelib: Dict[str, TypeTraits] = {}
        self._ancestors: List[TypeModule] = [] 
    
    #
    def normalize_typename(self, name: str) -> str:
        return name.replace("_","-")
        
    #
    def exists(self, typename: str) -> bool:
        return typename in self._typelib
    
    def find(self, typename: str) -> Optional[TypeTraits]:
        # 自分自身の定義を探索
        if typename in self._typelib:
            return self._typelib[typename]
        
        # 親モジュールを探索
        for ancmodule in self._ancestors:
            tt = ancmodule.find(typename)
            if tt is not None:
                return tt

        # 見つからなかった
        return None

    #
    # 型を取得する
    #
    def get(self, typecode: Any = None, fallback = False) -> Optional[TypeTraits]:
        if self._typelib is None:
            raise ValueError("No type library set up")
        if typecode is None:
            t = self.find("str")
        elif isinstance(typecode, str):
            typename = self.normalize_typename(typecode)
            t = self.find(typename)
        elif isinstance(typecode, TypeTraits):
            t = typecode
        else:
            if hasattr(typecode, "type_traits_typename"):
                typename = typecode.type_traits_typename
            else:
                typename = self.normalize_typename(typecode.__name__)
            t = self.find(typename)
        
        if t is None and not fallback:
            raise BadTypename(typecode)
        return t

    # objtypes[<typename>] -> TypeTraits
    def __getitem__(self, typecode) -> Optional[TypeTraits]:
        return self.get(typecode)

    # objtypes.<typename> -> TypeTraits
    def __getattr__(self, name) -> Optional[TypeTraits]:
        typename = self.normalize_typename(name)
        return self.get(typename)

    #
    # 型を定義する
    #
    def define(self, 
        traits: Any = None,
        *,
        typename = None, 
        description = "",
    ) -> TypeTraits:
        # 登録処理
        t: Any = None # 型オブジェクトのインスタンス
        if traits is None:
            # 一時的な型：振る舞いはすべてデフォルト、値の生成は不可
            t = TypeTraits(typename, description)
        elif isinstance(traits, TypeTraits):
            # Traitsまたは派生型のインスタンスが渡された
            t = traits.copy()
        elif isinstance(traits, type):
            if hasattr(traits, "_TypeTraits__mark"):
                # Traitsまたは派生型の型が渡された
                t = traits(traits.__name__)
            else:
                # 実装移譲先のクラス型が渡された
                t = TypeTraitsDelegation(traits)
            # describe_type
            t.make_described(traits)
        else:
            raise TypeError("TypeModule.defineの引数型が間違っています：{}".format(type(traits).__init__))

        if typename is not None:
            t.typename = typename

        if t.typename in self._typelib:
            raise ValueError("型'{}'は既に定義されています".format(t.typename))
        self._typelib[t.typename] = t

        return t
    
    # デコレータ用
    def definition(self, traits):
        return self.define(traits=traits)

    #
    #
    #
    def add_ancestor(self, other): # type: (TypeModule) -> None
        self._ancestors.append(other)




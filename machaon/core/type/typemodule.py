from typing import Dict, Optional, List, Union, Any, Generator

from machaon.core.symbol import (
    BadTypename, normalize_typename, BadMethodName, PythonBuiltinTypenames, 
    full_qualified_name, is_valid_typename,
    get_scoped_typename, parse_scoped_typename
)
from machaon.core.type.decl import TypeProxy
from machaon.core.type.type import Type
from machaon.core.type.typedef import TypeDefinition
from machaon.core.importer import ClassDescriber, attribute_loader


#
# 型定義モジュールのエラー 
#
class TypeModuleError(Exception):
    pass

# 
#
#
CORE_SCOPE = ""

TYPECODE_TYPENAME = 1
TYPECODE_VALUETYPE = 2

SUBTYPE_BASE_ANY = 1


#
# 型取得インターフェース
#
class TypeModule():
    def __init__(self):
        self.scopename = None
        self.parent = None
        self._lib_typename: Dict[str, Type] = {}
        self._lib_describer: Dict[str, str] = {}
        self._lib_valuetype: Dict[str, str] = {}
        self._subtype_rels: Dict[str, Dict[str, Type]] = {}
        self._loading_mixins: Dict[str, List[TypeDefinition]] = {}
        #
        self._children: Dict[str, TypeModule] = {} 

    #
    @property
    def root(self):
        if self.parent is None:
            return self
        else:
            return self.parent

    def count(self):
        """ このモジュールにある型定義の数を返す
        Returns:
            Int:
        """
        return len(self._lib_typename)
    
    #
    def _load_type(self, t: Union[Type, TypeDefinition]) -> Type:
        """ 型定義をロードする """
        if isinstance(t, TypeDefinition):
            ti = t.load_type()
        else:
            ti = t
        return ti
    
    def _select(self, value:str, code:int, *, noload=False) -> Optional[Type]:
        """ このライブラリから型定義を取り出す """
        libt = None
        if code == TYPECODE_TYPENAME:
            libt = self._lib_typename.get(value)
        elif code == TYPECODE_VALUETYPE:
            tn = self._lib_valuetype.get(value)
            if tn is not None:
                libt = self._lib_typename[tn]
        if libt is None:
            return None
        if noload:
            return libt
        else:
            return self._load_type(libt)

    def _select_scoped(self, scopename, typename):
        """ スコープから型を検索する """
        scope = self.get_scope(scopename)
        if scope is not None:
            target = scope._select(typename, TYPECODE_TYPENAME, noload=True)
            if target is not None:
                return target
        return None


    #
    # 型を取得する
    #
    def find(self, typename: str, *, code=TYPECODE_TYPENAME, scope=None) -> Optional[Type]:
        """ 定義を探索する 
        Params:
            typename(str): 型名
            code?(int): 検索対象
            scope?(str): スコープ名
        Returns:
            Optional[Type]:
        """
        t = None
        if scope is None:
            # 自分自身を探索する
            t = self._select(typename, code)
            if t is not None:
                return t

            # すべての子モジュールを探索
            for ch in self._children.values():
                t = ch.find(typename, code=code)
                if t is not None:
                    return t
        else:
            # 特定のモジュールを探索
            mod = self.get_scope(scope)
            if mod is None:
                raise TypeModuleError("スコープ'{}'は子モジュールのなかに見つかりません".format(scope))
            return mod._select(typename, code)
    
    def get(self, typecode: Any, *, scope=None) -> Optional[TypeProxy]:
        """ 色々なデータから定義を探索する 
        Params:
            typecode(Any): str=型名 | Type=型定義そのもの | <class>=型の値型
            scope?(str): スコープ名
        Returns:
            Optional[Type]:
        """
        if isinstance(typecode, TypeProxy):
            return typecode

        t = None
        if isinstance(typecode, str):
            typename = normalize_typename(typecode)
            t = self.find(typename, scope=scope)
        elif isinstance(typecode, Type):
            t = typecode
        elif hasattr(typecode, "Type_typename"):
            tn = typecode.Type_typename
            typename, thisscope = parse_scoped_typename(tn)
            t = self.find(typename, scope=thisscope)
        elif isinstance(typecode, type):
            t = self.find(full_qualified_name(t), code=TYPECODE_VALUETYPE, scope=scope)
        else:
            raise TypeError("未対応のtypecodeです: {}".format(typecode))

        if t is None:
            return None

        return t

    def _enum_types(self, lib, geterror):
        for name, t in lib.items():
            if geterror:
                try:
                    yield name, self._load_type(t), None
                except Exception as e:
                    from machaon.types.stacktrace import ErrorObject
                    yield name, None, ErrorObject(e)
            else:
                yield name, self._load_type(t)

    def enum(self, *, geterror=False) -> Generator[Type, None, None]:
        """ すべての型をロードし、取得する
        Params:
            geterror(bool): 発生したエラーを取得する
        """
        yield from self._enum_types(self._lib_typename, geterror)
        
        for chi in self._children.values():
            yield from chi.enum(geterror=geterror)

    def deduce(self, value_type) -> Optional[TypeProxy]:
        """ 値型に適合する型を取得する
        Params:
            value_type(type):
        Returns:
            Optional[TypeProxy]: 
        """
        if not isinstance(value_type, type):
            raise TypeError("value_type must be type instance, not value")

        # ビルトイン型に対応する
        if hasattr(value_type, "__name__"): 
            typename = value_type.__name__
            if typename in PythonBuiltinTypenames.literals: # 基本型
                return self.get(typename.capitalize())
            elif typename in PythonBuiltinTypenames.dictionaries: # 辞書型
                return self.get("ObjectCollection")
            elif typename in PythonBuiltinTypenames.iterables: # イテラブル型
                return self.get("Tuple")
        
        # 値型で検索する
        t = self.find(full_qualified_name(value_type), code=TYPECODE_VALUETYPE)
        if t is not None:
            return t

        # 見つからなかった
        return None

    #
    # サブタイプを取得する
    #
    def _select_subtype(self, basekey, typename):
        """ このモジュールで型名とサブタイプ名の関係を解決する 
        Params:
            basekey(str): 元の型名
            typename(str): サブタイプ名
        Returns:
            Optional[TypeProxy]
        """
        bag = self._subtype_rels.get(basekey)
        if bag is not None:
            td = self._subtype_rels[basekey].get(typename)
            if td is not None:
                return self._load_type(td)
        return None
        
    def find_subtype(self, basekey, typename, scope=None):
        """ findと同様にサブタイプを探索する
        Params:
            basekey(str): 元の型名
            typename(str): サブタイプ名
            scope?(str): スコープ名
        Returns:
            Optional[TypeProxy]
        """
        if scope is None:
            # 自分自身の定義を探索
            t = self._select_subtype(basekey, typename)
            if t is not None:
                return t

            # 子モジュールをすべて探索
            for ch in self._children.values():
                tt = ch.find_subtype(basekey, typename)
                if tt is not None:
                    return tt
        else:
            # 特定のモジュールを探索
            if scope not in self._children:
                raise TypeModuleError("スコープ'{}'は子モジュールのなかに見つかりません".format(scope))
            mod = self._children[scope]
            return mod._select_subtype(basekey, typename)
    
    def get_subtype(self, basetypecode: Any, typename: str, *, scope=None):
        """ サブタイプを探索する
        Params:
            basetypecode(Any): getで使用できるすべての値
            typename(str): サブタイプ名
            scope?(str): スコープ名
        Returns:
            Optional[TypeProxy]
        """
        basetype = self.get(basetypecode, scope=scope)
        if basetype is None:
            return None
        
        subtype = self.find_subtype(basetype.get_typename(), typename, scope=scope)
        if subtype is None:
            # 総称型のものを探す
            if basetypecode == SUBTYPE_BASE_ANY: 
                return None
            subtype = self.find_subtype(SUBTYPE_BASE_ANY, typename, scope=scope)

        return subtype

    def enum_subtypes_of(self, basetypecode, *, scope=None, geterror=False):
        """ ある型のすべてのサブタイプをロードし、取得する
        Params:
            geterror(bool): 発生したエラーを取得する
        Yields:
            Tuple[Str, Str, Type, Error]: scopename, typename, type, error
        """
        basetype = self.get(basetypecode, scope=scope)
        if basetype is None:
            return None
        basekey = basetype.get_typename()

        # 子モジュールを全て探索する
        def _enum(mod):
            types = mod._subtype_rels.get(basekey, {})
            for name, t, err in self._enum_types(types, geterror):
                yield (mod.scopename, "{}:{}".format(basekey,name), t, err)
                
            for ch in mod._children.values():
                yield from _enum(ch)
        
        yield from _enum(self)

    def enum_all_subtypes(self, *, geterror=False):
        """ 全てのサブタイプを取得する。 
        Yields:
            Tuple[Str, Str, Type, Error]: scopename, typename, type, error
        """
        def _enum(mod):
            for base, types in mod._subtype_rels.items():
                for name, t, err in self._enum_types(types, geterror):
                    yield (mod.scopename, "{}:{}".format(base,name), t, err)
                
            for ch in mod._children.values():
                yield from _enum(ch)

        yield from _enum(self)



    #
    # 型を定義する
    #
    def define(self, 
        describer: Any = None,
        *,
        typename = None, 
        value_type = None,
        doc = "",
        bits = 0
    ) -> Type:
        # 登録処理
        t: Any = None # 型オブジェクトのインスタンス
        if describer is None:
            # 実質文字列型
            t = Type({"ValueType":str})
        elif isinstance(describer, TypeDefinition):
            t = describer
        elif isinstance(describer, Type):
            # Traitsまたは派生型のインスタンスが渡された
            t = describer.copy() # 複製する
        elif isinstance(describer, dict):
            # 実装を記述した辞書型
            t = Type(describer)
        elif isinstance(describer, ClassDescriber) or isinstance(describer, type):
            if not isinstance(describer, ClassDescriber):
                describer = ClassDescriber(describer)
            td = TypeDefinition(describer)
            t = Type(describer, name=td.proto_define())
        else:
            raise TypeModuleError("TypeModule.defineは'{}'による型定義に対応していません：".format(type(describer).__name__))
        
        if isinstance(t, Type):
            # 定義をロードする
            t.describe(
                typename=typename, value_type=value_type, 
                doc=doc, bits=bits
            ).load()
            key = t.get_typename()
            if key is None:
                raise TypeModuleError("No typename is set: {}".format(describer))

            self._add_type(key, t)
        elif isinstance(t, TypeDefinition):
            if t.is_mixin():
                # mixinを登録するか読み込む
                basename, basescope = parse_scoped_typename(t.get_sub_target())
                self._load_mixin(basename, basescope, t, reserve=True)
            else:
                # 定義を型名に紐づけて配置する
                typename = t.proto_define()
                if t.is_subtype():
                    basename, basescope = parse_scoped_typename(t.get_sub_target())
                    self._add_subtype(basename, typename, t)
                else:
                    self._add_type(typename, t)
        else:
            raise TypeModuleError("Unknown result value of TypeModule.define: {}".format(t))

        return t

    def _add_type(self, typename, type):
        """ 型をモジュールに追加する """
        describername = type.get_describer_qualname()
        valuetypename = type.get_value_type_qualname()

        # 型名の辞書をチェックする
        if typename in self._lib_typename:
            dest = self._lib_typename[typename]
            if dest.get_describer_qualname() == describername:
                return dest # 同じものが登録済み
            else:
                o = dest.get_describer_qualname()
                n = describername
                raise TypeModuleError("型'{}'はこのモジュールに既に存在します\n  旧= {}\n  新= {}".format(typename, o, n))
        
        # デスクライバクラスをチェックする
        if describername is not None:
            if describername in self._lib_describer:
                return # 登録済み

        self._lib_typename[typename] = type
        self._lib_describer[describername] = typename

        # 値型は最初に登録されたものを優先する
        if valuetypename not in self._lib_valuetype:
            self._lib_valuetype[valuetypename] = typename

        # スコープモジュールを登録する
        type.scope = self

        # 予約済みのmixinロードを実行する
        self._load_reserved_mixin(typename, self.scopename, type)

        return type

    def _add_subtype(self, basename, typename, t):
        """ サブタイプ定義を追加する """
        if basename == "Any":
            basename = SUBTYPE_BASE_ANY
        base = self._subtype_rels.setdefault(basename, {})
        base[typename] = t
        
    def add_definition(self, describer, classname=None) -> TypeDefinition:
        """ 型定義を作成する """
        td = TypeDefinition.new(describer, classname)
        return self.define(td)

    def _load_mixin(self, basename, basescope, t, *, reserve=False):
        """ mixin定義を追加する """
        basescope = basescope or CORE_SCOPE
        target = self._select_scoped(basescope, basename)
        if target is not None:
            # 定義を追加、もしくは追加を予約する
            target.mixin_load(t.get_describer())
            return

        # 型やスコープの定義がまだ無かった
        if reserve:
            li = self._loading_mixins.setdefault((basename, basescope), [])
            li.append(t)

    def _load_reserved_mixin(self, typename, scopename, target):
        """  """
        mi = self.root._loading_mixins.get((typename, scopename))
        if mi:
            for mt in mi:
                target.mixin_load(mt.get_describer())
            mi.clear()

    def _load_reserved_mixin_all(self):
        """  """
        for (name, scope), mts in self.root._loading_mixins.items():
            target = self._select_scoped(scope, name)
            if target is None:
                continue
            for mt in mts:
                target.mixin_load(mt.get_describer())
            mts.clear()

    #
    # 子モジュールを操作する
    #
    def get_scope(self, scopename):
        """ 取得する
        Returns:
            TypeModule:
        """
        return self._children.get(scopename)

    def add_scope(self, scopename, other):
        """ 追加する 
        Params:
            scopename(str): 
            other(TypeModule):
        """
        return self.update_scope(scopename, other, addonly=True)
    
    def update_scope(self, scopename, other, *, addonly=False):
        """ 追加する 
        Params:
            scopename(str): 
            other(TypeModule):
        """
        if scopename in self._children:
            if addonly:
                raise TypeModuleError("スコープ'{}'はこのモジュールに既に存在します".format(scopename)) 
            self._children[scopename].update(other)
        else:
            self._add_child(other, scopename)
        # 予約中のmixinを解決する
        self._load_reserved_mixin_all()

    def add_fundamentals(self):
        """ 基本型を追加する """
        from machaon.types.fundamental import fundamental_types
        self.add_scope(CORE_SCOPE, fundamental_types())
    
    def add_default_modules(self, names=None):
        """ 標準モジュールの型を追加する """
        from machaon.package.package import create_module_package
        from machaon.core.symbol import DefaultModuleNames
        names = names or DefaultModuleNames
        for module in names:
            pkg = create_module_package("machaon." + module)
            mod = pkg.load_type_module()
            if mod is None:
                continue
            self.update_scope(CORE_SCOPE, mod)

    def add_package_types(self, pkg, scope=CORE_SCOPE):
        """ 手動でパッケージを読み込み追加する """
        mod = pkg.load_type_module()
        if mod is None:
            return False
        self.update_scope(scope, mod)
        return True

    def remove_scope(self, scope):
        """ 削除する 
        Params:
            scope(str):
        """
        if scope in self._children:
            del self._children[scope]
        else:
            raise TypeModuleError("スコープ'{}'はこのモジュールに見つかりません".format(scope))

    def _add_child(self, child, scopename):
        """ 親モジュールを設定する """
        # 子に自らを親モジュールとして設定する
        child.parent = self
        child.scopename = scopename
        # mixinをrootへと引き継ぐ
        self.root._loading_mixins.update(child._loading_mixins)
        child._loading_mixins.clear()
        # 子の辞書に追加する
        self._children[scopename] = child

    def update(self, other):
        """ 
        二つのモジュールを一つに結合する。
        新モジュールの値が優先される
        Params:
            other(TypeModule):
        """
        other.scopename = self.scopename
        other.parent = self.parent
        self._lib_typename.update(other._lib_typename)
        self._lib_describer.update(other._lib_describer)
        self._lib_valuetype.update(other._lib_valuetype)
        self._subtype_rels.update(other._subtype_rels)
        self._children.update(other._children)
        # mixinはトップレベルのモジュールで予約する
        self.root._loading_mixins.update(other._loading_mixins)

    def check_loading(self):
        """
        型を一通り読み込んだ後にエラーをチェックする
        """
        not_found_mixins = []
        for k, li in self._loading_mixins.items():
            if li:
                not_found_mixins.append((k, li))
        if not_found_mixins:
            vals = []
            for (tn, scope), li in not_found_mixins:
                typename = get_scoped_typename(tn, scope or "<no-scope>")
                descs = " + ".join([desc.get_describer_qualname() for desc in li])
                vals.append("{} <- {}".format(typename, descs))
            raise TypeModuleError("対象の型が見つからなかったmixin実装が残っています:\n  " + ", ".join(vals))


    # 型登録の構文を提供
    class DefinitionSyntax():
        def __init__(self, parent):
            self._parent = parent
        
        def register(self, typename):
            if not is_valid_typename(typename):
                raise BadTypename(typename)
            def _define(doc, *, describer=None, value_type=None, scope=None, bits=0):
                d = TypeDefinition(describer, typename, value_type, doc, scope, bits)
                self._parent.define(d)
            return _define
        
        def __getattr__(self, typename):
            return self.register(typename)
        
        def __getitem__(self, typename):
            return self.register(typename)
        
    # 遅延登録
    def definitions(self):
        return self.DefinitionSyntax(self)

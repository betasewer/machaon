from typing import Dict, Optional, List, Union, Any, Generator

from machaon.core.symbol import (
    BadTypename, normalize_typename, BadMethodName, PythonBuiltinTypenames, 
    full_qualified_name, is_valid_typename,
    QualTypename
)
from machaon.core.type.decl import TypeProxy
from machaon.core.type.type import Type
from machaon.core.type.describer import TypeDescriber, create_type_describer


#
# 型定義モジュールのエラー 
#
class TypeModuleError(Exception):
    pass

# 
#
#
TYPECODE_FULLNAME = 1
TYPECODE_VALUETYPE = 2
TYPECODE_TYPENAME = 3
TYPECODE_DESCRIBERNAME = 4

SUBTYPE_BASE_ANY = 1



#
# 型取得インターフェース
#
class TypeModule:
    def __init__(self):
        self._defs: Dict[str, Type] = {} # fulltypename -> Type
        self._lib_typename: Dict[str, List[str]] = {} # typename -> fulltypename[]
        self._lib_describer: Dict[str, str] = {} # describer -> fulltypename
        self._lib_valuetype: Dict[str, str] = {} # valuetypename -> fulltypename
        self._reserved_mixins: Dict[str, List[TypeDescriber]] = {}

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
        return len(self._defs)
    
    #
    def _load_type(self, t: Type) -> Type:
        """ 型定義をロードする """
        #t.load_method_prototypes()
        return t
    
    def _select_type(self, value:str, code:int, module:str=None, *, noload=False) -> Optional[Type]:
        """ このライブラリから型定義を1つ取り出す """
        tdef = None
        if code == TYPECODE_FULLNAME:
            tdef = self._defs.get(value)
        elif code == TYPECODE_TYPENAME:
            tns = self._lib_typename.get(value, [])
            if module is not None:
                tns = [x for x in tns if x.startswith(module)]
            if tns:
                tdef = self._defs[QualTypename(value, tns[0]).stringify()]
        elif code == TYPECODE_VALUETYPE:
            tn = self._lib_valuetype.get(value)
            if tn is not None:
                tdef = self._defs[tn]
        elif code == TYPECODE_DESCRIBERNAME:
            tn = self._lib_describer.get(value)
            if tn is not None:
                tdef = self._defs[tn]
        
        if tdef is not None:
            if noload:
                return tdef
            else:
                return self._load_type(tdef)
        else:
            return None


    #
    # 型を取得する
    #
    def find(self, typename) -> Optional[Type]:
        """ 定義を不完全な型名と実装名で探索する 
        Params:
            typename(str|QualTypename): 不完全な型名+実装名
        Returns:
            Optional[Type]:
        """
        if isinstance(typename, QualTypename):
            qualname = typename
        elif isinstance(typename, str):
            qualname = QualTypename.parse(normalize_typename(typename))
        else:
            raise TypeError("typename")
        return self._select_type(qualname.typename, TYPECODE_TYPENAME, qualname.describer)
    
    def get(self, typecode: Any) -> Optional[TypeProxy]:
        """ 色々なデータから定義を探索する 
        Params:
            typecode(Any): str=完全な型名・不完全な型名 | Type=型定義そのもの | <class>=型の値型
        Returns:
            Optional[Type]:
        """
        if isinstance(typecode, TypeProxy):
            return typecode

        t = None
        if isinstance(typecode, str):
            qualname = QualTypename.parse(normalize_typename(typecode))
            if qualname.is_qualified():
                # 完全一致で検索する
                t = self._select_type(qualname.stringify(), TYPECODE_FULLNAME)
            else:
                # 型名のみの一致で検索する
                t = self._select_type(qualname.typename, TYPECODE_TYPENAME)
        elif hasattr(typecode, "Type_typename"):
            # 登録済みの型のデスクライバ
            tn = typecode.Type_typename
            modname = full_qualified_name(typecode)
            t = self._select_type(QualTypename(tn,modname).stringify(), TYPECODE_FULLNAME)
        elif isinstance(typecode, type):
            # 値型
            vtn = full_qualified_name(typecode)
            t = self._select_type(vtn, TYPECODE_VALUETYPE)
        else:
            raise TypeError("未対応のtypecodeです: {}".format(typecode))

        if t is None:
            return None

        return t

    def getall(self, *, geterror=False) -> Generator[Type, None, None]:
        """ すべての型をロードし、取得する
        Params:
            geterror(bool): 発生したエラーを取得する
        Yields:
            str, Type | (geterror) str, Type, ErrorObject
        """
        for fullname, t in self._defs.items():
            if geterror:
                try:
                    yield fullname, self._load_type(t), None
                except Exception as e:
                    from machaon.types.stacktrace import ErrorObject
                    yield fullname, None, ErrorObject(e)
            else:
                yield fullname, self._load_type(t)

    def deduce(self, value_type) -> Optional[TypeProxy]:
        """ 値型に適合する型を取得する
        Params:
            value_type(type|str):
        Returns:
            Optional[TypeProxy]: 
        """
        if isinstance(value_type, type):
            # ビルトイン型に対応する
            if hasattr(value_type, "__name__"): 
                typename = value_type.__name__
                if typename in PythonBuiltinTypenames.literals: # 基本型
                    return self.get(typename.capitalize())
                elif typename in PythonBuiltinTypenames.dictionaries: # 辞書型
                    return self.get("ObjectCollection")
                elif typename in PythonBuiltinTypenames.iterables: # イテラブル型
                    return self.get("Tuple")
            
            tn = full_qualified_name(value_type)
        elif isinstance(value_type, str):
            tn = value_type
        else:
            raise TypeError("value_type must be type or str instance, not '{}'".format(value_type))

        # 値型で検索する
        t = self._select_type(tn, TYPECODE_VALUETYPE)
        if t is not None:
            return t

        # 見つからなかった
        return None

    def select(self, typecode, describername:str=None):
        """ 型名を検索し、存在しない場合は定義のロードを試みる
        Params:
            typecode(str|type|dict): 型名/デスクライバ型/辞書型
            describername(str): 完全な実装名
        Returns:
            Type:
        """
        if isinstance(typecode, str):  
            # 型名      
            t = self._select_type(normalize_typename(typecode), TYPECODE_TYPENAME, module=describername)
            if t is not None:
                # mixinのロードを確認する
                if describername is not None:
                    if all(describername != x.get_full_qualname() for x in t.get_all_describers()):
                        mxtd = create_type_describer(describername)
                        t.mixin_method_prototypes(mxtd)
                return t
            else:
                # 対象モジュールから定義をロードする
                if describername is None:
                    raise BadTypename("型'{}'は存在しません。定義クラスの指定があればロード可能です".format(typecode))
                return self.define(describername, typename=typecode)
        
        elif isinstance(typecode, type):
            # デスクライバクラス型
            t = self._select_type(full_qualified_name(typecode), TYPECODE_DESCRIBERNAME)
            if t is not None:
                return t
            else:
                # このデスクライバから定義をロードする
                return self.define(typecode)
            
        elif isinstance(typecode, dict):
            # 辞書型
            desc = create_type_describer(typecode)
            t = self._select_type(desc.get_typename(), TYPECODE_TYPENAME, desc.get_full_qualname())
            if t is not None:
                return t
            else:
                return self.define(desc)

    def define(self, describer, *,
        typename = None, 
        value_type = None,
        doc = None,
        bits = 0,
        describername = None,
        typeclass = None
    ) -> Type:
        """ 型定義を作成する """
        if isinstance(describer, Type):
            return self._add_type(describer)
    
        desc = create_type_describer(describer, name=describername)
        if desc.is_typedef():
            t = (typeclass or Type)(desc)
            t.load(typename=typename, value_type=value_type, doc=doc, bits=bits)
            return self._add_type(t)
        elif desc.is_mixin():
            return self._add_type_mixin(desc, desc.get_mixin_target()) # ミキシンが予約された場合はNoneが返る

    def _add_type(self, type):
        """ 型をモジュールに追加する """
        if not type.is_loaded():
            raise ValueError("type must be loaded")
        
        tqualname: QualTypename = type.get_qual_typename()
        if not tqualname.is_qualified():
            raise TypeModuleError("型'{}'のデスクライバクラス名が指定されていません".format(tqualname))
        typename:str = tqualname.typename
        describername:str = tqualname.describer
        qualname:str = tqualname.stringify()

        # フルスコープ型名の辞書をチェックする
        if qualname in self._defs:
            raise TypeModuleError("型'{}'はこのモジュールに既に存在します".format(qualname))

        valuetypename = type.get_value_type_qualname()

        # 型名の辞書をチェックする
        if typename in self._lib_typename:
            descs = self._lib_typename[typename]
            if describername in descs:
                raise TypeModuleError("型'{}'はこのモジュールに既に存在します".format(qualname))
        else:
            self._lib_typename[typename] = []

        self._defs[qualname] = type
        self._lib_typename[typename].append(describername)
        self._lib_describer[describername] = qualname

        # 値型は最初に登録されたものを優先する
        if valuetypename not in self._lib_valuetype:
            self._lib_valuetype[valuetypename] = qualname

        # 予約済みのmixinロードを実行する
        self._inject_reserved_mixins(qualname, type)

        return type

    def _add_type_mixin(self, describer: TypeDescriber, target: str):
        """ Mixin実装を追加する """
        qt = QualTypename.parse(target)
        if not qt.is_qualified():
            raise ValueError("mixin対象の型名はデスクライバで修飾してください")
        t = self.find(qt)
        if t is not None:
            t.mixin_method_prototypes(describer)
            return t 
        else:
            # 予約リストに追加する
            mixins = self._reserved_mixins.setdefault(target, [])
            mixins.append(describer)
            return None

    def _inject_reserved_mixins(self, fulltypename: str, target: Type):
        """ 予約済みのmixin実装を型に追加し、リストから削除する """
        for key, mixins in self._reserved_mixins.items():
            if fulltypename.startswith(key): # 前方一致
                for mixin in mixins:
                    target.mixin_method_prototypes(mixin)
            mixins.clear()

    #
    # モジュールを操作する
    #
    def add_fundamentals(self):
        """ 基本型を追加する """
        from machaon.types.fundamental import fundamental_types
        self.update(fundamental_types())
    
    def add_package_types(self, pkg, *, reporterror=False):
        """ パッケージに定義された全ての型を追加する """
        mod = pkg.load_type_module()
        if reporterror and pkg.get_load_errors():
            for err in pkg.get_load_errors():
                raise err # 最初のエラーを再送する
        if mod is None:
            return False
        self.update(mod)
        return True

    def add_default_modules(self, names=None, *, reporterror=False):
        """ 標準モジュールの型を追加する """
        from machaon.package.package import create_module_package
        from machaon.core.symbol import DefaultModuleNames
        names = names or DefaultModuleNames
        for module in names:
            pkg = create_module_package("machaon." + module)
            self.add_package_types(pkg, reporterror=reporterror)

    def update(self, other):
        """ 
        二つのモジュールを一つに結合する。
        新モジュールの値が優先される
        Params:
            other(TypeModule):
        """
        self._defs.update(other._defs)
        for k, v in other._lib_typename.items():
            li = self._lib_typename.setdefault(k, [])
            li.extend(v)
        self._lib_describer.update(other._lib_describer)
        self._lib_valuetype.update(other._lib_valuetype)
        for k, v in other._reserved_mixins.items():
            li = self._reserved_mixins.setdefault(k, [])
            li.extend(v)
    
    def remove_scope(self, scope):
        """ 削除する 
        Params:
            scope(str):
        """
        if scope in self._children:
            del self._children[scope]
        else:
            raise TypeModuleError("スコープ'{}'はこのモジュールに見つかりません".format(scope))

    def check_loading(self):
        """
        型を一通り読み込んだ後にエラーをチェックする
        """
        not_found_mixins = []
        for k, li in self._reserved_mixins.items():
            if li:
                not_found_mixins.append((k, li))
        if not_found_mixins:
            vals = []
            for typename, li in not_found_mixins:
                descs = " + ".join([desc.get_full_qualname() for desc in li])
                vals.append("{} <- {}".format(typename, descs))
            raise TypeModuleError("対象の型が見つからなかったmixin実装が残っています:\n  " + ", ".join(vals))


    # 型登録の構文を提供
    class DefinitionSyntax():
        def __init__(self, parent):
            self._parent = parent

        def register(self, fulltypename):
            if not is_valid_typename(fulltypename):
                raise BadTypename(fulltypename)
            def _define(doc, *, value_type=None, bits=0):
                self._parent.define(fulltypename, value_type=value_type, doc=doc, bits=bits)
            return _define

        def __getattr__(self, typename):
            return self.register(typename)

        def __getitem__(self, typename):
            return self.register(typename)

    # 遅延登録
    def definitions(self):
        return self.DefinitionSyntax(self)



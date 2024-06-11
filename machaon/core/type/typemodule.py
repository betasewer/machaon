from typing import Dict, Optional, List, Union, Any, Generator

from machaon.core.symbol import (
    BadTypename, normalize_typename, BadMethodName, PythonBuiltinTypenames, 
    full_qualified_name, is_valid_typename,
    QualTypename
)
from machaon.core.type.decl import TypeProxy, SpecialTypeDecls
from machaon.core.type.type import Type
from machaon.core.type.describer import TypeDescriber, create_type_describer, detect_describer_name_type
from machaon.core.error import ErrorSet
from machaon.core.importer import module_loader, attribute_loader

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
        # 特殊型のインスタンス
        from machaon.core.type.instance import AnyType, ObjectType, UnionType
        self.AnyType = AnyType
        self.ObjectType = ObjectType
        # 特殊型関数
        self.UnionType = UnionType

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
    def _select_type(self, value:str, code:int, module:str=None) -> Optional[Type]:
        """ このライブラリから型定義を1つ取り出す """
        tdef = None
        if code == TYPECODE_FULLNAME:
            tdef = self._defs.get(value)
        elif code == TYPECODE_TYPENAME:
            if value in SpecialTypeDecls:
                raise BadTypename("'{}'は型名として使用できません".format(value))
            tns = self._lib_typename.get(value, [])
            if module is not None:
                tns = [x for x in tns if x.startswith(module)]
            if tns:
                if tns[0]:
                    tn = QualTypename(value, tns[0]).stringify()
                else:
                    tn = value
                tdef = self._defs[tn]
        elif code == TYPECODE_VALUETYPE:
            tn = self._lib_valuetype.get(value)
            if tn is not None:
                tdef = self._defs[tn]
        elif code == TYPECODE_DESCRIBERNAME:
            tn = self._lib_describer.get(value)
            if tn is not None:
                tdef = self._defs[tn]
        
        if tdef is not None:
            return tdef
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
            typecode(Any): str=修飾された完全な型名 | 修飾されていない不完全な型名 | Type=型定義そのもの | <class>=型の値型
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
                # 型名の部分一致で検索する
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
        # メソッドが利用可能な特殊型も含まれる
        def special_type(x):
            r = (x.get_typename(), x)
            return r + (None,) if geterror else r
        yield special_type(self.ObjectType)

        # モジュール型
        for fullname, t in self._defs.items():
            if geterror:
                try:
                    yield fullname, t, None
                except Exception as e:
                    from machaon.types.stacktrace import ErrorObject
                    yield fullname, None, ErrorObject(e)
            else:
                yield fullname, t

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

    def select(self, typecode, describername:str=None, resolver=None):
        """ 型名を検索し、存在しない場合は定義のロードを試みる
        Params:
            typecode(QualTypename|str|type|dict): 型名/デスクライバ型/辞書型
            describername(str): 完全な実装名
        Returns:
            Type:
        """
        if isinstance(typecode, QualTypename):
            describername = typecode.describer
            typecode = typecode.typename

        if isinstance(typecode, str):  
            # 型名で検索する
            typename = normalize_typename(typecode)
            t = self._select_type(typename, TYPECODE_TYPENAME, module=describername)
            if t is not None:
                return t
            
            # 可能なら型名を解決する
            if resolver is not None:
                tqn: QualTypename = resolver.resolve(typename, describername)
                if tqn:
                    typename = tqn.typename
                    describername = tqn.describer

            # 対象モジュールから定義をロードする
            if describername is None:
                raise BadTypename("型'{}'は存在しません。定義クラス・モジュール・パッケージの指定があればロード可能です".format(typecode))
            
            target, isklass = detect_describer_name_type(describername)
            if target is None:
                raise TypeModuleError("デスクライバ'{}'はクラス名、モジュール名、パッケージ名のいずれでもありません".format(describername))
            if isklass: # クラス
                return self.define(target, typename=typename)
            else: # モジュール or パッケージの全ての型をロードする
                err = None
                try:
                    self.use_module_or_package_types(target, fallback=True)
                except Exception as e:
                    err = e
                # 再度型名で探索
                t = self._select_type(typename, TYPECODE_TYPENAME, describername) 
                if t is None:
                    if err is not None: 
                        raise err # 型が見つからなかった場合のみ、読み込み時に起きたエラーを投げる
                    else:
                        raise BadTypename("型'{}'の定義はモジュールまたはパッケージ'{}'に見つかりませんでした".format(typename, describername))
                return t
    
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
            
    def mixin(self, type: TypeProxy, describername):
        """ mixinとしてロードする """
        target, isklass = detect_describer_name_type(describername)
        if target is None:
            raise TypeModuleError("Mixin対象が不明です")
        if isklass:
            self.inject_type_mixin(target, type)
        else:
            # モジュールまたはパッケージの型を全てロードする（対象以外の型も変更される）
            self.use_module_or_package_types(target, fallback=True)


    #
    #
    #   
    def define(self, describer, *,
        typename = None, 
        value_type = None,
        doc = None,
        bits = 0,
        describername = None,
        typeclass = None,
        fallback = False
    ) -> Type:
        """ 型定義を作成する """
        if isinstance(describer, Type):
            return self._add_type(describer, fallback=fallback)
    
        desc = create_type_describer(describer, name=describername)
        if desc.is_typedef():
            t = (typeclass or resolve_typeclass(desc.get_value_full_qualname()))(desc)
            t.load(typename=typename, value_type=value_type, doc=doc, bits=bits)
            return self._add_type(t, fallback=fallback)
        elif desc.is_mixin():
            return self._add_type_mixin(desc, desc.get_mixin_target()) # ミキシンが予約された場合はNoneが返る

    def _add_type(self, type, *, fallback=False):
        """ 型をモジュールに追加する """
        if not type.is_loaded():
            raise ValueError("type must be loaded")
        
        tqualname: QualTypename = type.get_qual_typename()
        if not tqualname.is_qualified():
            raise TypeModuleError("型'{}'のデスクライバクラス名が指定されていません".format(tqualname))
        typename:str = tqualname.typename
        qualname:str = tqualname.stringify()
        describername:str = tqualname.describer
        original_describername:str = type.get_describer().get_value_full_qualname()

        # フルスコープ型名の辞書をチェックする
        if qualname in self._defs:
            if fallback: return
            raise TypeModuleError("型'{}'はこのモジュールに既に存在します".format(qualname))

        valuetypename = type.get_value_type_qualname()

        # 型名の辞書をチェックする
        if typename in self._lib_typename:
            descs = self._lib_typename[typename]
            if describername in descs:
                if fallback: return
                raise TypeModuleError("型'{}'はこのモジュールに既に存在します".format(qualname))

        # デスクライバの辞書をチェックする
        if original_describername in self._lib_describer:
            tn = self._lib_describer[original_describername]
            return self._defs[tn] # デスクライバの重複はエラーにしない

        # 型の登録を開始する
        self._defs[qualname] = type
        self._lib_typename.setdefault(typename, []).append(describername)

        # デスクライバは本名で登録する
        self._lib_describer[original_describername] = qualname

        # 値型は最初に登録されたものを優先する
        if valuetypename not in self._lib_valuetype:
            self._lib_valuetype[valuetypename] = qualname

        # 予約済みのmixinロードを実行する
        self._inject_reserved_mixins(qualname, type)

        return type

    def inject_type_mixin(self, describername, target_type: Type):
        """ Mixin実装を追加する """
        mxtd = create_type_describer(describername)
        if not mxtd.is_mixin():
            raise ValueError("mixin実装ではありません")
        if all(mxtd.get_full_qualname() != x.get_full_qualname() for x in target_type.get_all_describers()):
            target_type.mixin_method_prototypes(mxtd)

    def _add_type_mixin(self, describer: TypeDescriber, target: str):
        """ Mixin実装を追加する """
        qt = QualTypename.parse(target)
        if not qt.is_qualified():
            raise ValueError("{}: mixin対象の型名'{}'はデスクライバで修飾してください".format(describer.get_full_qualname(), target))
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
    
    def add_default_module_types(self, names=None):
        """ 標準モジュールの型を追加する """
        from machaon.core.symbol import DefaultModuleNames
        names = names or DefaultModuleNames
        with ErrorSet("標準モジュールの型を追加") as errs:
            for module in names:
                try:
                    name = "machaon."+module
                    self.use_module_or_package_types(name, fallback=True)
                except Exception as e:
                    errs.add(e, value=name)

    def use_module_or_package_types(self, name, fallback=False):
        """ モジュールあるいはパッケージ内の型を追加する """
        if isinstance(name, str):
            mod = module_loader(name)
        else:
            mod = name
        with ErrorSet("'{}'に定義された全ての型をロード".format(name)) as errs:
            for mod in mod.load_all_module_loaders():
                for desc in mod.load_all_describers():
                    try:
                        self.define(desc, fallback=fallback) # 重複した場合は単にスルーする
                    except Exception as e:
                        errs.add(e, value=desc.get_full_qualname())

    def add_special_type(self, t, describername=None):
        """ 特殊な型を追加する """
        qname = QualTypename(t.get_typename(), describername).stringify()
        self._defs[qname] = t
        self._lib_typename[t.get_typename()] = [describername or ""]
        self._lib_valuetype[full_qualified_name(t.get_value_type())] = qname

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
        # mixinを全ての型に試し、残りのリストを引き取る
        for fulltypename, type in self._defs.items():
            other._inject_reserved_mixins(fulltypename, type)
        for k, v in other._reserved_mixins.items():
            li = self._reserved_mixins.setdefault(k, [])
            li.extend(v)
    
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


#
#
#
def resolve_typeclass(describername):
    from machaon.core.type.fundamental import ObjectCollectionType
    return {
        "machaon.core.object.ObjectCollection" : ObjectCollectionType
    }.get(describername, Type)

from typing import Union

from machaon.core.symbol import (
    BadTypename, normalize_typename, full_qualified_name, QualTypename
)
from machaon.core.type.type import (
    TYPE_OBJCOLTYPE, Type, TYPE_TYPETRAIT_DESCRIBER, TYPE_USE_INSTANCE_METHOD,
    BadTypeDeclaration
)
from machaon.core.type.instance import UnspecifiedTypeParam

from machaon.core.type.describer import TypeDescriber, TypeDescriberClass, TypeDescriberDict
from machaon.core.importer import attribute_loader
from machaon.core.docstring import parse_doc_declaration



class TypeDefinition:
    """
    クラス文字列から型をロードする
    """
    def __init__(self, 
        describer: Union[str, TypeDescriber] = None, 
        typename: str = None, 
        value_type = None, 
        doc = "", 
        bits = 0,
        modulename = None,
        # 直接設定可能
        mixinto = None,
        subtypeof = None,
    ):
        self.value_type = value_type # Noneの可能性がある

        if describer is None:
            # 型名のみが指定されているなら、クラス実装もそこにあるとみなす
            if isinstance(value_type, str):
                describer = value_type
            elif value_type is not None:
                describer = TypeDescriberClass(value_type)
            else:
                raise BadTypeDeclaration("value_typeかdescriberを、クラスまたは文字列で与えてください")

        if isinstance(describer, str):
            describer = TypeDescriberClass(attribute_loader(describer))
        elif isinstance(describer, dict):
            describer = TypeDescriberDict(describer)
        elif isinstance(describer, type):
            describer = TypeDescriberClass(describer)
        elif isinstance(describer, TypeDescriber):
            pass
        else:
            raise BadTypeDeclaration("'describer' must be instance of 'str', 'dict', 'type' or 'TypeDescriber', but given '{}'".format(describer))
        
        self.describer = describer

        self.typename = typename
        if typename and not isinstance(typename, str):
            raise BadTypeDeclaration("型名を文字列で指定してください")     
        self.modulename = modulename
        
        self.doc = doc
        if self.doc:
            self.doc = self.doc.strip()
        self.bits = bits
        self.params = [] # 型パラメータ
        self.memberaliases = []

        self._t = None

        self._sub_target = None # Mixin, Subtypeのターゲット
        if mixinto is not None:
            self.bits |= TYPE_MIXIN
            self._sub_target = mixinto
        if subtypeof is not None:
            self.bits |= TYPE_SUBTYPE
            self._sub_target = subtypeof
        
        self._mixins = [] # Mixinされるクラス
    
    def is_loaded(self):
        return self._t is not None

    def _resolve_value_type(self):
        if self.value_type is None:
            self.value_type = self.describer.klass
        elif isinstance(self.value_type, str):
            loader = attribute_loader(self.value_type)
            self.value_type = loader()
        elif not isinstance(self.value_type, type):
            raise BadTypeDescription("Cannot resolve value_type")

    def get_typename(self):
        return self.typename

    def get_value_type(self):
        self._resolve_value_type()
        return self.value_type

    def get_value_type_qualname(self):
        if self.value_type is None:
            return self.describer.get_full_qualname()
        elif isinstance(self.value_type, str):
            return self.value_type
        else:
            return full_qualified_name(self.value_type)
            # raise BadTypeDescription("Cannot resolve value_type qualname from '{}'".format(self.value_type))

    def get_describer(self):
        return self.describer

    def get_describer_qualname(self):
        return self.describer.get_full_qualname()

    def get_all_describers(self):
        return [self.describer, *self._mixins]
    
    def get_qual_typename(self):
        if self.modulename:
            describer = self.modulename + "." + self.typename
        else:
            describer = self.get_describer_qualname()
        return QualTypename(self.typename, describer)

    def is_same_value_type(self, vt):
        # TypeModule.deduceで使用 - ロードせずに名前で一致を判定する
        if self.value_type is None:
            return self.describer.get_full_qualname() == full_qualified_name(vt)
        elif isinstance(self.value_type, str):
            return self.value_type == full_qualified_name(vt)
        else:
            return self.value_type is vt

    def get_loaded(self):
        return self._t

    def is_subtype(self):
        return self.bits & TYPE_SUBTYPE > 0

    def is_mixin(self):
        return self.bits & TYPE_MIXIN > 0

    def get_sub_target(self):
        return self._sub_target

    def proto_define(self):
        """ 
        型登録の直前に設定値を補完する処理 
        Returns:
            Str: 登録名. Noneなら登録しない
        """
        # 以下、型名が必要
        if self.typename is None:
            if self.describer.get_classname() is not None:
                # クラス名から補完する
                name = self.describer.get_classname()
                if not name[0].isupper():
                    name = name[0].upper() + name[1:]
                self.typename = normalize_typename(name)
            else:
                raise BadTypeDescription("TypeDefinition typename is not defined")
        
        if self.bits & TYPE_SUBTYPE:
            # Subtype型
            self.bits |= TYPE_TYPETRAIT_DESCRIBER
            self.value_type = _SubtypeBaseValueType # 代入しておかないと補完されてエラーになる

        # 型名を登録する
        return self.typename

    def load_type(self) -> Type:
        """ 実行時に型を読み込み定義する """
        if self._t is not None:
            return self._t
        
        self._resolve_value_type()
        
        # フラグによって特殊な型を使う
        if self.bits & TYPE_OBJCOLTYPE:
            from machaon.core.type.fundamental import ObjectCollectionType
            typeclass = ObjectCollectionType
        else:
            typeclass = Type

        self._t = typeclass(
            self.describer, 
            name=self.typename,
            value_type=self.value_type,
            params=self.params,
            doc=self.doc,
            bits=self.bits,
            modulename=self.modulename
        )
        try:
            self._t.load()
        except Exception as e:
            raise BadTypeDeclaration(self.typename) from e

        for name, row in self.memberaliases:
            self._t.add_member_alias(name, row)

        for mx in self._mixins:
            self._t.mixin_load(mx)

        return self._t

    def mixin_load(self, describer):
        if self._t is not None:
            self._t.mixin_load(describer)
        else:
            self._mixins.append(describer)

    @classmethod
    def new(cls, describer, *, modulename=None, typename=None, value_type=None, doc="", bits=0):       
        """ クラス定義から読み込み前の型定義を作成する """ 
        if isinstance(describer, TypeDefinition):
            td = describer
        else:
            if isinstance(describer, str):
                # 実装付きの型名、あるいは実装名
                qualname = QualTypename.parse(describer)
                if qualname.is_qualified():
                    describer = qualname
            if isinstance(describer, QualTypename):
                # 実装付きの型名
                typename = describer.typename
                describer = describer.describer

            td = TypeDefinition(describer, modulename=modulename, typename=typename, value_type=value_type, doc=doc, bits=bits)
        if not td.load_docstring():
            raise BadTypeDescription("Fail to load declaration")
        return td

# ダミーの値型に使用
class _SubtypeBaseValueType:
    pass








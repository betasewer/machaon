from typing import Union

from machaon.core.symbol import (
    BadTypename, normalize_typename, full_qualified_name
)
from machaon.core.type.type import (
    TYPE_OBJCOLTYPE, Type, TYPE_MIXIN, TYPE_SUBTYPE, TYPE_TYPETRAIT_DESCRIBER, TYPE_USE_INSTANCE_METHOD,
    BadTypeDeclaration
)
from machaon.core.type.instance import UnspecifiedTypeParam

from machaon.core.method import (
    PARAMETER_REQUIRED, MethodParameter,
    parse_type_declaration, parse_result_line, parse_parameter_line, 
)
from machaon.core.importer import ClassDescriber, attribute_loader
from machaon.core.docstring import parse_doc_declaration


class BadTypeDescription(Exception):
    """ 型定義の記述に誤りがある """


class TypeDefinition():
    """
    クラス文字列から型をロードする
    """
    def __init__(self, 
        describer: Union[str, ClassDescriber] = None, 
        typename: str = None, 
        value_type = None, 
        doc = "", 
        bits = 0,
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
                describer = ClassDescriber(value_type)
            else:
                raise BadTypeDescription("value_typeかdescriberを、クラスまたは文字列で与えてください")

        if not isinstance(describer, (str, ClassDescriber)):
            raise TypeError("describer type must be 'str' or 'core.importer.ClassDescriber'")
        if isinstance(describer, str):
            describer = ClassDescriber(attribute_loader(describer))
        self.describer = describer

        self.typename = typename
        if typename and not isinstance(typename, str):
            raise BadTypeDescription("型名を文字列で指定してください")     
        
        self.doc = doc
        if self.doc:
            self.doc = self.doc.strip()
        self.bits = bits
        self.params = [] # 型パラメータ
        self.memberaliases = [] 
        self.scope = None

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
            raise BadTypeDescription("Cannot resolve value_type qualname")

    def get_describer(self):
        return self.describer

    def get_describer_qualname(self):
        return self.describer.get_full_qualname()
        
    def get_all_describers(self):
        return [self.describer, *self._mixins]

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
        """ 型を登録する時点での処理 
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
            scope=self.scope,
            bits=self.bits
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
    
    def load_docstring(self, doc=None):
        """
        型定義の解析
        """
        """ @type trait use-instance-method subtype mixin [name aliases...]
        detailed description...
        .......................

        ValueType:
            <Typename>
        Params:
            name(typeconversion): description...
        MemberAlias:
            long: (mode ftype modtime size name)
            short: (ftype name)
            link: path
        MixinType:
            <Typename> (mixin target type)
        BaseType:
            <Typename> (subtype base type)
        """
        if doc is None:
            doc = self.get_describer().get_docstring()
            if doc is None:
                return False
        
        decl = parse_doc_declaration(doc, ("type",))
        if decl is None:
            return False
            
        # 定義部をパースする
        sections = decl.create_parser(("ValueType", "Params", "MemberAlias", "BaseType", "MixinType"))
        
        # Mixin宣言はあらかじめ読み込む
        if "mixin" in decl.props:
            self.bits |= TYPE_MIXIN
            mixin = sections.get_value("MixinType")
            if mixin is None:
                raise BadTypeDescription("mixin対象を'MixinType'で指定してください")
            self._sub_target = mixin.rstrip(":") # コロンがついていてもよしとする
            return True

        # Subtype宣言も
        elif "subtype" in decl.props:
            self.bits |= TYPE_SUBTYPE
            base = sections.get_value("BaseType")
            if base is None:
                raise BadTypeDescription("ベースクラスを'BaseType'で指定してください")
            self._sub_target = base.rstrip(":") # コロンがついていてもよしとする

        else:
            if "use-instance-method" in decl.props:
                self.bits |= TYPE_USE_INSTANCE_METHOD
            if "trait" in decl.props:
                self.bits |= TYPE_TYPETRAIT_DESCRIBER

        decltypename = decl.get_first_alias()
        if decltypename:
            self.typename = decltypename
        
        document = ""
        document += sections.get_string("Document")
        if document:
            self.doc = document.strip()

        valtypename = sections.get_value("ValueType")
        if valtypename:
            self.value_type = valtypename.rstrip(":") # コロンがついていてもよしとする
        
        # 型引数
        for line in sections.get_lines("Params"):
            typename, name, doc, flags = parse_parameter_line(line.strip())
            typedecl = parse_type_declaration(typename)

            # 全てオプショナル引数にする
            flags &= ~PARAMETER_REQUIRED 
            if typename == "Type":
                default = UnspecifiedTypeParam # デフォルト値
            else:
                default = None

            p = MethodParameter(name, typedecl, doc, default, flags)
            self.params.append(p)

        aliases = sections.get_lines("MemberAlias")
        for alias in aliases:
            name, _, dest = [x.strip() for x in alias.partition(":")]
            if not name or not dest:
                raise BadTypeDescription()

            if dest[0] == "(" and dest[-1] == ")":
                row = dest[1:-1].split()
                self.memberaliases.append((name, row))

        return True

    @classmethod
    def new(cls, describer, classname=None):       
        """ クラス定義から読み込み前の型定義を作成する """ 
        if not isinstance(describer, (str, ClassDescriber)):
            describer = ClassDescriber(describer)
        td = TypeDefinition(describer, classname)
        if not td.load_docstring():
            raise BadTypeDescription("Fail to load declaration")
        return td

# ダミーの値型に使用
class _SubtypeBaseValueType:
    pass

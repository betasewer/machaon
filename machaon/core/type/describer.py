from machaon.core.symbol import (
    full_qualified_name, QualTypename, normalize_typename
)
from machaon.core.type.basic import (
    BadTypeDeclaration,
)
from machaon.core.docstring import (
    parse_doc_declaration, DocStringDefinition, get_doc_declaration_type
)
from machaon.core.type.declresolver import BasicTypenameResolver
from machaon.core.method import (
    Method, BadMethodDeclaration,
    make_method_prototype_from_doc, 
    make_method_from_dict,
    meta_methods,
    parse_result_line, parse_parameter_line, 
)
from machaon.core.importer import (
    enum_attributes, attribute_loader, module_loader, AttributeLoader
)

DESCRIBE_TYPE_UNKNOWN = 0
DESCRIBE_TYPE_TYPEDEF = 1
DESCRIBE_TYPE_MIXIN = 2

#
#
#
class TypeDescriber:
    def __init__(self):
        self._typename = None
        self._qualname = None
        self._type = DESCRIBE_TYPE_UNKNOWN

    # 定義タイプを読み込む
    def load_describe_type(self):
        c = self.get_describe_type()
        self._type = c if c is not None else DESCRIBE_TYPE_UNKNOWN
        return self._type
    
    def get_describe_type(self):
        raise NotImplementedError()
    
    def is_valid(self): # 定義がある
        return self._type != DESCRIBE_TYPE_UNKNOWN

    def is_typedef(self): # 型定義である
        return self._type == DESCRIBE_TYPE_TYPEDEF
    
    def is_mixin(self): # ミキシン定義である
        return self._type == DESCRIBE_TYPE_MIXIN

    # あらかじめ型名を定義できる
    def set_typename(self, name):
        self._typename = name

    def get_typename(self):
        if self._typename is not None:
            return self._typename
        name = self.get_value_typename()
        if name is not None:
            if not name[0].isupper():
                name = name[0].upper() + name[1:]
            return name
        return None
    
    # デスクライバの名前
    def set_full_qualname(self, name):
        self._qualname = name

    def get_full_qualname(self):
        if self._qualname is not None:
            return self._qualname
        return self.get_value_full_qualname()
        
    def get_value_full_qualname(self):
        raise NotImplementedError()

    # 
    def get_value(self):        
        raise NotImplementedError()
    
    def get_value_typename(self):
        raise NotImplementedError()
    
    def get_value_type_qualname(self):
        raise NotImplementedError()

    # 型定義
    def describe_type(self, type):
        raise NotImplementedError()

    def describe_methods(self, type, mixinkey):
        raise NotImplementedError()

    def get_method_attribute(self, name):
        raise NotImplementedError()

    def get_metamethod_attribute(self, name):
        raise NotImplementedError()
    
    # mixin
    def get_mixin_target(self):
        raise NotImplementedError()
    
    # 型名解決
    def get_typename_resolver(self):
        raise NotImplementedError()
    
    
    

class TypeDescriberClass(TypeDescriber):
    '''
    クラスに定義された実装
    """ @type trait use-instance-method [name aliases...]
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
    """
    '''
    def __init__(self, resolver, docstring=None):
        super().__init__()
        self._resolver = resolver
        self._resolved = None
        self._doc = docstring
        self._typename_resolver = BasicTypenameResolver()

    @property
    def klass(self):
        if self._resolved is not None:
            return self._resolved        
        if isinstance(self._resolver, type):
            self._resolved = self._resolver
        elif isinstance(self._resolver, AttributeLoader):
            self._resolved = self._resolver()
            self._typename_resolver = self._resolver.module.get_typename_resolver()
        else:
            raise TypeError(self._resolver)
        return self._resolved

    def get_value_typename(self):
        """ 名前を取得 """
        if isinstance(self._resolver, type):
            return getattr(self._resolver, "__name__", None)
        else:
            return self._resolver.get_name()

    def get_value_full_qualname(self):
        """ ロードせずにフルネームを取得 """
        if isinstance(self._resolver, type):
            return full_qualified_name(self._resolver)
        else:
            return self._resolver.get_qualname()

    def get_value(self):
        return self.klass
    
    def get_docstring(self):
        """ ドキュメント文字列を取得 """
        if self._doc is not None:
            return self._doc
        else:
            doc = getattr(self.klass, "__doc__", None)
            return doc if doc else ""

    def describe_type(self, type):
        """ 
        型オブジェクトを構築する
        """
        # クラス文字列を解析
        doc = self.get_docstring()
        decl = parse_doc_declaration(doc, ("type",))
        if decl is None:
            raise ValueError("{}: 型定義は@typeを先頭に記述してください".format(self.get_full_qualname()))
        defs = DocStringDefinition.parse(decl, ("ValueType", "Params", "MemberAlias", "BaseType"))
        
        if defs.is_declared("use-instance-method"):
            type.use_instance_method()
        if defs.is_declared("trait"):
            type.use_typetrait_describer() 

        decltypename = defs.get_first_alias()
        if decltypename:
            type.set_typename(decltypename)
        else:
            type.set_typename(self.get_typename())

        document = ""
        document += defs.get_string("Document")
        if document:
            type.set_document(document.strip())

        valtypename = defs.get_value("ValueType")
        if valtypename:
            type.set_value_type(valtypename.rstrip(":")) # コロンがついていてもよしとする
        else:
            type.set_value_type(self.klass) # デスクライバクラスと同じ型

        # 型引数
        for line in defs.get_lines("Params"):
            typename, name, doc, flags = parse_parameter_line(line.strip())
            typedecl = BasicTypenameResolver().parse_type_declaration(typename) # 基本型のみなので解決は不要
            type.add_type_param(name, typedecl, doc, flags)

        for alias in defs.get_lines("MemberAlias"):
            name, _, dest = [x.strip() for x in alias.partition(":")]
            if not name or not dest:
                raise BadTypeDeclaration("error in the MemberAlias('{}')".format(name))

            if dest[0] == "(" and dest[-1] == ")":
                row = dest[1:-1].split()
                type.add_member_alias(name, row)

        if hasattr(self.klass, "describe_type"):
            self.klass.describe_type(type) # type: ignore

    def describe_methods(self, type, mixinkey):
        """
        メソッド要素を列挙する
        """
        for attrname, attrval in enum_attributes(self.klass, self.klass):      
            # メソッド      
            decl = parse_doc_declaration(attrval, ("method", "task"))
            if decl is not None:
                method, aliasnames = make_method_prototype_from_doc(decl, attrname, mixinkey)
                if method is None:
                    continue
                type.add_method(method, aliasnames)
                continue

            # メタメソッド
            decl = parse_doc_declaration(attrval, ("meta",))
            if decl is not None:
                method = meta_methods.get_prototype(attrname)
                if method is None:
                    continue
                type.add_meta_method(method)
                continue
    
    def get_method_attribute(self, name):
        return getattr(self.klass, name, None)

    def get_metamethod_attribute(self, name):
        return getattr(self.klass, name, None)
    
    def get_describe_type(self):
        """ 定義の種類を読み取る """
        doc = self.get_docstring()
        decltype = get_doc_declaration_type(doc)
        if decltype == "type":
            return DESCRIBE_TYPE_TYPEDEF
        elif decltype == "mixin":
            return DESCRIBE_TYPE_MIXIN
        else:
            return None
    
    def get_mixin_target(self):
        """ mixin対象を得る """
        doc = self.get_docstring()
        decl = parse_doc_declaration(doc, ("mixin",))
        if decl is None:
            raise ValueError("{}: mixin定義は@mixinを先頭に記述してください".format(self.get_full_qualname()))
        defs = DocStringDefinition.parse(decl, ("MixinType",))
        mixin = defs.get_value("MixinType")
        if mixin is None:
            raise BadTypeDeclaration("mixin対象を'MixinType'で指定してください")
        t = mixin.rstrip(":") # コロンがついていてもよしとする
        # 型名を解決する
        decl = self.get_typename_resolver().parse_type_declaration(t)
        return decl.to_string()
    
    def get_typename_resolver(self):
        """ リゾルバを返す """
        return self._typename_resolver


class TypeDescriberDict(TypeDescriber):
    """
    辞書で型を定義する
    """
    def __init__(self, d):
        super().__init__()
        self.d: dict = d

    def get_describe_type(self):
        """ 定義の種類を読み取る """
        if "MixinType" in self.d:
            return DESCRIBE_TYPE_MIXIN
        elif "Typename" in self.d:
            return DESCRIBE_TYPE_TYPEDEF
        else:
            return None

    #
    def get_value_typename(self):
        return self.d.get("Typename")

    def get_value_full_qualname(self):
        qualname = self.d.get("DescriberName")
        if qualname is None:
            raise ValueError("No DescriberName")
        return qualname

    def get_value(self):
        return self.d
    
    def describe_type(self, type):
        type.use_typetrait_describer()
        
        type.set_typename(self.get_typename())

        document = self.d.get("Doc") or self.d.get("Document")
        if document:
            type.set_document(document.strip())

        valtypename = self.d.get("ValueType")
        if valtypename:
            type.set_value_type(valtypename)
    
    def describe_methods(self, type, mixinkey):
        if not "Methods" in self.d:
            raise BadTypeDeclaration("'Methods'メンバが必要です")    
        for v in self.d["Methods"]:
            name = v.pop("Name", None)
            if name is None:
                raise BadMethodDeclaration("メソッド名を指定してください")
            mth = make_method_from_dict(name, v, mixinkey)
            type.add_method(mth, v.get("Alias", ()))

    def get_method_attribute(self, name):
        entry = self.d["Methods"].get(name)
        if entry is not None:
            return entry["Action"]
        return None

    def get_metamethod_attribute(self, name):
        entry = self.d["MetaMethods"].get(name)
        if entry is not None:
            return entry["Action"]
        return None
    
    def get_mixin_target(self):
        tg = self.d.get("MixinType")
        if tg is None:
            raise ValueError("No MixinType")
        return tg
    


def create_type_describer(describer, *, name=None): 
    """ クラス定義から読み込み前の型定義・mixin定義を作成する """ 
    typename = None
    if isinstance(describer, str):
        # 実装付きの型名、あるいは実装名
        qualname = QualTypename.parse(describer)
        if qualname.is_qualified():
            describer = qualname
    if isinstance(describer, QualTypename):
        # 実装付きの型名
        typename = describer.typename
        describer = describer.describer

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
    
    # 型定義かミキシンか判断する
    describer.load_describe_type()

    # デスクライバの名前を変更する
    if name is not None:
        describer.set_full_qualname(name)
    # 型名を紐づける
    if typename is not None:
        describer.set_typename(typename)

    return describer


def detect_describer_name_type(klass_or_module_or_package):
    """ デスクライバ名の差す対象を分析する
    Returns:
        ModuleLoader|str:
        bool: Tでクラス名、Fでモジュールまたはパッケージ
    """
    mod = module_loader(klass_or_module_or_package)
    if mod.exists():
        return mod, False
    elif "." in klass_or_module_or_package:
        return klass_or_module_or_package, True
    else:
        return None, False
    

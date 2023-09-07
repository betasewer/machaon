from machaon.core.type.decl import parse_type_declaration
from machaon.core.symbol import SPECIAL_TYPE_NAMES
from machaon.types.fundamental import fundamental_typenames, fundamental_describer_name


class BasicTypenameResolver:
    """ 一切の解決を行わない """
    def parse_type_declaration(self, name):
        return parse_type_declaration(name)

class ModuleTypenameResolver:
    """
    型の修飾がある
        実装名が大文字から開始 -> 同じモジュールにある実装とみなし補完
        その他 -> そのまま
    型の修飾が無い
        -> klassのUsingから探す
        -> moduleのUsingから探す
        -> fundamental_typesから探す
        -> 同じモジュールにある実装とみなし補完
    """
    def __init__(self, this_module, module_using_types, klass_using_types=None):
        self.module_using_types = module_using_types or []
        self.klass_using_types = klass_using_types or []
        self.this_module: str = this_module

    def resolve(self, typename, describername):
        """ 
        Returns:
            QualTypename
        """
        if describername:
            if describername[0].isupper():
                return typename, "{}.{}".format(self.this_module, describername)
            else:
                return typename, describername
        else:
            if typename in SPECIAL_TYPE_NAMES:
                return typename, None
            
            for ut in self.klass_using_types:
                if ut.typename == typename:
                    return ut.typename, ut.describer
            
            for ut in self.module_using_types:
                if ut.typename == typename:
                    return ut.typename, ut.describer
            
            for fn in fundamental_typenames:
                if fn.typename == typename:
                    return fn.typename, fundamental_describer_name

            return typename, "{}.{}".format(self.this_module, typename)

    def parse_type_declaration(self, name):
        decl = parse_type_declaration(name)
        decl.resolve(self.resolve)
        return decl


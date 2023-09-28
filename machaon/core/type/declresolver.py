from machaon.core.symbol import SPECIAL_TYPE_NAMES, QualTypename
from machaon.types.fundamental import fundamental_typenames, fundamental_describer_name


def resolve_basic(typename):
    """ 特殊型の型名を解決 """
    if typename in SPECIAL_TYPE_NAMES:
        return QualTypename(typename)
    return None

def resolve_fundamental(typename):
    """ Pythonビルトイン型の型名を解決 """
    if typename in py_anon_redirection:
        typename = py_anon_redirection[typename]
    
    for fn in fundamental_typenames:
        if fn.typename == typename:
            return QualTypename(fn.typename, fundamental_describer_name)



class BasicTypenameResolver:
    """ デフォルトの解決のみを行う """
    def resolve(self, typename, describername):
        if describername is None:
            qn = resolve_basic(typename)
            if qn: return qn

            qn = resolve_fundamental(typename)
            if qn: return qn
            
        return QualTypename(typename, describername)
    

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
                return QualTypename(typename, "{}.{}".format(self.this_module, describername))
            else:
                return QualTypename(typename, describername)
        else:
            qn = resolve_basic(typename)
            if qn: return qn

            for ut in self.klass_using_types:
                if ut.typename == typename:
                    return ut
            
            for ut in self.module_using_types:
                if ut.typename == typename:
                    return ut
            
            qn = resolve_fundamental(typename)
            if qn: return qn

            # このモジュールに定義された型
            return QualTypename(typename, "{}.{}".format(self.this_module, typename))



#
# Python標準の型注釈に対応
#
py_anon_redirection = {
    "list" : "Tuple",
    "List" : "Tuple",
    "Sequence" : "Tuple",
    "set" : "Tuple",
    "Set" : "Tuple",
    "dict" : "ObjectCollection",
    "Mapping" : "ObjectCollection",
    "Dict" : "ObjectCollection",
}


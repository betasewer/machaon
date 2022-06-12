from machaon.core.symbol import (
    SIGIL_SCOPE_RESOLUTION, SIGIL_PYMODULE_DOT, SIGIL_SUBTYPE_SEPARATOR,
    BadTypename, full_qualified_name, disp_qualified_name, PythonBuiltinTypenames
)
from machaon.core.type.basic import DefaultProxy, RedirectProxy, instantiate_args, ConstructorReturnTypeError

        
#
#
#
class SubType(RedirectProxy):
    """
    サブタイプ型
    """
    def __init__(self, basetype, meta):
        super().__init__()
        self.basetype = basetype
        self.meta = meta

    def redirect(self):
        return self.basetype

    def get_typename(self):
        return self.meta.get_typename()

    def get_typedef(self):
        return self.meta.get_typedef()
        
    def get_conversion(self):
        convs = [x.get_conversion() for x in (self.basetype, self.meta)]
        return "{}:{}".format(convs[0], convs[1])
    
    def instantiate(self, context, args):
        """ 転送する """
        newmeta = self.meta.instantiate(context, args)
        return SubType(self.basetype, newmeta)

    def instantiate_params(self):
        """ 転送する """
        return self.meta.instantiate_params()
    
    def construct(self, context, value):
        """ オブジェクトを構築して値を返す """
        # 値型と同一でもコンストラクタを呼び出す
        if self.get_value_type() is not str and self.check_value_type(type(value)):
            return value 
        ret = self.constructor(context, value)
        if not self.check_value_type(type(ret)):
            raise ConstructorReturnTypeError(self, type(ret))
        return ret

    def constructor(self, context, value):
        return self.meta.constructor(context, value)

    def stringify_value(self, value):
        return self.meta.stringify_value(value)
    
    def summarize_value(self, value):
        return self.meta.summarize_value(value)

    def pprint_value(self, app, value):
        return self.meta.pprint_value(app, value)

    def reflux_value(self, value):
        return self.meta.reflux_value(value)
    
#
#
#
class ExtendedType(RedirectProxy):
    """
    インスタンス単位で型定義に変更を加える
    """
    def __init__(self, basictype, methods):
        self._basetype = basictype
        self._defdict = methods

    def get_basetype(self):
        return self._basetype

    def redirect(self):
        return self._basetype
    
    def get_typedef(self):
        return self._basetype.get_typedef()
    
    def instantiate(self, context, args):
        t = self.redirect().instantiate(context, args)
        return ExtendedType(t, self._defdict)

    def select_method(self, name):
        if name in self._defdict:
            return self._defdict[name]
        return self.redirect().select_method(name)

    def is_selectable_method(self, name):
        if name in self._defdict:
            return True
        return self.redirect().is_selectable_method(name)

    def enum_methods(self):
        for name, meth in self._defdict.items():
            yield [name], meth
        yield from self.redirect().enum_methods()
    
    
#
# 型拡張
#
def get_type_extension_loader(value):
    if isinstance(value, dict):
        if "#extend" in value:
            basic = value.pop("#extend")
            return TypeExtensionLoader(basic, value)
    return None


class TypeExtensionLoader():
    def __init__(self, basic, defdic):
        self._basic = basic
        self._def = defdic

    def get_basic(self):
        return self._basic

    def load(self, basetype):
        methods = {}
        from machaon.core.method import (
            make_method_from_value, METHOD_INVOKEAS_IMMEDIATE_VALUE,
            METHOD_FROM_USER_DEFINITION
        )
        for k, v in self._def.items():
            m = make_method_from_value(v, k, METHOD_INVOKEAS_IMMEDIATE_VALUE, METHOD_FROM_USER_DEFINITION)
            methods[m.get_name()] = m
        
        return ExtendedType(basetype, methods)



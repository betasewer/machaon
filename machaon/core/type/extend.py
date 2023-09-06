
from machaon.core.type.basic import DefaultProxy, RedirectProxy, ConstructorReturnTypeError

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



from machaon.core.symbol import (
    full_qualified_name, disp_qualified_name
)
from machaon.core.type.basic import DefaultProxy, RedirectProxy


class PythonType(DefaultProxy):
    """
    Pythonの型
    """
    def __init__(self, type, expression=None):
        self.type = type
        self.expr = expression or full_qualified_name(type)
    
    @classmethod
    def load_from_name(cls, name):
        from machaon.core.importer import attribute_loader
        loader = attribute_loader(name)
        t = loader()
        if not isinstance(t, type):
            raise TypeError("'{}'はtypeのインスタンスではありません".format(name))
        return cls(t, name)

    def get_typename(self):
        return self.expr.rpartition(".")[2] # 最下位のシンボルのみ

    def get_conversion(self):
        return self.expr
    
    def get_value_type(self):
        return self.type
    
    def get_describer(self, _mixin):
        return self.type
    
    def get_document(self):
        doc = getattr(self.type, "__doc__", None)
        return doc if doc else ""
    
    def check_type_instance(self, type):
        return isinstance(type, PythonType) and type.type is self.type
    
    def check_value_type(self, valtype):
        return issubclass(valtype, self.type)

    def instantiate(self, _context, _args):
        """ 引数は無視される """
        return PythonType(self.type, self.expr)

    def instantiate_params(self):
        """ 引数の制限なし """
        from machaon.core.method import MethodParameter
        p = MethodParameter("params", "Any")
        p.set_variable()
        return [p]

    def select_method(self, name):
        from machaon.core.method import select_method_from_type_and_instance
        meth = select_method_from_type_and_instance(self.type, self.type, name)
        return meth

    def is_selectable_method(self, name):
        from machaon.core.method import is_method_selectable_from_type_and_instance
        return is_method_selectable_from_type_and_instance(self.type, self.type, name)

    def enum_methods(self):
        from machaon.core.method import enum_methods_from_type_and_instance
        for name, meth in enum_methods_from_type_and_instance(self.type, self.type):
            yield [name], meth 

    def is_selectable_instance_method(self):
        return True 
    
    def constructor(self, _context, args, _typeargs):
        return self.type(*args)

    def stringify_value(self, value):
        tn = disp_qualified_name(type(value))
        if type(value).__repr__ is object.__repr__:
            return "<{} id={:0X}>".format(tn, id(value))
        else:
            return "{}({})".format(value, tn)
    
    def summarize_value(self, value):
        if type(value).__str__ is object.__str__:
            return "<{} object>".format(disp_qualified_name(type(value)))
        else:
            return str(value)

    def pprint_value(self, app, value):
        app.post("message", self.summarize_value(value))

    def reflux_value(self, value):
        raise ValueError("reflux実装はPythonTypeでは提供されません")



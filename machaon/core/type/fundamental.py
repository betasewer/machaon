from machaon.core.symbol import full_qualified_name
from machaon.core.type.type import Type
from machaon.core.type.basic import DefaultProxy

#
#
#
class ObjectCollectionType(Type):
    """
    ObjectCollectionを操作する型
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def spawn_getter(self, name):
        from machaon.core.method import make_method_from_value, METHOD_INVOKEAS_BOUND_FUNCTION
        return make_method_from_value(ObjectCollectionMemberGetter(name), name, METHOD_INVOKEAS_BOUND_FUNCTION)

    def select_method(self, name):
        # 型固有のメソッド
        meth = super().select_method(name)
        if meth is not None:
            return meth
        # ジェネリックメソッド
        from machaon.types.generic import resolve_generic_method
        meth = resolve_generic_method(name)
        if meth is not None:
            return meth
        # メンバセレクタ 
        meth = self.spawn_getter(name)
        return meth

    def is_selectable_method(self, name):
        return True
    

class ObjectCollectionMemberGetter:
    def __init__(self, name):
        self.name = name

    def get_action_name(self):
        return "ObjectCollectionMemberGetter<{}>".format(self.name)

    def __call__(self, collection):
        elem = collection.get(self.name)
        if elem is not None:
            return elem.object
        else:
            return None


class NoneType(DefaultProxy):
    """
    None型。インスタンス化が可能
    """
    def __init__(self):
        super().__init__()
    
    def get_typename(self):
        return "None"
    
    def get_conversion(self):
        return "None"

    def get_value_type(self):
        return type(None)
    
    def check_value_type(self, t):
        return t is type(None)

    def get_describer_qualname(self, mixin=None):
        return "None"
    
    def get_document(self):
        return "PythonのNone型。 "
    
    def select_method(self, name):
        return None

    def is_selectable_method(self, name):
        return False

    def enum_methods(self):
        return []

    def constructor(self, context, args, typeargs=None):
        """ いかなる引数もNoneに変換する """
        return None

    def stringify_value(self, _):
        return "<None>"

    # Typeのメソッド
    def get_value_type_qualname(self):
        return full_qualified_name(self.get_value_type())

    def get_describer_qualname(self, _mixin=None):
        return self.get_value_type_qualname()
    
    def get_describer(self, _mixin=None):
        return None
    
    def load_method_prototypes(self):
        pass
    
    def mixin_method_prototypes(self, describer):
        pass


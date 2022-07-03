from machaon.core.type.type import Type

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

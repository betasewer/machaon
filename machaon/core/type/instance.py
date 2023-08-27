from machaon.core.type.basic import DefaultProxy, RedirectProxy, TypeProxy

#
#
#
class TypeInstance(RedirectProxy):
    """
    引数を含むインスタンス
    """
    def __init__(self, type, args=None):
        self.type = type
        self._args = args or []

    def get_typedef(self):
        return self.type

    def redirect(self):
        return self.type
    
    def check_type_instance(self, type):
        return self.type is type

    def check_value_type(self, valtype):
        return issubclass(valtype, self.type.value_type)
    
    def instantiate(self, context, args):
        """ 引数を付け足す """
        moreargs = self.instantiate_args(context, args)
        newargs = []
        # UnspecifiedTypeParamを埋める
        i = 0
        for a in self._args:
            if a is UnspecifiedTypeParam and i < len(moreargs):
                newargs.append(moreargs[i])
                i += 1
            else:
                newargs.append(a)
        newargs.extend(moreargs[i:])

        return TypeInstance(self.type, newargs)

    def instantiate_params(self):
        """ UnspecifiedTypeParamを埋める """
        ps = self.type.instantiate_params()
        params = []
        for i, p in enumerate(ps):
            if i < len(self._args):
                if self._args[i] is UnspecifiedTypeParam:
                    params.append(p)
            else:
                params.append(p)

        if not params:
            if ps and ps[-1].is_variable():
                params.append(ps[-1])
        return params        

    def get_conversion(self):
        n = ""
        n += self.type.get_conversion()
        if self._args:
            strs = []
            for a in self._args:
                if isinstance(a, TypeProxy):
                    x = a.get_conversion()
                    if " " in x:
                        x = "({})".format(x)
                else:
                    x = str(a)
                strs.append(x)
            n += ": " + " ".join(strs)
        return n

    def constructor(self, context, args):
        return self.type.constructor(context, args, self._args)

    def stringify_value(self, value):
        return self.type.stringify_value(value, self._args)
    
    def summarize_value(self, value):
        return self.type.summarize_value(value, self._args)

    def pprint_value(self, spirit, value):
        return self.type.pprint_value(spirit, value, self._args)
    
    def get_args(self):
        return self._args

#
#
#

class TypeAny(DefaultProxy):
    """
    全ての型を受け入れる
    """
    def get_typename(self):
        return "Any"

    def get_conversion(self):
        return "Any"
    
    def get_document(self):
        return "Any type"
    
    def check_type_instance(self, _type):
        return True
    
    def check_value_type(self, valtype):
        return True

    def instantiate(self, context, args):
        raise TypeAnyInstantiateError()

    def instantiate_params(self):
        raise TypeAnyInstantiateError()

    def get_methods_bound_type(self):
        raise TypeAnyInstantiateError()

    def constructor(self, context, args, typeargs):
        raise TypeAnyInstantiateError()

    def stringify_value(self, value):
        raise TypeAnyInstantiateError()
    
    def summarize_value(self, value):
        raise TypeAnyInstantiateError()

    def pprint_value(self, app, value):
        raise TypeAnyInstantiateError()

    

class TypeAnyInstantiateError(Exception):
    def __str__(self) -> str:
        return "Any type cannot be instantiated"


class TypeUnion(DefaultProxy):
    """
    共和型
    """
    def __init__(self, types):
        self.types = types
    
    def get_typename(self):
        return "Union"
    
    def get_conversion(self):
        return "|".join([x.get_typename() for x in self.types])
    
    def get_document(self):
        return "Union type of {}".format(", ".join(["'{}'".format(x.get_typename()) for x in self.types]))
    
    def check_type_instance(self, type):
        return any(x is type for x in self.types)
    
    def check_value_type(self, valtype):
        for t in self.types:
            if t.check_value_type(valtype):
                return True
        return False

    def select_value_type(self, valtype, *, fallback=False):
        for t in self.types:
            if t.check_value_type(valtype):
                return t
        if fallback:
            return None
        raise TypeError(valtype)

    def instantiate(self, context, args):
        """ 型引数を追加する """
        moretypes = self.instantiate_args(context, args)
        return TypeUnion(self.types + moretypes)

    def instantiate_params(self):
        """ 可変長の型引数を取れる """
        from machaon.core.method import MethodParameter
        p = MethodParameter("params", "Type")
        p.set_variable()
        return [p]
    
    def constructor(self, context, args, typeargs):
        firsttype = self.types[0]
        return firsttype.constructor(context, args, typeargs)

    def stringify_value(self, value):
        t = self.select_value_type(type(value))
        return t.stringify_value(value)
    
    def summarize_value(self, value):
        t = self.select_value_type(type(value))
        return t.summarize_value(value)

    def pprint_value(self, app, value):
        t = self.select_value_type(type(value))
        return t.pprint_value(app, value)


# 型引数のデフォルト値
UnspecifiedTypeParam = TypeAny()


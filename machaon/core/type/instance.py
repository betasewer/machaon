from machaon.core.type.basic import DefaultProxy, RedirectProxy, TypeProxy, METHODS_BOUND_TYPE_TRAIT_INSTANCE

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
class UninstantiableTypeError(Exception):
    def __str__(self) -> str:
        tn = self.args[0] if self.args else '<unspecified typename>'
        return "Type '{}' cannot be instantiated".format(tn)


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
        raise UninstantiableTypeError()

    def instantiate_params(self):
        raise UninstantiableTypeError()

    def get_methods_bound_type(self):
        raise UninstantiableTypeError()

    def constructor(self, context, args, typeargs):
        raise UninstantiableTypeError()

    def stringify_value(self, value):
        raise UninstantiableTypeError()
    
    def summarize_value(self, value):
        raise UninstantiableTypeError()

    def pprint_value(self, app, value):
        raise UninstantiableTypeError()

    

class TypeUnion(DefaultProxy):
    """
    共和型
    """
    def __init__(self, types):
        super().__init__()
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


class TypeAnyObject(DefaultProxy):
    """
    全ての型を受け入れる
    インスタンス化はできないが、メソッドの参照のみなされる
    """
    def __init__(self):
        self._methods = {}

    def get_typename(self):
        return "Object"

    def get_conversion(self):
        return "Object"
    
    def get_document(self):
        return "あらゆる型のオブジェクトを受け入れる型"
    
    def check_type_instance(self, _type):
        return True
    
    def check_value_type(self, valtype):
        return True
    
    def get_describer(self, _mixin):
        return self.method_resolver.get_describer()

    #
    #
    #
    @property
    def method_resolver(self):
        from machaon.types.generic import get_resolver
        return get_resolver()

    def select_method(self, name):
        """
        ほかの型と異なり、一度に全メソッドを読み込まず、要求が来るたびに該当メソッドだけを読み込む。
        メソッドが無い場合は、GenericMethodsのメンバ名のなかから実装を探し出し、読み込みを行う。
        したがって、関数本体でのエイリアス名の指定は無効である。
        """
        fnname = self.method_resolver.resolve(name)
        if fnname is None:
            return None
        if fnname not in self._methods:
            fn = self.method_resolver.get_attribute(fnname)
            if fn is None:
                return None
            return self.load_method(fn, fnname)
        else:
            return self._methods[fnname]

    def is_selectable_method(self, name):
        return self.method_resolver.is_resolvable(name)

    def enum_methods(self):
        """ 利用可能なメソッドをすべて挙げる """
        for names, fnname, fn in self.method_resolver.enum_attributes():
            if fnname not in self._methods:
                yield names, self.load_method(fn, fnname)
            else:
                yield names, self._methods[fnname]

    def load_method(self, fn, fnname):
        """ その都度メソッド定義をロードする """
        from machaon.core.docstring import parse_doc_declaration
        from machaon.core.method import make_method_prototype_from_doc

        decl = parse_doc_declaration(fn, ("method", "task"))
        if decl is None:
            return None

        method, _aliases = make_method_prototype_from_doc(decl, fnname)
        if method is None:
            return None

        method.load_from_type(self, callobj=fn)
        self._methods[fnname] = method
        return method

    #
    #
    #
    def instantiate(self, context, args):
        raise UninstantiableTypeError()

    def instantiate_params(self):
        raise UninstantiableTypeError()

    def get_methods_bound_type(self):
        return METHODS_BOUND_TYPE_TRAIT_INSTANCE

    def constructor(self, context, args, typeargs):
        raise UninstantiableTypeError()

    def stringify_value(self, value):
        raise UninstantiableTypeError()
    
    def summarize_value(self, value):
        raise UninstantiableTypeError()

    def pprint_value(self, app, value):
        raise UninstantiableTypeError()
    

class UnresolvableType(DefaultProxy):
    """
    宣言解決時にエラーが起きた型
    """
    def __init__(self, decl, err):
        super().__init__()
        self.basic = decl
        self.error = err

    def get_typename(self):
        return "UnresolvableType[{}: {}]".format(self.basic, self.error)

    def get_conversion(self):
        return self.get_typename()

    def get_document(self):
        return "解決できなかった型'{}':\n{}".format(self.basic, self.error)
    
    def check_type_instance(self, _type):
        return False
    
    def check_value_type(self, valtype):
        return False

    def instantiate(self, context, args):
        raise UninstantiableTypeError(self.get_typename())

    def instantiate_params(self):
        raise UninstantiableTypeError(self.get_typename())

    def get_methods_bound_type(self):
        raise UninstantiableTypeError(self.get_typename())

    def constructor(self, context, args, typeargs=None):
        raise UninstantiableTypeError(self.get_typename())

    def stringify_value(self, value):
        raise UninstantiableTypeError(self.get_typename())
    
    def summarize_value(self, value):
        raise UninstantiableTypeError(self.get_typename())

    def pprint_value(self, app, value):
        raise UninstantiableTypeError(self.get_typename())
    

#
# インスタンス
#
AnyType = TypeAny()
ObjectType = TypeAnyObject()
# 型関数
UnionType = TypeUnion
# 型引数のデフォルト値
UnspecifiedTypeParam = AnyType


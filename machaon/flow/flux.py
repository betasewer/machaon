
"""
パイプで連結可能な処理のユニット。
"""
from machaon.core.function import FunctionExpression

def display_function(fn):
    if fn is None:
        return "<identity>"
    elif isinstance(fn, FunctionExpression):
        return fn.get_expression()
    else:
        return repr(fn)


class FluxFunctor():
    def display(self):
        raise NotImplementedError()

    def __repr__(self):
        return self.display()

    def __rshift__(self, right):
        return AndFlux(self, right)

    def __or__(self, right):
        if not isinstance(right, FluxFunctor):
            right = ConstFlux(right)
        return OrFlux(self, right)

    @property
    def foreach(self):
        return ListFlux(self)


class Flux(FluxFunctor):
    """ @type
    入出力のセレクタを直接指定するユニット。
    Params:
        refl(Any):
    """
    def __init__(self, infl=None, refl=None):
        self._in = infl
        if refl is None:
            self._re = infl
        else:   
            self._re = refl

    def define_influx(self, re):
        self._re = re

    def define_reflux(self, re):
        self._re = re

    def influx(self, value):
        if self._in is None:
            return value # 設定がなければスルーする
        return self._in(value)

    def reflux(self, value):
        if self._re is None:
            return value # 設定がなければスルーする
        return self._re(value)

    def influx_flow(self):
        return display_function(self._in)
        
    def reflux_flow(self):
        return display_function(self._re)
    
    def constructor(self, context, infl, refl):
        """ @meta context
        Params:
            infl(Any):    
        """
        return Flux.from_values(context, infl, refl)
        
    def display(self):
        return "<Flux\n    {}\n    {}>".format(
            display_function(self._in), 
            display_function(self._re)
        )

    @classmethod
    def from_values(cls, cxt, infl, refl):
        from machaon.core.function import  parse_sequential_function
        if not cxt.is_instance(infl, "Function"):
            infl = parse_sequential_function(infl, cxt)
        if not cxt.is_instance(refl, "Function"):
            refl = parse_sequential_function(refl, cxt)
        return cls(infl, refl)


class TypeFlux(FluxFunctor):
    """ @type
    machaonの型インターフェースを利用して変換するユニット
    """
    def __init__(self, klass=None, *, type=None, context=None):
        if type is not None:
            self._context = context
            self._type = type
        else:
            from machaon.core.type.type import Type
            self._type = Type.new(klass)
            self._context = None

    def influx(self, value):
        return self._type.construct(self._context, value)

    def reflux(self, value):
        if isinstance(value, _ConstructorArgs):
            value = value.ctor(self._type.get_value_type())
        return self._type.reflux_value(value)

    def influx_flow(self):
        return "{} construct".format(self._type.get_conversion())

    def reflux_flow(self):
        return "{} reflux".format(self._type.get_conversion())

    def display(self):
        return "<TypeFlux {}>".format(self._type.get_conversion())


class _ConstructorArgs:
    """ 引数オブジェクト """
    def __init__(self, args):
        self.args = args

    def ctor(self, value_type):
        return value_type(*self.args)


class DecomposeFlux(FluxFunctor):
    """ @type
    オブジェクトと値のリストの変換ユニット。
    """
    def __init__(self, members):
        self._members = members

    def influx(self, value):
        """ オブジェクトからリストへと分解 """
        arr = []
        for membername in self._members:
            if membername.startswith("."):
                v = getattr(value, membername[1:])
            else:
                member = getattr(value, membername)
                v = member()
            arr.append(v) # 
        return arr

    def reflux(self, value):
        """ リストからConstructTypeなどに作用する引数オブジェクトを作る """
        return _ConstructorArgs(value)

    def influx_flow(self):
        return "[{}] decompose".format(", ".join(self._members))

    def reflux_flow(self):
        return "[{}] compose".format(", ".join(self._members))

    def display(self):
        return "<DecomposeFlux [{}]>".format(", ".join(self._members))


class JsonFlux(FluxFunctor):
    """ @type
    JSON文字列とオブジェクトの変換ユニット。
    """
    def __init__(self):
        pass

    def influx(self, value):
        import json
        return json.loads(value)

    def reflux(self, value):
        import json
        return json.dumps(value, ensure_ascii=False)
        
    def influx_flow(self):
        return "json loads"
        
    def reflux_flow(self):
        return "json dumps"

    def display(self):
        return "<JsonFlux>"


class NamedFunctorFlux(FluxFunctor):
    """ 名前付きファンクタを実行する """
    def __init__(self, flow, name):
        super().__init__()
        self.flow = flow
        self.name = name

    def resolve(self):
        return self.flow.get_named_functor(self.name)

    def influx(self, value):
        return self.resolve().influx(value)

    def reflux(self, value):
        return self.resolve().reflux(value)

    def display(self):
        return self.resolve().display()


class ConstFlux(FluxFunctor):
    """ @type
    入力を無視して定数を返すユニット
    """
    def __init__(self, value):
        super().__init__()
        self.value = value
    
    def influx(self, _value):
        return self.value

    def reflux(self, _value):
        return self.value

    def influx_flow(self):
        return "<const {}>".format(self.value)
        
    def reflux_flow(self):
        return "<const {}>".format(self.value)

    def constructor(self, value):
        """ @meta """
        return ConstFlux(value)


class InletFlux(FluxFunctor):
    """ @type
    Influxの時のみ、関数を実行するユニット
    """
    def __init__(self, function) -> None:
        super().__init__()
        self.func = function

    def influx(self, value):
        return self.func(value)

    def reflux(self, value):
        return value

    def influx_flow(self):
        return display_function(self.func)
        
    def reflux_flow(self):
        return "<identity>"
        
    def display(self):
        return "<InletFlux {}>".format(display_function(self.func))

    def constructor(self, context, selector):
        """ @meta context 
        Params:
            selector(Any): 
        """
        from machaon.core.function import parse_sequential_function
        fn = parse_sequential_function(selector, context)
        return InletFlux(fn)


class OutletFlux(FluxFunctor):
    """ @type
    refluxの時のみ、関数を実行するユニット
    """
    def __init__(self, function) -> None:
        super().__init__()
        self.func = function

    def influx(self, value):
        return value

    def reflux(self, value):
        return self.func(value)

    def influx_flow(self):
        return "<identity>"

    def reflux_flow(self):
        return display_function(self.func)
    
    def display(self):
        return "<OutletFlux {}>".format(display_function(self.func))

    def constructor(self, context, selector):
        """ @meta context 
        Params:
            selector(Any): 
        """
        from machaon.core.function import parse_sequential_function
        fn = parse_sequential_function(selector, context)
        return OutletFlux(fn)

#
#
#
class ValidateFlux(FluxFunctor):
    """ @type
    値を検査し、Noneであるか条件を満たさなければ、例外を投げるユニット。
    """
    def __init__(self, c=None):
        self.cond = c

    def constructor(self, context, value):
        """ @meta context """
        if isinstance(value, str):
            if value == "exists":
                return ValidateFlux(None)
            elif value == "all-exists":
                value = "@ values= all '(@ is-none not) and (@ strip length > 0)'"
        
        from machaon.core.function import parse_sequential_function
        fn = parse_sequential_function(value, context)
        return ValidateFlux(fn)
    
    def check(self, value):
        if value is None:
            raise ValidationFail(value, self)
        if self.cond and not self.cond(value):
            raise ValidationFail(value, self)

    def influx(self, value):
        self.check(value)
        return value

    def reflux(self, value):
        self.check(value)
        return value

    def influx_flow(self):
        return "validate {}".format(self.display())

    def reflux_flow(self):
        return "validate {}".format(self.display())
    
    def display(self):
        return "<Validate {}>".format(display_function(self.cond))


class ValidationFail(Exception):
    def __str__(self):
        val = self.args[0]
        cond = self.args[1].display()
        return "値'{}'は要件にあっていません: {}".format(val, cond)


#
#
#
class NoneToValueFlux(FluxFunctor):
    """ @type
    Noneを値に変換するユニット。
    """
    def __init__(self, value):
        self.value = value

    def influx(self, value):
        if value == self.value:
            return None
        return value

    def reflux(self, value):
        if value is None:
            return self.value
        return value

    def influx_flow(self):
        return repr(self.value)
        
    def reflux_flow(self):
        return repr(self.value)
        
    def display(self):
        return "<NoneToValueFlux '{}'>".format(self.value)

    
class NoneToBlankFlux(NoneToValueFlux):
    def __init__(self):
        super().__init__("")

    def influx_flow(self):
        return "blank"
        
    def reflux_flow(self):
        return "blank"

    def display(self):
        return "<NoneToBlankFlux>"


#
#
#
class OrFlux(FluxFunctor):
    """
    複数の変換を順にためすユニット。
    """
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def influx(self, value):
        try:
            return self.left.influx(value)
        except:
            pass
        return self.right.influx(value)

    def reflux(self, value):
        try:
            return self.left.reflux(value)
        except:
            pass
        return self.right.reflux(value)
    
    def influx_flow(self):
        return self.left.influx_flow() + "|" + self.right.influx_flow()
        
    def reflux_flow(self):
        return self.left.reflux_flow() + "|" + self.right.reflux_flow()
    
    def display(self):
        return "<OrFlux: \n  {}\n  {}\n  >".format(self.left.display(), self.right.display())


class AndFlux(FluxFunctor):
    """
    変換を順に行うユニット。
    """
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def influx(self, value):
        value = self.left.influx(value)
        return self.right.influx(value)

    def reflux(self, value):
        value = self.right.reflux(value)
        return self.left.reflux(value)
    
    def influx_flow(self):
        return self.left.influx_flow() + " >> " + self.right.influx_flow()

    def reflux_flow(self):
        return self.left.reflux_flow() + " << " + self.right.reflux_flow()

    def display(self):
        return "<AndFlux: \n  {}\n  {}\n  >".format(self.left.display(), self.right.display())


class ListFlux(FluxFunctor):
    """
    各要素に対し変換を行うユニット。
    """
    def __init__(self, elem):
        self.elem = elem

    def influx(self, value):
        return [self.elem.influx(x) for x in value]

    def reflux(self, value):
        return [self.elem.reflux(x) for x in value]
    
    def influx_flow(self):
        return "[list foreach: " + self.elem.influx_flow() + "]"

    def reflux_flow(self):
        return "[list foreach: " + self.elem.reflux_flow() + "]"

    def display(self):
        return "<ListFlux:\n  {}\n  >".format(self.elem.display())






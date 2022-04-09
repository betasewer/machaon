
"""
パイプで連結可能な処理のユニット。
"""

class FluxFunctor():
    def display(self):
        raise NotImplementedError()

    def __repr__(self):
        return self.display()

class Flux(FluxFunctor):
    """ @type
    入出力のセレクタを直接指定するユニット。
    Params:
        refl(Function[](seq)):
    """
    def __init__(self, infl=None, refl=None):
        self._in = infl
        self._re = refl

    def influx(self, value):
        if self._in is None:
            return value # 設定がなければスルーする
        return self._in(value)

    def reflux(self, value):
        if self._re is None:
            return value # 設定がなければスルーする
        return self._re(value)

    def influx_flow(self):
        if self._in is None:
            return "<identity>"
        return self._in.get_expression()
        
    def reflux_flow(self):
        if self._re is None:
            return "<identity>"
        return self._re.get_expression()

    def constructor(self, infl, refl):
        """ @meta
        Params:
            infl(Function[](seq)):    
        """
        return Flux(infl, refl)
        
    def display(self):
        return "<Flux {} |<||>| {}>".format(self._in.get_expression(), self._re.get_expression())

    @classmethod
    def from_string(cls, cxt, infl, refl):
        from machaon.core.function import  parse_sequential_function
        return cls(parse_sequential_function(infl, cxt), parse_sequential_function(refl, cxt))


class TypeFlux(FluxFunctor):
    """ @type
    machaonの型インターフェースを利用して変換するユニット
    """
    def __init__(self, context, t):
        self._context = context
        self._type = t

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
                value = getattr(value, membername[1:])
            else:
                member = getattr(value, membername)
                value = member()
            arr.append(value)
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


class OrFlux(FluxFunctor):
    """ @type
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



import json

from machaon.core.message import parse_sequential_function


class ConstructType():
    """
    machaonの型インターフェースを利用して変換する。
    """
    def __init__(self, context, t):
        self._context = context
        self._type = t

    def influx(self, value):
        return self._type.construct(self._context, value)

    def reflux(self, value):
        if isinstance(value, _ConstructorArgs):
            value = value.constructor(self._type.get_value_type())
        return self._type.reflux_value(value)
    
    def influx_flow(self):
        return "{} construct".format(self._type.get_conversion())
        
    def reflux_flow(self):
        return "{} reflux".format(self._type.get_conversion())

    def __str__(self):
        return "<ConstructType {}>".format(self._type.get_conversion())


class _ConstructorArgs:
    """ 引数オブジェクト """
    def __init__(self, args):
        self.args = args

    def constructor(self, value_type):
        return value_type(*self.args)


class DecomposeToTuple():
    """
    オブジェクトをリストへと分解する。
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
        return "[{}] decompose".format(" ".join(self._members))
        
    def reflux_flow(self):
        return "[{}] compose".format(" ".join(self._members))

    def __str__(self):
        return "<DecomposeToTuple [{}]>".format(" ".join(self._members))


class LoadJson():
    """
    JSONからオブジェクトを構築する。
    """
    def __init__(self):
        pass

    def influx(self, value):
        return json.loads(value)

    def reflux(self, value):
        return json.dumps(value, ensure_ascii=False)
        
    def influx_flow(self):
        return "json loads"
        
    def reflux_flow(self):
        return "json dumps"

    def __str__(self):
        return "<LoadJson>"

class RunMessage():
    """
    任意のメッセージを実行する。
    """
    def __init__(self, fn, context=None, fn2=None):
        self._in = None
        self._re = None
        if fn is not None:
            self.set_flux(fn, "influx", context)
        if fn2 is not None:
            self.set_flux(fn2, "reflux", context)

    def set_flux(self, fn, n, context=None):
        """ 後から設定する """
        if isinstance(fn, str):
            if context is None:
                raise ValueError("No context is provided")
            fn = parse_sequential_function(fn, context)
        if n == "influx":
            self._in = fn
        elif n == "reflux":
            self._re = fn

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

    def __str__(self):
        return "<RunMessage {} |<||>| {}>".format(self._in.get_expression(), self._re.get_expression())

class NoneMapValue():
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
    
class NoneMapBlank(NoneMapValue):
    def __init__(self):
        super().__init__("")

    def influx_flow(self):
        return "blank"
        
    def reflux_flow(self):
        return "blank"


class OrFlow():
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
    
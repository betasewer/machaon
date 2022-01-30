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
        return self._type.reflux_value(value)
    
    def influx_flow(self):
        return "{} construct".format(self._type.get_conversion())
        
    def reflux_flow(self):
        return "{} reflux".format(self._type.get_conversion())


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


class RunMessage():
    """
    任意のメッセージを実行する。
    """
    def __init__(self, fn, context=None):
        self._in = None
        self._re = None
        if fn is not None:
            self.set_flux(fn, "influx", context)

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


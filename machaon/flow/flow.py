
from machaon.core.type.basic import TypeProxy
from machaon.flow.flux import (
    FluxFunctor, TypeFlux, JsonFlux, DecomposeFlux, OrFlux, NamedFunctorFlux,
    NoneToBlankFlux, NoneToValueFlux
)


class Flow:
    """ @type
    データの変換の流れを定義する。
    """
    def __init__(self):
        self.functors = []
        self.none_functor = None
        self.named_functors = {}

    def influx(self, value):
        """ @task nospirit
        入力値からデータへと変換する。
        Params:
            value(Any): 入力値
        Returns:
            Any: 最終データ
        """
        try:
            if self.none_functor and self.none_functor.influx(value) is None: # 最初に入力値をチェックする
                return None
            for i, ft in enumerate(self.functors):
                value = ft.influx(value)
        except Exception as e:
            raise FlowError(e, "influx", value, i, ft) from e
        return value
    
    def influxes(self, value):
        """ @method
        influxをジェネレータとして実行する。
        Params:
            value(Any): 入力値
        Yields:
            Any: 各ファンクタの返り値。
        """
        try:
            if self.none_functor and self.none_functor.influx(value) is None: # 最初に入力値をチェックする
                yield None
                return
            for i, ft in enumerate(self.functors):
                value = yield ft.influx(value)
        except Exception as e:
            raise FlowError(e, "influx", value, i, ft) from e
        yield value
    
    def reflux(self, value):
        """ @task nospirit
        データから入力値へと逆の変換をする。
        Params:
            value(Any): データ
        Returns:
            Any: 入力値
        """
        try:
            if value is None and self.none_functor:
                return self.none_functor.reflux(None) # 最初にデータをチェックする
            for i, ft in enumerate(reversed(self.functors)):
                i = len(self.functors)-i-1
                value = ft.reflux(value)
        except Exception as e:
            raise FlowError(e, "reflux", value, i, ft) from e
        return value

    def refluxes(self, value):
        """ @task nospirit
        refluxをジェネレータとして実行する。
        Params:
            value(Any): データ
        Yields:
            Any: 各ファンクタの返り値。
        """
        try:
            if value is None and self.none_functor:
                ret = self.none_functor.reflux(None) # 最初にデータをチェックする
                yield ret
                return
            for i, ft in enumerate(reversed(self.functors)):
                i = len(self.functors)-i-1
                value = yield ft.reflux(value)
        except Exception as e:
            raise FlowError(e, "reflux", value, i, ft) from e
        yield value

    def influx_flow(self):
        """ @method
        Returns:
            Tuple:
        """
        parts = []
        if self.none_functor:
            parts.append("[None] {}".format(self.none_functor.influx_flow()))
        for i, fn in enumerate(self.functors):
            parts.append("[{}] {}".format(i, fn.influx_flow()))
        return parts

    def reflux_flow(self):
        """ @method
        Returns:
            Tuple:
        """
        parts = []
        if self.none_functor:
            parts.append("[None] {}".format(self.none_functor.reflux_flow()))
        for i, fn in reversed(list(enumerate(self.functors))):
            parts.append("[{}] {}".format(i, fn.reflux_flow()))
        return parts

    def flow(self):
        """ @method
        Returns:
            Str:
        """
        infx = " -> ".join(self.influx_flow())
        refx = " -> ".join(self.reflux_flow())
        return "influx: {} | reflux: {}".format(infx, refx)

    #
    # ファンクタを追加する
    #
    def add_functor(self, fn):
        self.functors.append(fn)
        return self
        
    def add_named_functor(self, name):
        return self.add_functor(NamedFunctorFlux(self, name))

    def pipe(self, context, functor):
        """ @method context alias-name [>>]
        machaonの型インターフェースまたはメソッドによって変換する
        Params:
            functor(Any): 型名
        """
        if isinstance(functor, FluxFunctor):
            # 直接指定
            return self.add_functor(functor)

        elif isinstance(functor, str):
            if functor.startswith("<") and functor.endswith(">"):
                return self.add_named_functor(functor[1:-1].strip())

            elif functor == "json":
                return self.add_functor(JsonFlux())

            elif context and functor[0].isupper():
                # 型インターフェースで変換する
                typeconversion = functor
                t = context.instantiate_type(typeconversion)
                if t is None:
                    raise ValueError("型'{}'は存在しません".format(typeconversion))
                return self.add_functor(TypeFlux(type=t, context=context))

            else:
                raise ValueError("値'{}'はファンクタとして解釈できません".format(functor))

        elif context and isinstance(functor, TypeProxy):
            return self.add_functor(TypeFlux(type=functor, context=context))

        elif isinstance(functor, (list, tuple)) or (context and context.is_tuple(functor)):
            # リストとの変換
            selectors = functor
            return self.add_functor(DecomposeFlux(selectors))
        
        else:
            raise TypeError(functor)

    def pipe_or(self, context, functor):
        """ @method context alias-name [|]
        machaonの型インターフェースまたはメソッドによって変換する
        Params:
            functor(Any): 
        """
        self.pipe(context, functor)
        if len(self.functors) < 2:
            raise ValueError("Or節を作るためのユニットの数が足りません")
        functor2 = self.functors.pop()
        functor1 = self.functors.pop()
        return self.add_functor(OrFlux(functor1, functor2))
    
    def pipe_none(self, functor, arg=None):
        """ @method alias-name [none>>]
        machaonの型インターフェースまたはメソッドによってNoneを変換する
        Params:
            functor(Any): blank|zero|hyphen|value[a]
            arg?(Any): 引数
        """
        if isinstance(functor, FluxFunctor):
            # 任意のファンクタ
            self.none_functor = functor
        elif functor == "blank":
            # 空白文字に変換する
            self.none_functor = NoneToBlankFlux()
        elif functor == "zero":
            # ゼロに変換する
            self.none_functor = NoneToValueFlux(0)
        elif functor == "hyphen":
            # ゼロに変換する
            self.none_functor = NoneToValueFlux("―")
        elif functor == "value":
            # 任意の値
            self.none_functor = NoneToValueFlux(arg)
        else:
            raise ValueError(functor)
        return self

    def define_named_functor(self, name, flux):
        """ キーワードで指定できるファンクタを定義する """
        self.named_functors[name] = flux

    def get_named_functor(self, name):
        """ """
        if name not in self.named_functors:
            raise ValueError("ファンクタ名'{}'は定義されていません".format(name))
        return self.named_functors[name]
    


class FlowError(Exception):
    """ Slotのpickまたはpackで発生したエラー """
    def __init__(self, error, type, argument, funcindex, func):
        super().__init__(error, type, argument, funcindex, func)
    
    def get(self):
        error, type, argument, funcindex, func = self.args
        return error, type, argument, funcindex, func

    def __str__(self):
        error, type, argument, funcindex, func = self.args
        fun = "ファンクタ #{}: {}".format(funcindex, func)
        arg = "引数: {!r}".format(argument)
        err = "エラー: {}".format(error)
        return "\n".join([type, fun, arg, err])

    def get_error(self):
        return self.args[0]
    

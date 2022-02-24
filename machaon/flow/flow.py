


from re import A


class Flow:
    """ @type
    データの変換の流れを定義する。
    """
    def __init__(self):
        self.functors = []
        self.none_functor = None

    def influx(self, value):
        """ @task
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
    
    def reflux(self, value):
        """ @task
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

    def pipe(self, context, functor):
        """ @method context alias-name [>>]
        machaonの型インターフェースまたはメソッドによって変換する
        Params:
            functor(str): 型名
        """
        # jsonで変換する
        if functor == "json":
            from machaon.flow.functor import LoadJson
            return self.add_functor(LoadJson())

        # 型インターフェースまたはメソッドによって変換する
        typeconversion = functor
        t = context.instantiate_type(typeconversion)
        if t is None:
            raise ValueError("型'{}'は存在しません".format(typeconversion))
        if t.get_value_type() is Influx:
            msg = t.args[0] if t.args else None
            return self.pipe_message(context, msg)
        elif t.get_value_type() is Reflux:
            msg = t.args[0] if t.args else None
            return self.pipe_message(context, None).message_reflux(context, msg)
        else:
            from machaon.flow.functor import ConstructType
            return self.add_functor(ConstructType(context, t))

    def pipe_message(self, context, block):
        """ @method context alias-name [>>message >>+]
        任意のメッセージをinfluxとして設定する。
        Params:
            block(Function[](seq)):
        """
        from machaon.flow.functor import RunMessage
        return self.add_functor(RunMessage(block, context))

    def message_reflux(self, context, block):
        """ @method context [reflux+]
        任意のメッセージを直前のファンクタのrefluxとして設定する。
        Params:
            block(Function[](seq)):
        """
        from machaon.flow.functor import RunMessage
        if self.functors and isinstance(self.functors[-1], RunMessage):
            fn = self.functors[-1]
        else:
            raise ValueError("直前のファンクタがRunMessageではありません")
        fn.set_flux(block, "reflux", context)
        return self

    def pipe_none(self, context, functor, arg=None):
        """ @method context alias-name [none>>]
        machaonの型インターフェースまたはメソッドによってNoneを変換する
        Params:
            functor(str): blank|zero|hyphen|value[a]
            arg?(Any): 引数
        """
        from machaon.flow.functor import NoneMapValue, NoneMapBlank
        if functor == "blank":
            # 空白文字に変換する
            self.none_functor = NoneMapBlank()
        elif functor == "zero":
            # ゼロに変換する
            self.none_functor = NoneMapValue(0)
        elif functor == "hyphen":
            # ゼロに変換する
            self.none_functor = NoneMapValue("―")
        elif functor == "value":
            # 任意の値
            self.none_functor = NoneMapValue(arg)
        elif functor == "functor":
            # 任意の値
            self.none_functor = NoneMapValue(arg)
        else:
            raise ValueError(functor)
        return self

    #
    # 文字列
    #
    def strip(self, context, chars=None):
        """ @method context
        空白を削除する。
        Params:
            chars?(str): カスタム削除文字
        """
        from machaon.flow.functor import RunMessage
        return self.add_functor(RunMessage("@ strip", context, args=(chars,)))

    #_ Flow >> Influx(strip) >> Str:Postfix(月) >> Reflux("{02} format @") >> Int:Zen+Kan10+Kan0 >> Int:
    #_ Flow >> Flow:Json
    #_ Flow >>message "@ ..." message-reflux "@ ..." 


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

    def child_exception(self):
        return self.args[0]
    
#
# Flow.pipeで使用できるダミーの型
#
class Influx():
    """ @type
    Flowの入力処理を定義する。
    """
    pass

class Reflux():
    """ @type
    Flowの出力処理を定義する。
    """
    pass
    
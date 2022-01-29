

from machaon.core.message import parse_sequential_function


class Flow:
    """ @type
    データの変換の流れを定義する。
    """
    def __init__(self):
        self.functors = []

    def influx(self, value):
        """ @task
        入力値からデータへと変換する。
        Params:
            value(Any): 入力値
        Returns:
            Any: 最終データ
        """
        try:
            for i, ft in enumerate(self.functors):
                value = ft.influx(value)
        except Exception as e:
            raise FlowError(e, "influx", value, i, ft)
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
            for i, ft in enumerate(reversed(self.functors)):
                i = len(self.functors)-i-1
                value = ft.reflux(value)
        except Exception as e:
            raise FlowError(e, "reflux", value, i, ft)
        return value

    def influx_flow(self):
        """ @method
        Returns:
            Tuple:
        """
        parts = []
        for i, fn in enumerate(self.functors):
            parts.append("[{}] {}".format(i, fn.influx_flow()))
        return parts

    def reflux_flow(self):
        """ @method
        Returns:
            Tuple:
        """
        parts = []
        for i, fn in reversed(list(enumerate(self.functors))):
            parts.append("[{}] {}".format(i, fn.influx_flow()))
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

    def pipe(self, context, typeconversion):
        """ @method context alias-name [>>]
        machaonの型インターフェースまたはメソッドによって変換する
        Params:
            typename(str): 型名
        """
        from machaon.flow.functor import ConstructType
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
            return self.add_functor(ConstructType(context, t))

    def pipe_json(self):
        """ @method alias-name [>>json]
        JSONによって変換する。
        """
        from machaon.flow.functor import LoadJson
        return self.add_functor(LoadJson())

    def pipe_message(self, context, block):
        """ @method context alias-name [>>message]
        任意のメッセージをinfluxとして設定する。
        Params:
            block(Function[](seq)):
        """
        from machaon.flow.functor import RunMessage
        return self.add_functor(RunMessage(block, context))

    def message_reflux(self, context, block):
        """ @method context [m-reflux]
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
    
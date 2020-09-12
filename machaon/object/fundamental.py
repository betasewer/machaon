import re

from machaon.object.type import Type, TypeModule
from machaon.object.object import Object

fundamental_type = TypeModule()

#
class UnsupportedMethod(Exception):
    pass

# ----------------------------------------------------------
#
#  基本型
#
# ----------------------------------------------------------
@fundamental_type.definition(typename="Type")
class TypeType():
    """型。
    ValueType: machaon.object.type.Type
    """

    def construct(self, s):
        raise UnsupportedMethod()

    def stringify(self, v):
        raise UnsupportedMethod()

    #
    # 演算子
    #
    def new(self, type, parameter):
        '''@method [->]
        文字列からインスタンスを生成する。
        Params:
            type (Type): 型
            parameter (str...): パラメータ文字列
        Returns:
            Object: オブジェクト
        '''
        value = type.construct_from_string(parameter)
        return Object(type, value)


@fundamental_type.definition(typename="Function")
class FunctionType():
    """引数を一つとるメッセージ。
    ValueType: machaon.object.message.Function
    """

    def stringify(self, f):
        return f.get_expr()

# ----------------------------------------------------------
#
#  Pythonのビルトイン型
#
# ----------------------------------------------------------
@fundamental_type.definition(typename="Str")
class StrType():
    """Python.str
    文字列。
    ValueType: str
    """
    def construct(self, s):
        return s
    
    def stringify(self, v):
        return v

    #
    # 演算子
    #
    def regmatch(self, s, pattern):
        '''@method
        正規表現に先頭から一致するかを調べる。
        Params:
            s (str): 文字列
            pattern (str): 正規表現
        Returns:
            bool: 一致するか
        '''
        m = re.match(pattern, s)
        if m:
            return True
        return False
    
    def regsearch(self, s, pattern):
        '''@method
        正規表現にいずれかの部分が一致するかを調べる。
        Params:
            s (str): 文字列
            pattern (str): 正規表現
        Returns:
            bool: 一致するか
        '''
        m = re.search(pattern, s)
        if m:
            return True
        return False
    
    def format(self, s, *args):
        """@method
        引数から書式にしたがって文字列を作成する。
        Params:
            s (str): 文字列
            *args: 任意の引数
        Returns:
            str: 文字列
        """
        return s.format(*args)

@fundamental_type.definition(typename="Bool")
class BoolType():
    """Python.bool
    真偽値。
    ValueType: bool
    """

    def construct(self, s):
        if s == "True":
            return True
        elif s == "False":
            return False
        elif not s:
            return False
        else:
            raise ValueError(s)

@fundamental_type.definition(typename="Int")
class IntType():
    """Python.int
    整数。
    ValueType: int
    """

    def construct(self, s):
        return int(s, 0)

@fundamental_type.definition(typename="Float")
class FloatType():
    """Python.float
    浮動小数点。
    ValueType: float
    """


@fundamental_type.definition(typename="Complex")
class ComplexType():
    """Python.complex
    複素数。
    ValueType: complex
    """


# ----------------------------------------------------------
#
#  その他のデータ型
#
# ----------------------------------------------------------
@fundamental_type.definition(typename="Dataview")
class DataviewType():    
    """
    データ集合。
    ValueType: machaon.object.dataset.DataView
    """

    def construct(self, s):
        raise UnsupportedMethod()

    def stringify(self, v):
        raise UnsupportedMethod()

    def make_summary(self, view):
        itemtype = view.itemtype
        col = ", ".join([x.get_name() for x in view.get_current_columns()])
        return "{}：{}\n({})\n{}件のアイテム".format(itemtype.typename, itemtype.description, col, view.count())

@fundamental_type.definition(typename="ProcessError")
class ProcessErrorType():
    """
    プロセスで発生したエラー。
    ValueType: machaon.process.ProcessError
    """

    def construct(self, s):
        raise UnsupportedMethod()

    def stringify(self, v):
        raise UnsupportedMethod()

    def make_summary(self, error):
        excep, _ = error.get_traces()
        msg = "\n".join([error.explain_process(), error.explain_timing(), excep])
        return msg
    

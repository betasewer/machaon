import re

from machaon.object.type import TypeTraits, TypeModule

fundamental_type = TypeModule()

#
#
#
@fundamental_type.definition()
class Str(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        traits.describe(
            doc="Python.str",
            value_type=str
        )["method"](
            "regmatch",
            "regsearch",
            "format"
        )

    def construct_from_string(self, s):
        return s
    
    def stringify(self, v):
        return v

    #
    # 演算子
    #
    def regmatch(self, s, pattern):
        '''
        正規表現にマッチするかを調べる
        
        Str: 文字列
        Str: 正規表現
        ->
        Bool: マッチ成功か
        '''
        m = re.match(pattern, s)
        if m:
            return True
        return False
    
    def regsearch(self, s, pattern):
        '''
        正規表現に一部が適合するかを調べる

        Str: 文字列
        Str: 正規表現
        -> 
        Bool: 適合したか
        '''
        m = re.search(pattern, s)
        if m:
            return True
        return False
    
    def format(self, s, *args):
        """
        引数から書式にしたがって文字列を作成する

        Str: 書式
        *Any: 引数
        ->
        Str: 文字列
        """
        return s.format(*args)

#
#
#
@fundamental_type.definition()
class Bool(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        traits.describe(
            doc="True/False",
            value_type=bool
        )

    def convert_from_string(self, s):
        if s == "True":
            return True
        elif s == "False":
            return False
        elif not s:
            return False
        else:
            raise ValueError(s)

#
#
#
@fundamental_type.definition()
class Int(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        traits.describe(
            doc="整数",
            value_type=int
        )

    def convert_from_string(self, s):
        return int(s, 0)

#
#
#
@fundamental_type.definition()
class Float(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        traits.describe(
            doc="浮動小数",
            value_type=float
        )

    def convert_from_string(self, s):
        return float(s)

#
#
#
@fundamental_type.definition()
class Complex(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        traits.describe(
            doc="複素数",
            value_type=complex
        )

    def convert_from_string(self, s):
        return complex(s)

#
#
#
@fundamental_type.definition()
class DataviewType(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        from machaon.object.dataset import DataView
        traits.describe(
            typename="Dataview", 
            doc="データビュー",
            value_type=DataView
        )

    def convert_from_string(self, s):
        raise ValueError("unsupported")

    def convert_to_string(self, v):
        raise ValueError("unsupported")

    def make_summary(self, view):
        itemtype = view.itemtype
        col = ", ".join([x.get_name() for x in view.get_current_columns()])
        return "{}：{}\n({})\n{}件のアイテム".format(itemtype.typename, itemtype.description, col, view.count())

#
#
#
@fundamental_type.definition()
class ProcessErrorType(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        from machaon.process import ProcessError
        traits.describe(
            "ProcessError", 
            doc="プロセスで発生したエラー",
            value_type=ProcessError
        )

    def convert_from_string(self, s):
        raise ValueError("unsupported")

    def convert_to_string(self, v):
        raise ValueError("unsupported")

    def make_summary(self, error):
        excep, _ = error.get_traces()
        msg = "\n".join([error.explain_process(), error.explain_timing(), excep])
        return msg
    

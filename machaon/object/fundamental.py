import re

from machaon.object.type import TypeTraits, TypeModule

fundamental_type = TypeModule()

#
#
#
@fundamental_type.definition
class str_(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        traits.describe(
            typename="str",
            description="Python.str",
            value_type=str
        )["member length -> int"](
            help="文字列の長さ",
            target="len"
        )["operator regmatch -> bool"](
            help="正規表現に先頭から適合するか"
        )["operator regsearch -> bool"](
            help="正規表現に一部が適合するか"
        )

    def convert_from_string(self, s):
        return s

    #
    # 演算子
    #
    def regmatch(self, s, pattern):
        m = re.match(pattern, s)
        if m:
            return True
        return False
    
    def regsearch(self, s, pattern):
        m = re.search(pattern, s)
        if m:
            return True
        return False

#
#
#
@fundamental_type.definition
class bool_(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        traits.describe(
            "bool", 
            description="True/False",
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
@fundamental_type.definition
class int_(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        traits.describe(
            "int", 
            description="整数",
            value_type=int
        )

    def convert_from_string(self, s):
        return int(s, 0)

#
#
#
@fundamental_type.definition
class float_(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        traits.describe(
            "float", 
            description="浮動小数",
            value_type=float
        )

    def convert_from_string(self, s):
        return float(s)

#
#
#
@fundamental_type.definition
class complex_(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        traits.describe(
            "complex", 
            description="複素数",
            value_type=complex
        )

    def convert_from_string(self, s):
        return complex(s)

#
#
#
@fundamental_type.definition
class dataview_t(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        from machaon.object.dataset import DataView
        traits.describe(
            "dataview", 
            description="データビュー",
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
@fundamental_type.definition
class process_error_t(TypeTraits):
    @classmethod
    def describe_object(self, traits):
        from machaon.process import ProcessError
        traits.describe(
            "process-error", 
            description="プロセスで発生したエラー",
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
    

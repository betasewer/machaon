import re

from machaon.object.type import Type, TypeModule, TypeDelayLoader
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
@fundamental_type.definition(typename="Type", doc="""
オブジェクトの型。
""")
class TypeType():
    """@no-instance-method
    ValueType: machaon.object.type.Type
    """

    def construct(self, s):
        raise UnsupportedMethod()

    def stringify(self, v):
        raise UnsupportedMethod()

    #
    # メソッド
    #
    def new(self, type, args=()):
        '''@method
        インスタンスを生成する。
        Params:
            type (Type): 型
            args (Any): 1つか0個の引数
        Returns:
            Object: オブジェクト
        '''
        if isinstance(args, tuple) and len(args)==0:
            value = type.get_value_type()()
        else:
            value = type.get_value_type()(args)
        return Object(type, value)
        
    def new_from_string(self, type, parameter=""):
        '''@method [-> -->]
        文字列からインスタンスを生成する。
        Params:
            type (Type): 型
            parameter (str...): パラメータ文字列
        Returns:
            Object: オブジェクト
        '''
        value = type.construct_from_string(parameter)
        return Object(type, value)
    
    def methods(self, type):
        '''@method
        使用可能なメソッドを列挙する。
        Params:
            type (Type): 型
        Returns:
            str: 文字列
        '''
        lines = []
        from machaon.object.message import enum_selectable_method
        for inv, meth in enum_selectable_method(type):
            mtype, _mname, _mod = inv.display()
            msig = meth.display_signature()

            doc = meth.get_doc()
            docline = doc.splitlines()[0] if doc else ""

            lines.append("{} {}".format(mtype, msig))
            lines.append("    {}".format(docline))

        return "\n".join(lines)


@fundamental_type.definition(typename="Any", doc="""
あらゆる型を受け入れる型。
""")
class AnyType():
    """@type no-instance-method
    ValueType: machaon.Any
    """

    def construct(self, s):
        raise UnsupportedMethod()


@fundamental_type.definition(typename="Function", doc="""
一つの引数をとるメッセージ。
""")
class FunctionType():
    """@type no-instance-method    
    ValueType: machaon.object.message.Function
    """

    def stringify(self, f):
        return f.get_expr()

# ----------------------------------------------------------
#
#  Pythonのビルトイン型
#
# ----------------------------------------------------------
@fundamental_type.definition(typename="Str", doc="""
Python.str 文字列。
""")
class StrType():
    """
    ValueType: str
    """
    def construct(self, s):
        return s
    
    def stringify(self, v):
        return v

    #
    # メソッド
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

@fundamental_type.definition(typename="Bool", doc="""
Python.bool 真偽値。
""")
class BoolType():
    """
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

@fundamental_type.definition(typename="Int", doc="""
Python.int 整数。
""")
class IntType():
    """
    ValueType: int
    """

    def construct(self, s):
        return int(s, 0)

@fundamental_type.definition(typename="Float", doc="""
Python.float 小数。
""")
class FloatType():
    """
    ValueType: float
    """


@fundamental_type.definition(typename="Complex", doc="""
Python.complex 複素数。
""")
class ComplexType():
    """
    ValueType: complex
    """


# ----------------------------------------------------------
#
#  その他のデータ型
#
# ----------------------------------------------------------
@fundamental_type.definition(typename="Dataview", doc="""
データ集合型。
""")
class DataviewType():    
    """
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

@fundamental_type.definition(typename="ProcessError", doc="""
エラー型。
""")
class ProcessErrorType():
    """
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

# ----------------------------------------------------------
#
#  実行コンテキストの参照
#
# ----------------------------------------------------------
@fundamental_type.definition(typename="ThisContext", doc="""
メッセージが実行されるコンテキスト。
""")
class ThisContextType:
    """ @no-instance-method
    ValueType: machaon.object.invocation.InvocationContext
    """

    #
    # メソッド
    #
    def types(self, context):
        '''@method
        使用可能なメソッドを列挙する。
        Params:
            context (machaon.object.invocation.InvocationContext): 型
        Returns:
            str: 文字列
        '''        
        lines = []
        for t in context.type_module.enum():
            lines.append(t.typename)
            if isinstance(t, Type):
                l2 = t.doc.splitlines()[0] if t.doc else ""
            elif isinstance(t, TypeDelayLoader):
                if t.doc:
                    l2 = t.doc.splitlines()[0] if t.doc else ""
                else:
                    name = ".".join([t.traits.__module__, t.traits.__qualname__])
                    l2 = "<{}>".format(name)
            else:
                continue
            lines.append("    "+l2)
    
        return "\n".join(lines)



# Desktop new glob *.docx |> add-target Xuthus.Genko new => $genko 
# | Xuthus.GenkoProcess new indent 2 => $setting 
# | $genko process $setting 
# | $genko report $genko commonpath sameext output 
#

# Desktop new glob *.docx => $file Xuthus.Genko new => $genko
# $genko add-target $file
# $genko process
# $genko inspect


import math
import locale

#
#
# 数学型
#
#
class NumericType():   
    def abs(self, n):
        """ @method
        絶対値。
        Returns:
            Any:
        """
        return abs(n)
    
    def round(self, n, digits=None):
        """ @method
        小数を丸める。
        Arguments:
            digits(Int): 桁数
        Returns:
            Any: 丸められた小数。
        """
        return round(n, digits)

    def sqrt(self, n):
        """ @method 
        平方根を得る。
        Returns:
            Float:
        """
        return math.sqrt(n)


class IntType(NumericType):
    """ @type trait [Int]
    Pythonの整数型。
    ValueType:
        int
    """
    def constructor(self, s):
        """ @meta [from_dec_literal]
        Params:
            s(Any):
        """
        return int(s, 0)
    
    def pow(self, n, exp):
        """ @method
        べき乗を計算する。
        Params:
            exp(Int):
        Returns:
            Int:
        """
        return pow(n, exp)

    #
    #
    #
    def to(self, n, end, step=None):
        """ @method
        タプルを生成する。
        Params:
            end(Int):
            step?(Int):
        Returns:
            Tuple:
        """
        if step is not None:
            return range(n, end, step)
        else:
            return range(n, end)


class FloatType(NumericType):
    """ @type trait [Float]
    Pythonの浮動小数点型。
    ValueType:
        float
    """
    def constructor(self, s):
        """ @meta
        Params:
            Any:
        """
        return float(s)
    
    # math
    def pow(self, n, exp):
        """ @method
        べき乗を計算する。
        Params:
            exp(Float):
        Returns:
            Float:
        """
        import math
        return math.pow(n, exp)

    def floor(self, n):
        """ @method
        小数点以下を切り捨てる。
        Returns:
            Int:
        """
        import math
        return math.floor(n)
        
    def ceil(self, n):
        """ @method
        小数点以下を切り上げる。
        Returns:
            Int:
        """
        import math
        return math.ceil(n)

    def round(self, n, d=None):
        """ @method
        任意の桁数で偶数に丸める。
        Params:
            d?(int): 桁数
        Returns:
            Float
        """
        return round(n, d)

class ComplexType():
    """ @type trait [Complex]
    Pythonの複素数型。
    ValueType:
        complex
    """
    def constructor(self, s):
        """ @meta 
        Params:
            Any:
        """
        return complex(s)

    def real(self, c):
        """ @method
        実部
        Returns:
            Float:
        """
        return c.real
    
    def imag(self, c):
        """ @method
        虚部
        Returns:
            Float:
        """
        return c.imag

    def conjugate(self, c):
        """ @method
        共訳複素数を得る。
        Returns:
            Complex:
        """
        return c.conjugate()

#
#
# 外部メソッド
#
class IntRepresent:
    """ @mixin
    MixinType:
        Int:machaon.core:
    """
    #
    # N進数
    #
    def from_hex(self, value):
        """@method external
        16進数から変換する。
        Params:
            value(Str):
        """
        return int(value, 16)
    
    def hex(self, value):
        """ @method
        16進数文字に変換する。
        Returns:
            Str:
        """
        return "{:x}".format(value)
    
    def from_oct(self, value):
        """@method external
        8進数から変換する。
        Params:
            value(Str):
        """
        return int(value, 8)
    
    def oct(self, value):
        """ @method
        8進数文字に変換する。
        Returns:
            Str:
        """
        return "{:o}".format(value)
    
    def from_bin(self, value):
        """@method external
        2進数から変換する。
        Params:
            value(Str):
        """
        return int(value, 2)

    def bin(self, value):
        """ @method
        2進数文字に変換する。
        Returns:
            Str:
        """
        return "{:b}".format(value)
    
    def from_dec(self, value):
        """@method external
        緩いルールの10進数から変換する。
        Params:
            value(Str):
        """
        return int(value, 10)

    #
    # ロケール
    #
    def from_locale(self, s, localename=''):
        """ @method external
        ロケールの数値表現から変換する。
        Params:
            s(Str):
            localename?(Str): 省略でシステムロケール
        """
        locale.setlocale(locale.LC_NUMERIC, localename)
        return locale.atoi(s)
    
    def locale(self, value, localename='', nogrouping=False):
        """ @method
        ロケールの数値表現へと変換する。
        Params:
            localename?(Str): 省略でシステムロケール
            nogrouping?(bool):
        Returns:
            Str:
        """
        locale.setlocale(locale.LC_NUMERIC, localename)
        return locale.format_string("%d", value, grouping=not nogrouping)


class FloatRepresent:
    """ @mixin
    MixinType:
        Float:machaon.core:
    """
    #
    # ロケール
    #
    def from_locale(self, s, localename=''):
        """ @method external
        ロケールの数値表現を変換する。
        Params:
            s(Str):
            localename?(Str): 省略でシステムロケール
        """
        locale.setlocale(locale.LC_NUMERIC, localename)
        return locale.atof(s)
    
    def locale(self, value, localename='', nogrouping=False):
        """ @method
        ロケールの数値表現へと変換する。
        Params:
            localename?(Str): 省略でシステムロケール
            nogrouping?(bool):
        Returns:
            Str:
        """
        locale.setlocale(locale.LC_NUMERIC, localename)
        return locale.format_string("%f", value, grouping=not nogrouping)
    


# "ABC" Int:machaon.core#hex
# "ABC" Int:machaon.core>>hex
# "ABC" math#pi
# "ABC" hex->Int 




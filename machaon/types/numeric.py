import math

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
        """ @meta 
        Params:
            Any:
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
            Int:
        """
        import math
        return math.pow(n, exp)


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
# サブタイプ
#
class Hex:
    """ @type subtype
    16進数に変換する。
    BaseType:
        Int
    """
    def constructor(self, v):
        """ @meta """
        return int(v, 16)

    def stringify(self, v):
        """ @meta """
        return "{:x}".format(v)

class Oct:
    """ @type subtype
    8進数に変換する。
    BaseType:
        Int
    """
    def constructor(self, v):
        """ @meta """
        return int(v, 8)

    def stringify(self, v):
        """ @meta """
        return "{:o}".format(v)

class Bin:
    """ @type subtype
    2進数に変換する。
    BaseType:
        Int
    """
    def constructor(self, v):
        """ @meta """
        return int(v, 2)

    def stringify(self, v):
        """ @meta """
        return "{:b}".format(v)


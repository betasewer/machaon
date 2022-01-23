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
    def constructor(self, _context, s):
        """ @meta 
        Params:
            Any:
        """
        return int(s, 0)
    
    def hex(self, n):
        """ @method
        16進表記を得る。
        Returns:
            Str:
        """
        return hex(n)
    
    def oct(self, n):
        """ @method
        8進表記を得る。
        Returns:
            Str:
        """
        return oct(n)
    
    def bin(self, n):
        """ @method
        2進表記を得る。
        Returns:
            Str:
        """
        return bin(n)
    
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
    def constructor(self, _context, s):
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
    def constructor(self, _context, s):
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

    
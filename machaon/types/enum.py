



class BookFormat:
    """ type enum
    Params:
        Tuple:
    """
    def __init__(self, name, variant):
        self.name = name
        self.vari = variant

    def constructor(self, name, variant):
        """ @meta
        """
        isvari = variant == "v"
        return BookFormat(name, isvari)
    
    def stringify(self):
        """ @meta
        """
        if self.vari:
            return self.name + "判変形"
        else:
            return self.name + "判"

        



class JproFormat(BookFormat):
    """ type subtype
    BaseType:
        BookFormat
    Cases:
        B119 = 46
        B120 = 46 v
        B108 = A5
        B123 = A5 v
        B128 = 菊
        B129 = 菊 v
        B121 = A4
        B122 = A4 v
        B110 = B6
        B125 = B6 v
        B111 = A6
        B112 = B40
        B130 = B4
        B127 = B7
        B126 = AB
        BZ = []
    """
    def constructor(self, value):
        """ @meta """
        return BookFormat(*self.constructor_case(value))

    def reflux(self, fmt):
        value = self.constructor_case_inverse((fmt.name, fmt.variant))
        return value

'''
    "未刊" : "02", # 未刊
    "既刊" : "03",  # 既刊
    "刊行" : "03",  # 既刊
    "削除" : "05;削除", # 削除
'''

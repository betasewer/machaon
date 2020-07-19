import re

from machaon.object.type import TypeTraits, TypeModule

fundamental_type = TypeModule()

#
#
#
@fundamental_type.define(
    "str",
    description="文字列"
)
class str_(TypeTraits):
    value_type = str

    def convert_from_string(self, s):
        return s
        
    def convert_to_string(self, v, _spirit=None):
        return v
        
    #
    # 演算子
    #
    def operator_regmatch(self, s, pattern):
        m = re.match(pattern, s)
        if m:
            return True
        return False

#
@fundamental_type.define(
    "bool", 
    description="True/False"
)
class bool_(TypeTraits):
    value_type = bool

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
@fundamental_type.define(
    "int", 
    description="整数"
)
class int_(TypeTraits):
    value_type = int

    def convert_from_string(self, s):
        return int(s)

#
@fundamental_type.define(
    "float", 
    description="浮動小数"
)
class float_(TypeTraits):
    value_type = float

    def convert_from_string(self, s):
        return float(s)

#
@fundamental_type.define(
    "complex", 
    description="複素数"
)
class complex_(TypeTraits):
    value_type = complex

    def convert_from_string(self, s):
        return complex(s)


import os
import glob
import re

from machaon.object.type import type_traits, type_definer

#fundamental_type = type_definer()
def fundamental_type(*a, **kw):
    return lambda x:x

#
#
#
@fundamental_type(
    "str",
    description="文字列"
)
class str_(type_traits):
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
@fundamental_type(
    "bool", 
    description="True/False"
)
class bool_(type_traits):
    value_type = bool

    def convert_from_string(self, s):
        return int(s)
        

#
@fundamental_type(
    "int", 
    description="整数"
)
class int_(type_traits):
    value_type = int

    def convert_from_string(self, s):
        return int(s)

#
@fundamental_type(
    "float", 
    description="浮動小数"
)
class float_(type_traits):
    value_type = float

    def convert_from_string(self, s):
        return float(s)

#
@fundamental_type(
    "complex", 
    description="複素数"
)
class complex_(type_traits):
    value_type = complex

    def convert_from_string(self, s):
        return complex(s)
        

del fundamental_type


#
# 区切られた値のリスト
#
# machaon.object.separated_value_list(machaon.object.int_, sep=None, )
#
class separated_value_list():
    value_type = list

    def __init__(self, valuetype: type_traits=None, *, sep=None, maxsplit=-1):
        self.vtype = valuetype or str_
        self.sep = sep
        self.maxsplit = maxsplit

    def convert_from_string(self, arg):
        spl = arg.split(sep=self.sep, maxsplit=self.maxsplit)
        return [self.vtype.convert_from_string(x.strip()) for x in spl]

#
class constant_value():
    value_type = None

    def __init__(self, type):
        self.type = type

    def convert_from_string(self, arg):
        raise ValueError("Constant value cannot be parsed from another type '{}'".format(type(arg).__name__))


#
# ファイルパス
#
class filepath():
    value_type = list
    with_spirit = True

    def convert_from_string(self, arg, spirit):
        if not arg:
            return []

        # パスの羅列を区切る
        paths = []
        for fpath in arg.split(sep = "|"):
            if not fpath:
                continue
            # ホームディレクトリを展開
            fpath = os.path.expanduser(fpath)
            # 環境変数を展開
            fpath = os.path.expandvars(fpath)
            # カレントディレクトリを基準に絶対パスに直す
            fpath = spirit.abspath(fpath)
            paths.append(fpath)
        return paths
    
    def prompt(self, spirit):
        # ダイアログ
        pass

#
# 存在するファイルパス
#
class input_filepath(filepath):
    value_type = list
    with_spirit = True

    def convert_from_string(self, arg, spirit):
        # パスの羅列を区切る
        patterns = super().convert_from_string(arg, spirit)

        # ファイルパターンから対象となるすべてのファイルパスを展開する
        paths = []
        for fpath in patterns:
            expanded = glob.glob(fpath)
            if expanded:
                paths.extend(expanded)
            else:
                paths.append(fpath)
        return paths
    
    def prompt(self, spirit):
        # ダイアログ
        pass

#
#
#
class dirpath(filepath):
    def prompt(self, spirit):
        # ダイアログ
        pass

class input_dirpath(dirpath, input_filepath):
    pass

#
#
#
def define_fundamental(typelib):
    defined_type = type_definer(typelib)

    # 基本型
    defined_type(traits=str_)
    defined_type(traits=bool_)
    defined_type(traits=int_)
    defined_type(traits=float_)
    defined_type(traits=complex_)
    
    defined_type("constant", traits=constant_value, description="定数でのみ利用可能な型")

    defined_type.compound(
        name="separated-value-list", 
        description="値のリスト",
        traits=separated_value_list
    )

    defined_type.sequence(
        name="filepath",
        description="ファイルパス",
        traits=filepath
    )
    defined_type.sequence(
        name="input-filepath",
        description="存在する入力ファイルのパス",
        traits=input_filepath,
    )
    defined_type.sequence(
        name="dirpath",
        description="ディレクトリのパス",
        traits=dirpath,
    )
    defined_type.sequence(
        name="input-dirpath",
        description="存在する入力ディレクトリのパス",
        traits=input_dirpath,
    )

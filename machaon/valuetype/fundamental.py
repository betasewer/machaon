import os
import glob
import re

from machaon.valuetype.type import type_traits, type_define_decolator

#
#
#
class str_():
    value_type = str

    def convert_from_string(self, s):
        return s
        
    #
    def operator_regmatch(self, s, pattern):
        m = re.match(pattern, s)
        if m:
            return True
        return False

#
class bool_():
    value_type = int

    def convert_from_string(self, s):
        return int(s)
        

#
class int_():
    value_type = int

    def convert_from_string(self, s):
        return int(s)

#
class float_():
    value_type = float

    def convert_from_string(self, s):
        return float(s)

#
class complex_():
    value_type = complex

    def convert_from_string(self, s):
        return complex(s)
        
#
# 区切られた値のリスト
#
# machaon.valuetype.separated_value_list(machaon.valuetype.int_, sep=None, )
#
class separated_value_list():
    value_type = list

    def __init__(self, valuetype: type_traits, *, sep=None, maxsplit=-1):
        self.vtype = valuetype
        self.sep = sep
        self.maxsplit = maxsplit

    def convert_from_string(self, arg):
        spl = arg.split(implicit_sep=self.sep, maxsplit=self.maxsplit)
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
        for fpath in arg.split(explicit_sep = "|"):
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
    defined_type = type_define_decolator(typelib)

    # 基本型
    defined_type("str", traits=str_, description="文字列")
    defined_type("bool", traits=bool_, description="True/False")
    defined_type("int", traits=int_, description="整数")
    defined_type("float", traits=float_, description="小数")
    defined_type("complex", traits=complex_, description="複素数")
    
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


    
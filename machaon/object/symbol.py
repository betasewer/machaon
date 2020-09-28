
#
# 型名
#
#
python_builtin_typenames = {
    "str", "int", "bool", "float", "complex"
}

#
def normalize_typename(name: str) -> str:
    if not name[0].isupper():
        if name in python_builtin_typenames:
            name = name.capitalize() # ドキュメントとしても使うために、Pythonの組み込み型に限り小文字でも可とする
    return name.replace("_","-")
    
# 型名の間違い
class BadTypename(Exception):
    pass


#
# メソッド名
#
def normalize_method_name(name):
    return name.replace("_","-") # ハイフンはアンダースコア扱いにする

def normalize_method_target(name):
    """ メソッド名からロードする実際の関数名に戻す """
    return name.replace("-","_")

# メソッド名の間違い
class BadMethodName(Exception):
    pass
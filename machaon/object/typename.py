
# 型名の間違い
class BadTypename(Exception):
    pass


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
    

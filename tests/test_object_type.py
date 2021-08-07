import pytest
from machaon.core.type import TypeDefinition, TypeModule, TypeMemberAlias
from machaon.types.fundamental import fundamental_type

def run(fn): fn()

class SomeValue:
    """ @type alias-name [SomeAlias]
    適当な値オブジェクト
    """
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def perimeter(self):
        """ @method
        外周
        Returns:
            int: 値
        """
        return self.x * 2 + self.y * 2

# defineで登録
def test_valuetype_define():
    t = fundamental_type.define(SomeValue)
    assert t.typename == "SomeValue"
    assert t.value_type is SomeValue
    assert t.doc == "<no document>"
    assert t.is_methods_instance_bound()

# TypeDefinitionで登録
def test_valuetype_td_define():
    td = TypeDefinition(SomeValue, "SomeValue2")
    assert td.load_declaration_docstring()
    t = td.define(fundamental_type)
    assert t.typename == "SomeAlias" # 宣言が反映される
    assert t.value_type is SomeValue
    assert t.doc == "適当な値オブジェクト" # 宣言が反映される
    assert t.is_methods_instance_bound()

# 文字列で登録
def test_valuetype_td_docstring_define():
    td = TypeDefinition(SomeValue, "SomeValue")
    td.load_docstring('''@type use-instance-method alias-name [BigEntity]
    巨大なオブジェクト
    ''')
    assert td._decl.rest == "    巨大なオブジェクト"
    t = td.define(fundamental_type)
    assert t.typename == "BigEntity"
    assert t.value_type is SomeValue
    assert t.doc == "巨大なオブジェクト"
    assert t.is_methods_instance_bound()
    assert t.is_using_instance_method()

# 宣言と値がかみ合わない場合
@pytest.mark.xfail()
def test_valuetype_td_docstring_failure():
    td = TypeDefinition(SomeValue, "SomeValue")
    td.load_docstring('''@type trait
    巨大なオブジェクト
    ''') # traitだが値型を指定していない
    td.define(fundamental_type)

#
# スコープ付きの型を定義する
#
class SpecStrType:
    """
    スコープ限定のStr型。
    """
    def __init__(self, num):
        self.num = num
    
    def zeros(self):
        """ @method [0-0-0]
        発言する。
        Params:
        Returns:
            Str: 0の連続
        """
        return "0"*self.num

# defineで登録
def test_scoped_define():
    types = TypeModule()

    assert not hasattr(SpecStrType, "Type_typename")
    spec_str_t = types.define(SpecStrType, typename="Str", scope="spec")
    assert spec_str_t is not None
    assert spec_str_t.is_scope("spec")
    assert spec_str_t.typename == "Str"
    assert spec_str_t.get_value_type() is SpecStrType
    assert spec_str_t.get_describer_qualname() == "tests.test_object_type.SpecStrType"
    assert getattr(SpecStrType, "Type_typename") == "spec.Str"
    assert not spec_str_t.is_methods_type_bound()
    assert spec_str_t.is_methods_instance_bound()
    assert not spec_str_t.is_using_instance_method()

    str_t = types.define(fundamental_type.get("Str"))
    assert types.get("Str", scope="spec") is spec_str_t
    assert types.get("Str") is str_t

    # enum
    typelist = list(types.enum())
    assert len(typelist) == 2
    assert typelist[0] is spec_str_t # 追加順で取り出される
    assert typelist[1] is str_t

# 値から型を推定
def test_deduce():
    assert fundamental_type.deduce(int) is fundamental_type.get("Int")
    assert fundamental_type.deduce(str) is fundamental_type.get("Str")
    assert fundamental_type.deduce(float) is fundamental_type.get("Float")
    assert fundamental_type.deduce(complex) is fundamental_type.get("Complex")
    assert fundamental_type.deduce(bool) is fundamental_type.get("Bool")
    assert fundamental_type.deduce(ValueError) is None

    types = TypeModule()
    spec_str_t = types.define(SpecStrType, scope="spec")
    str_t = types.define(fundamental_type.get("Str"))
    assert types.deduce(str) is str_t
    assert types.deduce(SpecStrType) is spec_str_t

# defineで登録
def test_method():
    types = TypeModule()
    t = types.define(SpecStrType, scope="spec")

    t.select_method("zeros") # ロードのために必要
    m = t.get_method("zeros")
    assert m is not None
    assert m.name == "zeros"

    assert t.get_method("0-0-0") is None

    m2 = t.select_method("0-0-0")
    assert m2 is not None
    assert m2 is m

    zeros = t.delegate_method("zeros")
    assert SpecStrType.zeros is zeros


# defineで登録
def test_method_alias():
    types = TypeModule()
    t = types.define(SpecStrType, scope="spec")

    t.add_member_alias("ge_ak", "get_aknom")
    t.add_member_alias("g", "get_aknom")
    t.add_member_alias("std", ("name", "size", "attr"))
    assert t.get_member_alias("ge_ak") == "get_aknom"
    assert t.get_member_alias("std") is None
    assert t.get_member_group("std") == ["name", "size", "attr"]
    assert t.get_member_group("ge_ak") == ["get_aknom"]

    assert t.get_member_identical_names("get_aknom") == ["get_aknom", "ge_ak", "g"]
    assert t.get_member_identical_names("g") == ["get_aknom", "ge_ak", "g"]

    a = TypeMemberAlias("dest")
    assert a.get_destination() == "dest"
    assert not a.is_group_alias()
    b = TypeMemberAlias(["dest1", "dest2"])
    assert b.get_destination() == ["dest1", "dest2"]
    assert b.is_group_alias()

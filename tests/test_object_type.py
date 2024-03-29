import pytest

from machaon.core.context import instant_context
from machaon.core.type.alltype import (
    METHODS_BOUND_TYPE_INSTANCE, METHODS_BOUND_TYPE_TRAIT_INSTANCE, PythonType, parse_type_declaration,
    TypeModule, TypeMemberAlias, Type
)
from machaon.core.type.describer import TypeDescriberClass
from machaon.core.importer import attribute_loader
from machaon.types.fundamental import fundamental_types


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

class SomeTrait:
    """ @type trait [SomeValueX]
    適当な値オブジェクトの型
    ValueType:
        complex
    """
    def imag(self, cx):
        """ @method
        imag
        Returns:
            Float:
        """
        return cx.imag
        
    def real(self, cx):
        """ @method
        real
        Returns:
            Float:
        """
        return cx.real

    def constructor(self, value):
        """ @meta """
        return complex(value)


# 宣言をドキュメント文字列で登録
def test_valuetype_define():
    fundamental_type = fundamental_types()
    t = fundamental_type.define(SomeValue)
    assert t.typename == "SomeAlias" # 宣言が反映される
    assert t.value_type is SomeValue
    assert t.doc == "適当な値オブジェクト" # 宣言が反映される
    assert t.get_methods_bound_type() == METHODS_BOUND_TYPE_INSTANCE
    assert t.get_value_type() is SomeValue
    
    t = fundamental_type.define(SomeTrait)
    assert t
    assert t.typename == "SomeValueX"
    assert t.doc == "適当な値オブジェクトの型"
    assert t.get_methods_bound_type() == METHODS_BOUND_TYPE_TRAIT_INSTANCE
    assert t.get_value_type() is complex

# 宣言を直接文字列で登録
def test_valuetype_td_docstring_define():
    desc = TypeDescriberClass(SomeValue, 
        '''@type use-instance-method [BigEntity]
        巨大なオブジェクト
        '''
    )
    mod = TypeModule()
    t = mod.define(desc)
    assert t.typename == "BigEntity"
    assert t.value_type is SomeValue
    assert t.doc == "巨大なオブジェクト"
    assert t.get_methods_bound_type() == METHODS_BOUND_TYPE_INSTANCE
    assert t.is_selectable_instance_method()
    assert t.get_value_type() is SomeValue

# attribute_loaderを用いる
def test_valuetype_td_attribute_loader():
    import machaon.types.shell
    desc = TypeDescriberClass(attribute_loader("machaon.types.shell.Path"))
    mod = TypeModule()
    t = mod.define(desc, typename="Path2")
    assert t.typename == "Path2"
    assert t.value_type is machaon.types.shell.Path
    assert t.get_value_type() is machaon.types.shell.Path

# 宣言と値がかみ合わない場合
@pytest.mark.xfail()
def test_valuetype_td_docstring_failure():
    desc = TypeDescriberClass(SomeValue, 
        docstring='''@type trait
        巨大なオブジェクト
        '''
    ) # traitだが値型を指定していない
    mod = TypeModule()
    mod.define(desc)


#
# スコープ付きの型を定義する
#
class SpecStrType:
    """ @type
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

    def get_path(self):
        """ @method
        パスを返す。
        Returns:
            Any:
        """
        from machaon.types.shell import Path
        return Path("")


# defineで登録
def test_scoped_define():
    newtypes = TypeModule()

    assert not hasattr(SpecStrType, "Type_typename")
    spec_str_t = newtypes.define(SpecStrType, typename="Str")
    assert spec_str_t is not None
    assert spec_str_t.typename == "Str"
    assert spec_str_t.get_value_type() is SpecStrType
    assert getattr(SpecStrType, "Type_typename") == "Str"
    assert spec_str_t.get_methods_bound_type() == METHODS_BOUND_TYPE_INSTANCE
    assert not spec_str_t.is_selectable_instance_method()

    types = TypeModule()
    types.add_fundamentals()
    types.update(newtypes)
    str_t = types.get("Str")
    assert str_t.get_describer_qualname() == "machaon.core" # 先に定義されたものが取得される
    assert types.find("Str:tests") is spec_str_t # デスクライバを指定して取得
    assert types.find("Str") is str_t

    # enum
    typelist = list(types.getall())
    #assert len(typelist) == types.get_scope(CORE_SCOPE).count() + 1
    assert typelist[-1][1] is spec_str_t # スコープの追加順で取り出される


# 値から型を推定
def test_deduce():
    fundamental_type = fundamental_types()
    # fundamental types
    assert fundamental_type.deduce(int) is fundamental_type.get("Int")
    assert fundamental_type.deduce(str) is fundamental_type.get("Str")
    assert fundamental_type.deduce(float) is fundamental_type.get("Float")
    assert fundamental_type.deduce(complex) is fundamental_type.get("Complex")
    assert fundamental_type.deduce(bool) is fundamental_type.get("Bool")
    assert fundamental_type.deduce(ValueError) is None

    # defined type
    types = TypeModule()
    spec_str_t = types.define(SpecStrType)
    str_t = types.define(fundamental_type.get("Str"))
    assert types.deduce(str) is str_t
    assert types.deduce(SpecStrType) is spec_str_t



# defineで登録
def test_method():
    types = TypeModule()
    t = types.define(SpecStrType)

    t.select_method("zeros") # ロードのために必要
    m = t.get_method("zeros")
    assert m is not None
    assert m.name == "zeros"

    assert t.get_method("0-0-0") is None

    m2 = t.select_method("0-0-0")
    assert m2 is not None
    assert m2 is m

    zeros = t.describer.get_method_attribute("zeros")
    assert SpecStrType.zeros is zeros


# defineで登録
def test_method_alias():
    types = TypeModule()
    t = types.define(SpecStrType)

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


def test_method_return_deduce():
    cxt = instant_context()

    types = TypeModule()
    t = types.define(SpecStrType)

    m1 = t.select_method("get-path")
    assert m1.get_result().get_typedecl().instance(cxt).get_typename() == "Any"

    inv = m1.make_invocation(type=t)
    this = SpecStrType(10)
    ret = inv._prepare(cxt, this).invoke(cxt)
    #assert not isinstance(ret.type, PythonType) # 推定できる

#
# TypeModule
#
class Dummy_Rabbit():
    """ @type
    """
    describe_count = 0
    
    @classmethod
    def describe_type(cls, t):
        t.set_document("うさぎ")
        cls.describe_count += 1
    
def test_typemodule_get():
    fundamental_type = fundamental_types()
    fundamental_type.define(Dummy_Rabbit, typename="Dummy-Rabbit")
    assert fundamental_type.get("Dummy_Rabbit").typename == "Dummy-Rabbit"
    assert fundamental_type.get(Dummy_Rabbit).typename == "Dummy-Rabbit"
    assert Dummy_Rabbit.describe_count == 1
    Dummy_Rabbit.describe_count = 0

def test_typemodule_move():
    fundamental_type = fundamental_types()
    fundamental_type.define(Dummy_Rabbit, typename="Dummy-Rabbit")
    assert Dummy_Rabbit.describe_count == 1

    new_typeset = TypeModule()
    new_typeset.define(Dummy_Rabbit, typename="Second-Rabbit")

    fundamental_type.update(new_typeset)
    
    cxt = instant_context()
    cxt.type_module = fundamental_type

    assert cxt.get_type("Int").construct(cxt, "0x35") == 0x35
    assert cxt.get_type("Dummy_Rabbit") is not None
    assert cxt.get_type("Dummy_Rabbit").typename == "Dummy-Rabbit"
    assert Dummy_Rabbit.describe_count == 2 # Dummy-Rabbit, Second-Rabbitの両方で呼ばれる
    assert cxt.get_type("Second_Rabbit") is not None
    assert cxt.get_type("Second_Rabbit").typename == "Second-Rabbit"


class AryType:
    """ @type
    引数をとる型
    Params:
        T(Type):
        param1(int):
        param2(int):
    """
    def __init__(self, value, p1, p2):
        self.v = value
        self.p1 = p1
        self.p2 = p2

    def constructor(self, T, p1, p2, value):
        """ @meta 
        Params:
            Int:
        """
        return AryType(value, p1, p2)

    def stringify(self, T, p1, p2=None):
        """ @meta """
        return str([self.v, T.get_conversion(), p1, p2])

    def get(self):
        return (self.v, self.p1, self.p2)

def test_type_params():
    cxt = instant_context()
    t = cxt.type_module.define(AryType)
    
    assert len(t.get_type_params()) == 3
    assert t.get_type_params()[0].get_name() == "T"
    assert t.get_type_params()[0].is_type()
    assert t.get_type_params()[1].get_name() == "param1"
    assert t.get_type_params()[1].get_typename() == "Int"
    assert t.get_type_params()[2].get_name() == "param2"
    assert t.get_type_params()[2].get_typename() == "Int"

    decl = parse_type_declaration("AryType[Int,98,23]")
    assert len(decl.declargs) == 3

    t = decl.instance(cxt)
    assert len(t.get_args()) == 3
    assert t.get_args()[0].get_typename() == "Int"
    assert t.get_args()[1] == 98
    assert t.get_args()[2] == 23
    v = t.construct(cxt, 101)

    assert v.get() == (101, 98, 23)

    # stringify
    assert t.stringify_value(v) == str([101, "Int:machaon.core", 98, 23])

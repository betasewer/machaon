from machaon.valuetype import (
    valtype
)

#
# 引数型
#
def test_simplex_complex():
    assert valtype.str.is_simplex_type()
    assert valtype.int.is_simplex_type()
    assert valtype.bool.is_simplex_type()
    assert valtype.float.is_simplex_type()
    assert valtype.complex.is_simplex_type()

    assert not valtype.separated_value_list.is_simplex_type()
    assert valtype.separated_value_list.is_compound_type()
    assert not valtype.separated_value_list.is_sequence_type()
    
    assert not valtype.filepath.is_simplex_type()
    assert valtype.filepath.is_compound_type()
    assert valtype.filepath.is_sequence_type()


def test_separated_list():
    csv_list = valtype.separated_value_list(sep=",")
    assert csv_list.convert_from_string("neko, inu, saru, azarashi") == ["neko", "inu", "saru", "azarashi"]

    int_list = valtype.separated_value_list(valtype.int)
    assert int_list.convert_from_string("1 -2 3 -4") == [1, -2, 3, -4]

def test_filepath():
    fpath = valtype.filepath
    ifpath = valtype.input_filepath
    dpath = valtype.dirpath
    idpath = valtype.input_dirpath

    # filepath
    from machaon.process import TempSpirit
    spi = TempSpirit(cd="basic")

    assert fpath.convert_from_string("users/desktop/memo.txt bin/appli.exe", spi) == [
        "basic\\users\\desktop\\memo.txt", "basic\\bin\\appli.exe"
    ]

    # input-filepath: globパターンを受け入れ、実在するパスを集める
    spi = TempSpirit(cd = "c:\\Windows")
    assert len(ifpath.convert_from_string("System32/*.dll py.exe", spi)) > 2

    #
    spi = TempSpirit(cd="users")
    assert dpath.convert_from_string("desktop/folder bin", spi) == [
        "users\\desktop\\folder", "users\\bin"
    ]

    #
    spi = TempSpirit(cd = "c:\\Windows")
    assert len(idpath.convert_from_string("system32/* system")) > 2

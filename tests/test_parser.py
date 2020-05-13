import pytest

from machaon.parser import CommandParser, OPT_METHOD_TARGET, OPT_METHOD_EXIT, PARSE_SEP, typeof_argument, OptionContext, ArgString
from machaon.process import TempSpirit

def equal_contents(l, r):
    return set(map(frozenset, l)) == set(map(frozenset, r))

#
class option:
    def __init__(self, *args, **kwargs):
        self.a = args
        self.ka = kwargs
    
def build_parser(*options):
    p = CommandParser(description="test argparser", prog="nicht")
    for o in options:
        p.add_arg(*o.a, **o.ka)
    return p

#
# add_arg / OptionContext
#
def test_optioncontext():
    p = build_parser(
        option("target", methodtype="target"),
        option("--strict", "-s", "-!", flag=True, methodtype="exit"),
        option("--level", "-l", defarg="1", valuetype="int"),
    )

    a1 = p.positional
    assert a1.get_name() == "target"
    assert a1.is_positional()
    assert a1.get_dest_method() == OPT_METHOD_TARGET
    assert a1.get_dest() == "target"
    assert a1.get_value_typename() == "str"
    assert a1.default is None
    assert a1.make_key("-") == "target"
    assert a1.make_keys("-") == ["target"]
    assert a1.match_name("target")

    assert a1.parse_arg(ArgString(["filename"]), {}) == "filename"
    assert a1.parse_default({}) is None

    assert len(p.options) == 2

    a2 = p.options[0]
    assert a2.get_name() == "strict"
    assert a2.longnames == ["strict"]
    assert a2.shortnames == ["s", "!"]
    assert not a2.is_positional()
    assert a2.get_dest_method() == OPT_METHOD_EXIT
    assert a2.get_dest() == "strict"
    assert a2.make_key("-") == "--strict"
    assert a2.make_keys("-") == ["--strict", "-s", "-!"]
    
    assert a2.parse_arg(ArgString([]), {}) is True
    assert a2.parse_default({}) is False

    a3 = p.options[1]
    assert a3.get_name() == "level"
    assert a3.get_dest_method() == OPT_METHOD_TARGET
    assert a3.get_value_typename() == "int"
    assert a3.is_optional_unary()
    assert not a3.is_nullary() and not a3.is_unary()
    assert a3.value == "1"
    assert a3.default is None

    assert a3.parse_arg(ArgString(["10"]), {}) == 10
    assert a3.parse_arg(ArgString([]), {}) == 1
    assert a3.parse_default({}) is None

    assert list(p.argnames.keys()) == ["target", "strict", "level"]

#
def inv(fn):
    fn()

#
# パーステスト : do_parse_args
#
def test_simple_posit():
    p = build_parser(
        option("target"),
        option("--log", "-l", defarg="default.txt"),
        option("--strict", flag=True)
    )
    assert p.do_parse_args(["input.txt", "output.txt", "--strict", "-l", "log.txt"]) == {
        'target' : 'input.txt output.txt',
        'log' : 'log.txt',
        'strict' : True
    }
    assert p.do_parse_args(["input.txt", "output.txt", "-l", "--strict"]) == {
        'target' : 'input.txt output.txt',
        'log' : 'default.txt',
        'strict' : True
    }

def test_remainder():
    p = build_parser(
        option("query", remainder=True),
        option("--verbose", "-v", flag=True),
    )
    assert p.do_parse_args("select * from table --age 23".split()) == {
        'query' : 'select * from table --age 23',
        'verbose' : False
    }

def test_accumulate():
    p = build_parser(
        option("name"),
        option("--page", "-p", accumulate=True, defarg=1),
        option("--verbose", "-v", accumulate="count"),
    )
    assert p.do_parse_args(["watanabe", "mieko", "--page", "23", "--page", "3", "--page", "128", "--page"]) == {
        'name' : 'watanabe mieko',
        'page' : [23, 3, 128, 1],
        'verbose' : 0,
    }
    assert p.do_parse_args(["watanabe", "mieko", "-v", "-v", "-v"]) == {
        'name' : 'watanabe mieko',
        'page' : [],
        'verbose' : 3,
    }
    
def test_typespec():
    p = build_parser(
        option("name"),
        option("--age", "-a", valuetype=int),
        option("--offset", valuetype=int)
    )
    assert p.do_parse_args(["watanabe", "mieko", "--age", "23", "--offset", "-1"]) == {
        'name' : 'watanabe mieko',
        'age' : 23,
        'offset' : -1,
    }
    
def test_defaults(): 
    p = build_parser(
        option("name", arg="?"),
        option("--page", "-p", valuetype=int, accumulate=True),
        option("--zoo-alpha", "-za", flag=True, dest="zoo"),
        option("--zoo-omega", "-zo", const="omega", dest="zoo"), # zoのデフォルト値は無視される
        option("--depth", "-d", defarg=3, default=1, valuetype=int),
    )
    assert p.do_parse_args([""]) == {
        'name' : None,
        'page' : [],
        'zoo' : False,
        'depth' : 1
    }
    assert p.do_parse_args(["--depth"]) == {
        'name' : None,
        'page' : [],
        'zoo' : False,
        'depth' : 3
    }
    assert p.do_parse_args(["--depth", "99"]) == {
        'name' : None,
        'page' : [],
        'zoo' : False,
        'depth' : 99
    }
    
def test_dest():
    # 複数のオプションで同じdestに書き込む場合
    p = build_parser(
        option("name", arg="?"),
        option("--preset-name", "-np", dest="name", const="Mike"),
        option("--omakase-name", "-nh", dest="name", const="Kiji"),
    )
    
    # const で指定可能
    assert p.do_parse_args(["--preset-name"]) == {
        'name' : "Mike"
    }
    
    # 被った場合、コマンドの順序通りに書き込まれる
    assert p.do_parse_args(["--preset-name", "Yoshio"]) == {
        'name' : "Yoshio"
    }
    assert p.do_parse_args(["Yoshio", "--preset-name"]) == {
        'name' : "Mike"
    }
    assert p.do_parse_args(["--preset-name", "--omakase-name"]) == {
        'name' : "Kiji"
    }

#
# 位置引数の扱い
#   
def test_optional_posit():
    p = build_parser(
        option("name", arg="?"),
        option("--log", "-l", defarg="files.txt"),
        option("--strict", flag=True)
    )
    assert p.do_parse_args(["--strict", "-l", "log.txt"]) == {
        'name' : None,
        'log' : 'log.txt',
        'strict' : True
    }
    assert p.do_parse_args(["watanabe", "input.txt", "output.txt", "-l"]) == {
        'name' : 'watanabe input.txt output.txt',
        'log' : 'files.txt',
        'strict' : False
    }

@pytest.mark.xfail()
def test_posit_missing():
    p = build_parser(
        option("target"),
        option("--flag1", "-f1", flag=True),
        option("--flag2", "-f2", flag=True),
        option("--level", default=1)
    )
    assert p.do_parse_args(["-f1", "--level", "2", "bad-target"])

def test_postpositive_posit(): 
    p = build_parser(
        option("target"),
        option("--flag1", "-f1", flag=True),
        option("--flag2", "-f2", flag=True)
    )
    assert p.do_parse_args(["-f1", "-f2", "hamas"]) == {
        'flag1' : True,
        'flag2' : True,
        'target' : 'hamas'
    }

def test_explicitly_separated_posit():
    p = build_parser(
        option("target"),
        option("--flag1", "-f1", flag=True),
        option("--flag2", "-f2", flag=True),
        option("--level", valuetype=int, default=1)
    )
    assert p.do_parse_args(["-f1", PARSE_SEP, "target-name", "--level", "2"]) == {
        'flag1' : True,
        'flag2' : False,
        'level' : 2,
        'target' : 'target-name'
    }
    assert p.do_parse_args(["-f1", PARSE_SEP, "-f2", "target-name"]) == {
        'flag1' : True,
        'flag2' : True,
        'level' : 1,
        'target' : 'target-name'
    }
    
def test_no_posit():
    p = build_parser(
        option("--value", "-v"),
        option("--flag", "-f", flag=True),
        option("--level", valuetype=int, default=1)
    )
    assert p.do_parse_args(["-v", "value-name", "--level", "2"]) == {
        'value' : 'value-name',
        'level' : 2,
        'flag' : False
    }

#
# generate_parsing_candidates
#
def test_parsing_candidates():  
    p = build_parser(
        option("name"),
        option("--horizontal", "-h", flag=True),
        option("--vertical", "-v", flag=True),
        option("--alt", "-a", flag=True),
        option("--forest", "-f", flag=True),
        option("--ocean", "-o", flag=True),
        option("--heaven", "-hv", flag=True),
        option("--zoopark", "-zp", valuetype=int),
    )
    def parse_and_recompose(cmd):
        rows = []
        for cmdrow in p.generate_parsing_candidates(cmd):
            rows.append(["-"+x.shortnames[0] if not isinstance(x,str) else x for x in cmdrow])
        return rows

    # 抱合オプション
    assert parse_and_recompose(["john", "-afo"]) == [["john", "-a", "-f", "-o"]]
    assert parse_and_recompose(["-hov", "john", "-af"]) == [["-h", "-o", "-v", "john", "-a", "-f"]]
    assert equal_contents(parse_and_recompose(["john", "-hv"]), [["john", "-h", "-v"], ["john", "-hv"]])

    # 抱合オプション：引数を取るオプションの混合
    assert parse_and_recompose(["john", "-afzp", "99"]) == [["john", "-a", "-f", "-zp", "99"]]
    assert parse_and_recompose(["john", "-zpaf"]) == [["john", "-zp", "af"]]
    assert parse_and_recompose(["john", "-ozp1"]) == [["john", "-o", "-zp", "1"]]



#
# 引数型
#
def test_preset_types():
    str_, int_, bool_, float_, complex_, valuelist, filepath = [
        typeof_argument(x) for x in ("str", "int", "bool", "float", "complex", "value-list", "filepath")
    ]
    assert str_.is_simplex_type()
    assert int_.is_simplex_type()
    assert bool_.is_simplex_type()
    assert float_.is_simplex_type()
    assert complex_.is_simplex_type()

    assert not valuelist.is_simplex_type()
    assert valuelist.is_compound_type()
    assert not valuelist.is_sequence_type()
    
    assert not filepath.is_simplex_type()
    assert filepath.is_compound_type()
    assert filepath.is_sequence_type()

#
#
#
def test_listarg():
    p = build_parser(
        option("animal-names", valuetype=typeof_argument("value-list", sep=",")),
        option("--rating", "-r", valuetype="float"),
        option("--margin", "-m", valuetype=typeof_argument("value-list", "int"))
    )
    assert p.do_parse_args(["neko, inu, saru, azarashi", "-r", "1.2", "--margin", "1 -2 3 -4"]) == {
        'animal-names' : ["neko", "inu", "saru", "azarashi"],
        'rating' : 1.2,
        'margin' : [1, -2, 3, -4]
    }

#
#
#
def test_filepath():
    p = build_parser(
        option("files", valuetype="filepath"),
        option("--rating", "-r", valuetype="float"),
    )
    spirit = TempSpirit(cd="basic")
    assert p.do_parse_args(["users/desktop/memo.txt", "bin/appli.exe", "-r", "1.2"], spirit) == {
        'files' : ["basic\\users\\desktop\\memo.txt", "basic\\bin\\appli.exe"],
        'rating' : 1.2,
    }
    
#
#
#
def test_parser_result():
    p = build_parser(
        option("files", valuetype="filepath", foreach=True),
        option("--rating", "-r", valuetype="float"),
    )
    spi = TempSpirit(cd="/")
    assert list(
        p.parse_args(["users/desktop/memo.txt", "bin/appli.exe", "-r", "1.2"], spi)
        .prepare_arguments("target")
    ) == [
        { 'files' : "\\users\\desktop\\memo.txt", 'rating' : 1.2, },
        { 'files' : "\\bin\\appli.exe", 'rating' : 1.2, },
    ]

    # input-filepath: globパターンを受け入れ、実在するパスを集める
    p = build_parser(
        option("files", valuetype="input-filepath"),
        option("--margin", valuetype=typeof_argument("value-list", "int")),
    )
    spi = TempSpirit(cd = "c:\\Windows")
    assert len(list(p.parse_args(["System32/*.dll", "py.exe"], spi).prepare_arguments("target"))) > 2

    # 元のアイテムの区切り方が、空白によらず保存される
    # 型ごとにデフォルトでforeachかどうかが決まっている
    assert list(
        p.parse_args(["Program Files/folder1", "folder2", "folder3/【整理済】 原稿.docx", "--margin", "10", "20"], spi)
        .prepare_arguments("target")
    ) == [
        { 'files' : "c:\\Windows\\Program Files\\folder1", 'margin' : [10,20] },
        { 'files' : "c:\\Windows\\folder2", 'margin' : [10,20] },
        { 'files' : "c:\\Windows\\folder3\\【整理済】 原稿.docx", 'margin' : [10,20] },
    ]

    # 型のforeach設定をオーバーライド
    p = build_parser(
        option("path", valuetype="input-filepath", foreach=False),
        option("--ids", valuetype=typeof_argument("value-list", "int"), foreach=True),
    )
    assert list(
        p.parse_args(["memo.txt", "--ids", "1001", "1002", "1003"], spi)
        .prepare_arguments("target")
    ) == [
        { 'path' : "c:\\Windows\\memo.txt", 'ids' : 1001 },
        { 'path' : "c:\\Windows\\memo.txt", 'ids' : 1002 },
        { 'path' : "c:\\Windows\\memo.txt", 'ids' : 1003 },
    ]

    # デフォルトでは、位置引数にはforeachが利き、オプション引数には利かない
    p = build_parser(
        option("path", valuetype="input-filepath"), # expands foreach
        option("--out", valuetype="input-dirpath"), # as value
    )
    spi.change_current_dir("c:\\")
    assert list(
        p.parse_args(["data1.dat", "data2.dat", "data3.dat", "--out", "output.txt"], spi)
        .prepare_arguments("target")
    ) == [
        { 'path' : "c:\\data1.dat", 'out' : "c:\\output.txt" },
        { 'path' : "c:\\data2.dat", 'out' : "c:\\output.txt" },
        { 'path' : "c:\\data3.dat", 'out' : "c:\\output.txt" },
    ]

    # foreach デフォルト値のテスト
    p = build_parser(
        option("--ids", valuetype=typeof_argument("value-list", "int"), foreach=True),     # OPT_SEQUENCEFOREACH
        option("--aux", valuetype="input-filepath"),                                       # OPT_SEQUENCETOP
        option("--out", valuetype="input-filepath", default="out.txt"),                    # OPT_SEQUENCETOP
        option("--lis", valuetype=typeof_argument("value-list", "int"), default=[1,2,3]),  # OPT_SEQUENCEASVALUE
    )

    # OPT_SEQUENCEFOREACHのデフォルト値は空のシーケンスになる（全体が実行されない -> やっぱりオプションでの使用は禁じた方がよいかも...）
    assert list(
        p.parse_args(["--out", "basic/out"], spi)
        .prepare_arguments("target")
    ) == []

    # OPT_SEQUENCETOP, OPT_SEQUENCEASVALUEのデフォルト値は、add_arg.defaultに従う
    # デフォルト値は変換される
    assert list(
        p.parse_args(["--ids", "10", "20"], spi)
        .prepare_arguments("target")
    ) == [
        { 'ids' : 10, 'aux' : None, 'out' : "c:\\out.txt", 'lis' : [1,2,3]},
        { 'ids' : 20, 'aux' : None, 'out' : "c:\\out.txt", 'lis' : [1,2,3]}
    ]


import pytest

from machaon.parser import CommandParser, OPT_METHOD_TARGET, OPT_METHOD_EXIT, PARSE_SEP

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
# add_arg
#
def test_add_arg():
    p = build_parser(
        option("target", methodtype="target"),
        option("--strict", "-s", "-!", flag=True, methodtype="exit")
    )

    a1 = p.positional
    assert a1.get_name() == "target"
    assert a1.is_positional()
    assert a1.get_dest_method() == OPT_METHOD_TARGET
    assert a1.get_dest() == "target"

    assert len(p.options) == 1
    a2 = p.options[0]
    assert a2.get_name() == "strict"
    assert a2.longnames == ["strict"]
    assert a2.shortnames == ["s", "!"]
    assert not a2.is_positional()
    assert a2.get_dest_method() == OPT_METHOD_EXIT
    assert a2.get_dest() == "strict"

    assert list(p.argnames.keys()) == ["target", "strict"]

#
def inv(fn):
    fn()

#
# クエリ区切りテスト
#
def test_split_query():
    p = build_parser(
        option("target"),
        option("--query"),
        option("--output", "-o"),
    )
    # 基本
    assert p.split_query("aa bb cc dd") == ["aa", "bb", "cc", "dd"]
    assert p.split_query("file1 --query where level == 1") == ["file1", "--query", "where", "level", "==", "1"]
    # エスケープの--
    assert p.split_query("file1 --query -- where level == 1") == ["file1", "--query", "where level == 1"]
    assert p.split_query("file1 --query --") == ["file1", "--query", "--"]
    assert p.split_query("file1 --query -- --") == ["file1", "--query", "--"]
    # 改行区切り
    assert p.split_query("""file1
        query where level == 1""") == ["file1", "--query", "where level == 1"]
    assert p.split_query("""C:\\Program Files\\CompanyName\\Software\\Trojan.exe
        query where not-bad
        o C:\\apps\\security\\log.txt
        """) == [
            "C:\\Program Files\\CompanyName\\Software\\Trojan.exe",
            "--query",
            "where not-bad", 
            "-o", 
            "C:\\apps\\security\\log.txt"
        ]

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

def test_variable_posit():
    p = build_parser(
        option("name"),
        option("--log", "-l", defarg="files.txt"),
        option("--strict", flag=True)
    )
    assert p.do_parse_args(["watanabe", "input.txt", "output.txt", "-l"]) == {
        'name' : 'watanabe input.txt output.txt',
        'log' : 'files.txt',
        'strict' : False
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
    )
    assert p.do_parse_args(["watanabe", "mieko", "--page", "23", "--page", "3", "--page", "128", "--page"]) == {
        'name' : 'watanabe mieko',
        'page' : [23, 3, 128, 1]
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

#
# 位置引数の扱い
#   
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
# generate_command_rows
#
def test_compound_rows():  
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
        for cmdrow in p.generate_command_rows(cmd):
            rows.append(["-"+x.shortnames[0] if not isinstance(x,str) else x for x in cmdrow])
        return rows

    assert parse_and_recompose("john -afo") == [["john", "-a", "-f", "-o"]]
    assert parse_and_recompose("-hov john -af") == [["-h", "-o", "-v", "john", "-a", "-f"]]
    assert equal_contents(parse_and_recompose("john -hv"), [["john", "-h", "-v"], ["john", "-hv"]])
    # 引数を取るオプションの混合
    assert parse_and_recompose("john -afzp 99") == [["john", "-a", "-f", "-zp", "99"]]
    assert parse_and_recompose("john -zpaf") == [["john", "-zp", "af"]]
    assert parse_and_recompose("john -ozp1") == [["john", "-o", "-zp", "1"]]

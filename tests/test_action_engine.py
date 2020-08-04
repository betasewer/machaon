from machaon.engine import CommandEntry, CommandSet, CommandEngine, HIDDEN_COMMAND
from machaon.command import describe_command
from machaon.process import Spirit, TempSpirit
from machaon.action import Action, ActionFunction, ActionClass, ActionInvocation, ActionArgDef

from machaon.object.desktop import ObjectDesktop, Object, ObjectValue

from collections import defaultdict
import pytest

def equal_contents(l, r):
    return set(map(frozenset, l)) == set(map(frozenset, r))

#
#
# action
#
#

def test_invocation_arg():
    spi = TempSpirit()

    args = ObjectDesktop()
    args.add_fundamental_types()

    args.push("obj-1", "int", 3)
    args.push("obj-2", "int", 100)
    args.push("obj-3", "complex", 3+5j)

    inv = ActionInvocation(spi, "parameter", args)
    
    assert inv.pop_object("int").value == 100
    assert inv.pop_object("int").value == 100
    assert inv.pop_object("complex").value == 3+5j

    assert inv.pop_parameter() == "parameter"

#
#
# engine
#
#

@pytest.fixture
def a_cmdset():
    dummy_target = describe_command(lambda a,b,c: print("a={}, b={}, c={}".format(a,b,c)),
        description="Dummy Command", 
    )["target alpha"](
        help="param A",
        dest="a"
    )["target --beta -b"](
        help="param B",
        dest="b"
    )["target --cappa -c"](
        help="param C",
        dest="c"
    )["target --epsilon -e"](
        help="param B e",
        flag=True,
        dest="b"
    )["target --rho -r"](
        help="param C r",
        flag=True,
        dest="c"
    )
    entries = {
        "command" : CommandEntry(("cmd", "command"), prog="command", builder=dummy_target),
        "ending" : CommandEntry(("en", "ending"), prog="ending", builder=dummy_target),
        "commander" : CommandEntry(("commander",), prog="commander", builder=dummy_target),
        "commands" : CommandEntry(("commands",), prog="commands", builder=dummy_target),
        "commandc" : CommandEntry(("commandc",), prog="commandc", builder=dummy_target),
        "commandce" : CommandEntry(("commandce",), prog="commandce", builder=dummy_target),
    }
    cmdset = CommandSet("test", ("test","ts"), entries.values(), description="Test command set.")
    return cmdset, entries

def test_empty_cmdentry():
    entry = CommandEntry(("cmd", "command"), prog="command", description="A Command.")

    assert entry.match("cmd") == (True, "")
    assert entry.match("command") == (True, "")
    assert entry.match("ayahuasca") == (False, None)
    assert entry.match("cmdla") == (True, "la")
    
    assert entry.get_prog() == "command"
    assert entry.get_description() == "A Command."
    assert entry.get_keywords() == ("cmd", "command")
    assert not entry.is_hidden()
    
def test_built_actionfunction_cmdentry():
    entry = CommandEntry(("cmd", "command"), prog="first-prog", description="First description.", commandtype=HIDDEN_COMMAND)
    
    def funcbody(filepath, int):
        pass

    entry.builder = describe_command(
        funcbody,
        description="Described description.",
        prog="described-prog",
        hidden=False
    )["target input-filepath: filepath"](
        help="入力ファイル"
    )["target depth: int"](
        help="探索深度"
    )["yield: research-map"](
        help="調査結果"
    )
    act = entry.load_action()

    assert isinstance(act, ActionFunction)
    assert act.get_description() == "Described description."
    assert act.get_prog() == "first-prog"
    assert act.spirittype is None

    assert act.argdefs["target"][0].typename == "filepath"
    assert act.argdefs["target"][0].name == "input-filepath"
    assert act.argdefs["target"][0].help == "入力ファイル"
    assert act.argdefs["target"][1].typename == "int"
    assert act.argdefs["target"][1].name == "depth"
    assert act.argdefs["target"][1].help == "探索深度"

    assert act.resdefs[0].typename == "research-map"
    assert act.resdefs[0].help == "調査結果"

    #assert act.get_help()


def test_entryset(a_cmdset):
    cmdset, entries = a_cmdset
    
    assert len(cmdset.match("cmd")) == 1
    assert cmdset.match("cmd")[0] == (entries["command"], "")

    assert len(cmdset.match("ending")) == 1
    assert cmdset.match("ending")[0] == (entries["ending"], "")

    assert len(cmdset.match("cmdla")) == 1
    assert cmdset.match("cmdla")[0] == (entries["command"], "la")

    assert len(cmdset.match("en")) == 1
    assert cmdset.match("en")[0] == (entries["ending"], "")
    
    assert len(cmdset.match("commander")) == 2
    assert cmdset.match("commander")[0] == (entries["command"], "er")
    assert cmdset.match("commander")[1] == (entries["commander"], "")

#
# クエリ区切りテスト
#
def test_split_query():
    from machaon.engine import split_command_by_line, split_command_by_space
    # 基本
    assert split_command_by_space("aa bb cc dd") == ["aa", "bb", "cc", "dd"]
    assert split_command_by_space("file1 --query where level == 1") == ["file1", "--query", "where", "level", "==", "1"]
    # エスケープの--
    assert split_command_by_space("file1 --query -- where level == 1") == ["file1", "--query", "where level == 1"]
    assert split_command_by_space("file1 --query --") == ["file1", "--query", "--"]
    assert split_command_by_space("file1 --query -- --") == ["file1", "--query", "--"]
    # 改行区切り
    assert split_command_by_line("""
        file1
        --query
        where level == 1
        """) == ["file1", "--query", "where level == 1"]
    assert split_command_by_line("""
        C:\\Program Files\\CompanyName\\Software\\Trojan.exe
        --query 
        where not-bad
        --output
        C:\\apps\\security\\log.txt
        """) == [
            "C:\\Program Files\\CompanyName\\Software\\Trojan.exe",
            "--query",
            "where not-bad", 
            "--output", 
            "C:\\apps\\security\\log.txt"
        ]

def test_engine_cmdsetspec(a_cmdset):
    cmdset, entries = a_cmdset
    cmdset0 = CommandSet("plain", (), entries.values(), description="Test command set. no prefix")
    cmdset2 = CommandSet("beast", ("beast","be"), entries.values(), description="Test command set. beast")
    eng = CommandEngine()
    eng.add_command_set(cmdset)
    eng.add_command_set(cmdset0)
    eng.add_command_set(cmdset2)

    assert len(eng.expand_command_head("command")) == 3
    assert len(eng.expand_command_head("command::beast")) == 1
    assert len(eng.expand_command_head("command::test")) == 1
    assert len(eng.expand_command_head("command::")) == 1


#
# command split
#
def test_split_syntax():
    from machaon.engine import split_command
    def conv_(s):
        return split_command(s)
        
    assert (conv_("command file.txt --option1 --option2") 
        == ("command", ["file.txt", "--option1", "--option2"]))

    assert (conv_("command   file.txt    --option1    ") 
        == ("command", ["file.txt", "--option1"]))

    assert (conv_("""
    command
    file1.txt
    file2.txt
    --option1
    arg1
    """) 
        == ("command", ["file1.txt", "file2.txt", "--option1", "arg1"]))


# >> を使った後置記法
def test_split_postfix_syntax():
    from machaon.engine import split_command
    def conv_(s):
        return split_command(s)
    
    assert (conv_("file.txt >> command --option1 --option2") 
        == ("command", ["file.txt", "--option1", "--option2"]))
        
    # strip
    assert (conv_("  file.txt  >>   command") 
        == ("command", ["file.txt"]))
        
    assert (conv_("""
    file1.txt
    >>
    commander
    """) 
        == ("commander", ["file1.txt"]))

    assert (conv_("""
    file1.txt
    file2.txt
    file3.txt 
    >>
    command
    --option1
    arg1
    """) 
        == ("command", ["file1.txt", "file2.txt", "file3.txt", "--option1", "arg1"]))

    assert (conv_("""
    file1.txt
    file2.txt
    file3.txt 
    --files >>
    command
    target
    --option1
    """) 
        == ("command", ["--files", "file1.txt", "file2.txt", "file3.txt", "target", "--option1"]))

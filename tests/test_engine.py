from machaon.engine import CommandEntry, CommandSet, CommandEngine, CommandParserResult
from machaon.command import describe_command
from machaon.process import TempSpirit
from machaon.parser import OPT_METHOD_TARGET, PARSE_SEP

import pytest

def equal_contents(l, r):
    return set(map(frozenset, l)) == set(map(frozenset, r))

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
        "command" : CommandEntry(("cmd", "command"), prog="command", description="A Command.", builder=dummy_target),
        "ending" : CommandEntry(("en", "ending"), prog="ending", description="A Ending command.", builder=dummy_target),
        "commander" : CommandEntry(("commander",), prog="commander", description="A Commander command.", builder=dummy_target),
        "commands" : CommandEntry(("commands",), prog="commands", description="Many Commands.", builder=dummy_target),
        "commandc" : CommandEntry(("commandc",), prog="commandc", description="A Commit command.", builder=dummy_target),
        "commandce" : CommandEntry(("commandce",), prog="commandce", description="A Celurian command.", builder=dummy_target),
    }
    cmdset = CommandSet("test", ("test","ts"), entries.values(), description="Test command set.")
    return cmdset, entries

def test_entry():
    entry = CommandEntry(("cmd", "command"), prog="command", description="A Command.")
    assert entry.match("cmd") == (True, "")
    assert entry.match("command") == (True, "")
    assert entry.match("ayahuasca") == (False, None)
    assert entry.match("cmdla") == (True, "la")
    assert entry.get_prog() == "command"
    assert entry.get_description() == "A Command."

def test_entryset(a_cmdset):
    cmdset, entries = a_cmdset
    
    assert len(cmdset.match("test.cmd")) == 1
    assert cmdset.match("test.cmd")[0] == (entries["command"], "")

    assert len(cmdset.match("test.ending")) == 1
    assert cmdset.match("test.ending")[0] == (entries["ending"], "")

    assert len(cmdset.match("test.cmdla")) == 1
    assert cmdset.match("test.cmdla")[0] == (entries["command"], "la")

    assert len(cmdset.match("tsen")) == 1
    assert cmdset.match("tsen")[0] == (entries["ending"], "")
    
    assert len(cmdset.match("test.commander")) == 2
    assert cmdset.match("test.commander")[0] == (entries["command"], "er")
    assert cmdset.match("test.commander")[1] == (entries["commander"], "")

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

#
def test_engine_parsing(a_cmdset):
    cmdset, entries = a_cmdset
    eng = CommandEngine()
    eng.install_commands(cmdset)

    assert eng.expand_parsing_command_head("tscommander") == [
        (entries["command"], "er"),
        (entries["commander"], "")
    ]

    spirit = TempSpirit()
    assert [x.command_string() for x in eng.expand_parsing_command("tscommander targetname", spirit)] == [
        "commander targetname",
        "command --epsilon --rho | targetname",
    ]

    cmdrows = eng.expand_parsing_command("""
        tscommander 
        targetname
        --beta
        lao gamma
        --cappa
        iwate-no-cappa
    """, spirit)
    argparser2 = entries["command"].target.argparser
    alpha = argparser2.find_context("alpha")
    beta = argparser2.find_context("beta")
    cappa = argparser2.find_context("cappa")
    epsilon = argparser2.find_context("epsilon")
    rho = argparser2.find_context("rho")

    assert [x.command_row for x in cmdrows] == [
            ["targetname", "--beta", "lao gamma", "--cappa" ,"iwate-no-cappa"],
            [epsilon, rho, PARSE_SEP, "targetname", "--beta", "lao gamma", "--cappa", "iwate-no-cappa"],
        ]

    assert eng.parse_command(cmdrows[0]).get_values(OPT_METHOD_TARGET) == {
        "a" : "targetname",
        "b" : "lao gamma",
        "c" : "iwate-no-cappa",
    }
    
def candidate_tests(syntax_items, literals):
    if len(syntax_items) != len(literals):
        print("!not equal length:", len(syntax_items), "!=", len(literals))
        return False
    for item, lit in zip(syntax_items, literals):
        if item.command_string() != lit:
            print("!not equal:", item.command_string(), "!=", lit)
            return False
    return True

def test_candidates_engine_parsing(a_cmdset):
    cmdset, entries = a_cmdset
    eng = CommandEngine()
    eng.install_commands(cmdset)

    spirit = TempSpirit()

    # 2つ
    assert candidate_tests(
        eng.expand_parsing_command("tscommander", spirit),
        [ "commander", "command --epsilon --rho" ]
    )

    # 3つ
    assert candidate_tests(
        eng.expand_parsing_command("tscommandce", spirit),
        [ "commandce", "commandc --epsilon", "command --cappa e" ]
    )

    # 1つ: command -s は存在しないので飛ばされる
    assert candidate_tests(
        eng.expand_parsing_command("tscommands", spirit),
        [ "commands" ]
    )
    
    # 候補なし
    assert candidate_tests(
        eng.expand_parsing_command("tscommandz", spirit),
        []
    )
    assert candidate_tests(
        eng.expand_parsing_command("", spirit),
        []
    )

#
def test_postfix_syntax_engine_parsing(a_cmdset):
    cmdset, entries = a_cmdset
    eng = CommandEngine()
    eng.install_commands(cmdset)

    spirit = TempSpirit()

    assert candidate_tests(
        eng.expand_parsing_command("files.txt >> tscommand", spirit),
        ["command files.txt"]
    )
    assert candidate_tests(
        eng.expand_parsing_command("files.txt >> tscommandr -b 10", spirit),
        ["command --rho | files.txt --beta 10"]
    )
    assert candidate_tests(
        eng.expand_parsing_command("""files.txt
            >>
            tscommander
            --cappa
            20
        """, spirit),
        [
            "commander files.txt --cappa 20", 
            "command --epsilon --rho | files.txt --cappa 20"
        ]
    )

pytest.main(["-k test_split_postfix_syntax"])



from machaon.engine import CommandEntry, CommandSet, CommandEngine, CommandParserResult

def test_entry():
    entry = CommandEntry(("cmd", "command"), prog="command", description="A Command.")
    assert entry.match("cmd") == (True, "")
    assert entry.match("command") == (True, "")
    assert entry.match("ayahuasca") == (False, None)
    assert entry.match("cmdla") == (True, "la")
    assert entry.get_prog() == "command"
    assert entry.get_description() == "A Command."

def test_entryset():
    entries = {
        "command" : CommandEntry(("cmd", "command"), prog="command", description="A Command."),
        "ending" : CommandEntry(("en", "ending"), prog="ending", description="A Ending command."),
        "commander" : CommandEntry(("commander",), prog="commander", description="A Commander command."),
    }
    cmdset = CommandSet("test", ("test","ts"), entries.values(), description="Test command set.")
    
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

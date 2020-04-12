from typing import List, Sequence, Optional, Any, Tuple

from machaon.cui import fixsplit
from machaon.parser import BadCommand, display_command_row, CommandParserResult

#
# ###############################################################
#  CommandLauncher
# ###############################################################
#
normal_command = 0
auxiliary_command = 1
hidden_command = 2

COMMAND_TYPES = {
    normal_command : normal_command,
    "normal" : normal_command,
    auxiliary_command : auxiliary_command,
    "auxiliary" : auxiliary_command,
    "aux" : auxiliary_command,
    hidden_command : hidden_command,
    "hidden" : hidden_command
}

# process + command keyword
class CommandEntry():
    def __init__(
        self, 
        keywords,
        prog=None, 
        description="",
        builder=None,
        commandtype=normal_command,
    ):
        self.target = None
        self.keywords = keywords # 展開済みのキーワード
        self.builder = builder
        self.prog = prog
        self.description = description
        self.commandtype = COMMAND_TYPES.get(commandtype, normal_command)

    def load(self):
        if self.target is None and self.builder:
            self.target = self.builder.build_target(self)
        return self.target
    
    def match(self, target):
        match_rests = []
        for keyword in self.keywords:
            if target.startswith(keyword):
                match_rests.append(target[len(keyword):])
        if match_rests:
            return True, min(match_rests, key=lambda x:len(x)) # 最も長くマッチした結果を採用する
        return False, None
    
    def get_prog(self):
        return self.prog
    
    def get_keywords(self):
        return self.keywords

    def get_description(self):
        return self.description
    
    def is_hidden(self):
        return self.commandtype == hidden_command

#
# set of CommandEntry
#
class CommandSet:
    def __init__(self, name, prefixes, entries, *, description=""):
        self.name = name
        self.entries = entries
        self.prefixes = prefixes
        self.description = description
        
    def match(self, target):
        m = []
        if self.prefixes:
            hit = None
            for pfx in self.prefixes:
                if target.startswith(pfx):
                    hit = pfx
                    break
            if hit is None:
                return m
                
            target = target[len(pfx):]
            if target.startswith("."):
                target = target[1:]
        
        for e in self.entries:
            success, rest = e.match(target)
            if not success:
                continue
            m.append((e, rest))
        return m
    
    def get_name(self):
        return self.name
    
    def get_description(self):
        return self.description
    
    def get_prefixes(self):
        return self.prefixes
    
    def get_entries(self):
        return self.entries
    
    def display_entries(self, *, forcehidden=False):
        entries = []
        for x in sorted(self.entries, key=lambda x: x.commandtype):
            if not forcehidden and x.is_hidden():
                continue
            entries.append(x)
        return entries

#
# コマンド解釈の候補
#
class PossibleCommandSyntaxItem():
    def __init__(self, target, spirit, cmdrow):
        self.target = target
        self.spirit = spirit
        self.command_row = cmdrow
    
    def command_string(self):
        return (self.target.get_prog() + " " + display_command_row(self.command_row)).strip()
    
    def description(self):
        return self.target.get_description()
    
    @classmethod
    def describe(cls, cmd):
        cmd.default_columns(
            table = ("command_string", "description")
        )["command_string cmd"](
            disp="コマンド"
        )["description"](
            disp="説明"
        )

#
# 文字列から対応するコマンドを見つけ出す
#
class CommandEngine:
    def __init__(self):
        self.commandsets = []
        self.parseerror = None
        self.prefix = ""
        
    def install_commands(self, commandset):
        self.commandsets.append(commandset)
    
    def command_sets(self):
        return self.commandsets
    
    def set_command_prefix(self, prefix):
        self.prefix = prefix

    # コマンドを解析して候補を選ぶ
    def expand_parsing_command(self, commandstr, spirit) -> List[PossibleCommandSyntaxItem]:
        # コマンドを先頭の空白で区切る
        commandhead, commandtail = fixsplit(commandstr, maxsplit=1, default="")

        # 先頭文字列が示すコマンドエントリを選び出す
        possible_commands: List[Tuple[CommandEntry, str]] = [] # (entry, reststr)
        for cmdset in self.commandsets:
            matches = cmdset.match(commandhead)
            possible_commands.extend(matches)
            if self.prefix:
                matches = cmdset.match(self.prefix + commandhead)
                possible_commands.extend(matches)
        
        # オプションと引数を解析し、全ての可能なコマンド解釈を生成する
        possible_entries = []
        for commandentry, commandoption in possible_commands:
            if commandoption:
                commandtail = "-{} {}".format(commandoption, commandtail)

            target = commandentry.load()
            spirit = target.inherit_spirit(spirit)
            target.load_lazy_describer(spirit)

            argparser = target.get_argparser()
            rows = argparser.generate_command_rows(commandtail)
            for cmdrow in rows:
                entry = (target, spirit, cmdrow)
                possible_entries.append(entry)
        
        # 最も長く入力コマンドにマッチしている解釈の順に並べ直す
        possible_entries.sort(key=lambda x:len(x[2]))
        return [PossibleCommandSyntaxItem(targ, spi, cmdr) for targ, spi, cmdr in possible_entries]
        
    # ひとつを選択する
    def select_parsing_command(self, spirit, possible_entries: Sequence[PossibleCommandSyntaxItem]) -> Optional[PossibleCommandSyntaxItem]:
        if not possible_entries:
            return None
        elif len(possible_entries) > 1:
            if len(possible_entries[0].command_row()) == 0:
                # 先頭コマンド全体でマッチしているならそれを優先
                return possible_entries[0]
            # 一つ選択
            spirit.create_data(possible_entries)
            spirit.dataview()
            # 今はとりあえず先頭を採用
            return possible_entries[0]
        else:
            return possible_entries[0]

    # コマンド文字列を引数の集合に変換する
    def parse_command(self, argparser, spirit, commandrow: List[str]) -> Optional[CommandParserResult]:
        result = None
        self.parseerror = None
        
        use_dialog = False
        if commandrow and commandrow[0] == "?":
            use_dialog = True

        if not use_dialog:
            try:
                result = argparser.parse_args(commandrow)
            except BadCommand as e:
                self.parseerror = e
                use_dialog = True

            if result is None:
                use_dialog = True

        if use_dialog:
            self.prompt_command_args(argparser, spirit)
            self.parseerror = "<dialog under construction>"

        return result
    
    #
    def prompt_command_args(self, argparser, spirit):
        spirit.message("<argument fill prompt: under construction...>")
        for cxt in argparser.list_contexts():
            line = "{} [{}]  {}".format(" ".join(cxt.get_keys()), cxt.get_value_typename(), cxt.get_help())
            spirit.message(line)
        return None

    # 
    def get_last_parse_error(self):
        return self.parseerror

    #
    def test_command_head(self, commandhead):
        for cmdset in self.commandsets:
            if cmdset.match(commandhead):
                return True
        return False
        

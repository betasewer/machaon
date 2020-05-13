from typing import List, Sequence, Optional, Any, Tuple

from machaon.cui import fixsplit
from machaon.parser import BadCommand, CommandParser, CommandParserResult, PARSE_SEP, TokenRow, product_candidates
from machaon.process import ProcessTarget, Spirit

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
        keywords: Sequence[str],
        prog: Optional[str] = None, 
        description: str = "",
        builder: Any = None,
        target: Optional[ProcessTarget] = None,
        commandtype: int = normal_command,
    ):
        self.target = target
        self.keywords = keywords # 展開済みのキーワード
        self.builder = builder
        self.prog = prog
        self.description = description
        self.commandtype = COMMAND_TYPES.get(commandtype, normal_command)

    def load_target(self) -> Optional[ProcessTarget]:
        if self.target is None and self.builder:
            self.target = self.builder.build_target(self)
        return self.target
    
    def match(self, target: str) -> Tuple[bool, Optional[str]]:
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
        cmdstring = self.target.get_argparser().display_command_row(self.command_row)
        return (self.target.get_prog() + " " + cmdstring).strip()
    
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
    POSTFIX_SYNTAX_SEPARATOR = ">>"

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
    
    # 先頭文字列が示すコマンドエントリを選び出す
    def expand_parsing_command_head(self, commandhead) -> List[Tuple[CommandEntry, str]]: # [(entry, optioncompound)...]
        possible_commands: List[Tuple[CommandEntry, str]] = []
        for cmdset in self.commandsets:
            matches = cmdset.match(commandhead)
            possible_commands.extend(matches)
            if self.prefix:
                matches = cmdset.match(self.prefix + commandhead)
                possible_commands.extend(matches)
        return possible_commands

    # コマンドを解析して候補を選ぶ
    def expand_parsing_command(self, commandstr: str, spirit: Spirit) -> List[PossibleCommandSyntaxItem]:
        commandhead, commandargs = split_command(commandstr)
        
        # オプションと引数を解析し、全ての可能なコマンド解釈を生成する
        possible_commands = self.expand_parsing_command_head(commandhead) # コマンドエントリの解釈
        possible_entries: List[PossibleCommandSyntaxItem] = []
        for commandentry, optioncompound in possible_commands:
            target = commandentry.load_target()
            if target is None:
                raise ValueError("CommandEntry '{}' の構築に失敗".format(commandentry.get_prog()))

            spirit = target.inherit_spirit(spirit)
            target.load_lazy_describer(spirit)

            rows: List[TokenRow] = [] 

            argparser: CommandParser = target.get_argparser()
            tailrows = argparser.generate_parsing_candidates(commandargs)
            rows.extend(tailrows)

            if optioncompound:
                # コマンド名に抱合されたオプションを前に挿入する
                optrows = argparser.generate_parsing_candidates((optioncompound,), compound=True)
                rows = product_candidates(optrows, (PARSE_SEP,), rows)
            
            if not rows:
                rows.append([]) # 引数ゼロを示す

            for cmdrow in rows:
                entry = PossibleCommandSyntaxItem(target, spirit, cmdrow)
                possible_entries.append(entry)
        
        # 最も長く入力コマンドにマッチしている解釈の順に並べ直す
        possible_entries.sort(key=lambda x:len(x.command_row))
        return possible_entries
        
    # ひとつを選択する
    def select_parsing_command(self, spirit, possible_entries: Sequence[PossibleCommandSyntaxItem]) -> Optional[PossibleCommandSyntaxItem]:
        if not possible_entries:
            return None
        elif len(possible_entries) > 1:
            if len(possible_entries[0].command_row) == 0:
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
    def parse_command(self, item: PossibleCommandSyntaxItem) -> Optional[CommandParserResult]:
        argparser = item.target.get_argparser()
        spirit = item.spirit
        commandrow = item.command_row

        result = None
        self.parseerror = None
        
        use_dialog = False
        if commandrow and commandrow[0] == "?":
            use_dialog = True
            self.parseerror = "<dialog under construction>"

        if not use_dialog:
            try:
                result = argparser.parse_args(commandrow, spirit)
            except BadCommand as e:
                self.parseerror = e
                use_dialog = True

            if result is None:
                use_dialog = True

        if use_dialog:
            self.prompt_command_args(argparser, spirit)

        return result
    
    #
    def prompt_command_args(self, argparser, spirit):
        spirit.message("<argument fill prompt: under construction...>")
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

#
#
#
def split_command(commandstr: str) -> Tuple[str, List[str]]:
    # 複数行コマンドか
    parts: List[str] = []
    ismultiline = "\n" in commandstr
    if ismultiline:
        parts = split_command_by_line(commandstr)
    else:
        parts = split_command_by_space(commandstr)
    
    # 後置形式を通常の形式に直す
    fixed_parts = []
    for i, part in enumerate(parts):
        seppos = part.find(CommandEngine.POSTFIX_SYNTAX_SEPARATOR)
        if seppos == 0 or (seppos >= 2 and part[seppos-1].isspace()):
            fixed_parts.append(parts[i+1]) # メインコマンド

            if seppos > 1:
                pre_option_key = part[:seppos-1].strip()
                if pre_option_key:
                    fixed_parts.append(pre_option_key)
                    
            fixed_parts.extend(parts[:i])
            fixed_parts.extend(parts[i+2:])
            break
    else:
        fixed_parts = parts

    if fixed_parts:
        return fixed_parts[0], fixed_parts[1:]
    else:
        return "", []

#
def split_command_by_space(q):
    splitting = True
    parts = []
    for ch in q:
        if splitting and ch.isspace():
            if len(parts)>0:
                if parts[-1] == "--":
                    # -- によるエスケープ
                    parts[-1] = ""
                    splitting = False
                elif len(parts[-1])>0:
                    parts.append("")
        else:
            if len(parts)==0:
                parts.append("")
            parts[-1] += ch

    if parts and not parts[-1]: # 空白で終わった場合、空文字列が残る
        parts.pop(-1)

    return parts

def split_command_by_line(q):
    parts = []
    for line in q.splitlines():
        line = line.strip()
        if line:
            parts.append(line)
    return parts

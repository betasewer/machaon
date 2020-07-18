from typing import List, Sequence, Optional, Any, Tuple, Union, Dict
from collections import defaultdict

from machaon.cui import fixsplit
from machaon.action import Action, ActionClass, ActionFunction
from machaon.process import Spirit

#
# ###############################################################
#  CommandLauncher
# ###############################################################
#
NORMAL_COMMAND = 0
AUXILIARY_COMMAND = 1
HIDDEN_COMMAND = 2
COMMAND_TYPES: Dict[Union[str, int], int] = {
    "normal" : NORMAL_COMMAND,
    "auxiliary" : AUXILIARY_COMMAND,
    "aux" : AUXILIARY_COMMAND,
    "hidden" : HIDDEN_COMMAND
}

cmdsetspec_sigil = '::'

#
# process + command keyword
#
class CommandEntry():
    def __init__(
        self, 
        keywords: Sequence[str],
        prog: Optional[str] = None, 
        description: str = "",
        builder: Any = None,
        action: Optional[Action] = None,
        commandtype: Union[int, str] = NORMAL_COMMAND,
    ):
        self.action = action
        self.keywords = keywords # 展開済みのキーワード
        self.builder = builder
        self.prog = prog
        self.description = description
        self.commandtype = COMMAND_TYPES.get(commandtype, commandtype)

    def load_action(self) -> Optional[Action]:
        if self.action is None and self.builder:
            self.action = self.build_action()
        return self.action

    def build_action(self) -> Action:
        if self.builder is None:
            raise ValueError("No builder")

        prog = self.prog

        # コマンドをロードする
        target = self.builder.target
        if isinstance(target, str):
            if isinstance(self.builder.frommodule, str):
                import importlib
                mod = importlib.import_module(self.builder.frommodule)
                member = getattr(mod, target, None)
                if member is None:
                    raise ValueError("コマンド'{}'のターゲット'{}'をロードできません".format(prog, target))
                target = member
        
        # コマンド自体に定義された初期化処理があれば呼ぶ
        if hasattr(target, "describe_function"):
            target.describe_function(self.builder)
            action_type = "fn"
        elif hasattr(target, "describe_class"):
            target.describe_class(self.builder)
            action_type = "cl"
        elif isinstance(target, type):
            action_type = "cl"
        elif callable(target):
            action_type = "fn"
        else:
            raise ValueError("Invalid process action target")
        
        # description
        description = self.builder.description

        # spirit
        spirittype = self.builder.spirit
        if spirittype is None:
            spirittype = Spirit
        
        # 遅延コマンド初期化処理を実行する関数を作成する
        lazy_arg_describe = self.builder.get_lazy_action_describer()
        
        # コマンドで実行するアクション
        if action_type == "cl":
            act: Action = ActionClass(target, prog, description, spirittype=spirittype, lazyargdescribe=lazy_arg_describe)
        elif action_type == "fn":
            act = ActionFunction(target, prog, description, spirittype=spirittype, lazyargdescribe=lazy_arg_describe)

        # 引数の定義
        for cmdtype, cmdkwds, objtype, kwargs in self.builder.argument_describers():
            if cmdtype in ("target", "init", "exit"):
                act.add_argument(cmdtype, cmdkwds, objtype, kwargs)
            elif cmdtype in ("yield",):
                act.add_result(objtype, kwargs)
            else:
                raise ValueError("Undefined command type '{}'".format(cmdtype))
        
        return act
    
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
        if self.builder:
            return self.builder.description
        return self.description

    def is_hidden(self):
        return self.commandtype == HIDDEN_COMMAND

#
# set of CommandEntry
#
class CommandSet:
    def __init__(self, name, prefixes, entries, *, description=""):
        self.name = name
        self.entries = entries
        self.prefixes = prefixes
        self.description = description
        if isinstance(self.prefixes, str):
            raise TypeError("'prefixes' must be sequence of str, not str")
        
    def match(self, target, cmdsetspec=None): 
        m = []
        if cmdsetspec is not None:
            if self.prefixes:   
                if not any(cmdsetspec == x for x in self.prefixes):
                    return []
            else:
                if cmdsetspec != "": # cmdsetspec="" で名前なしのコマンドセットを指名できる
                    return []
        
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
    
    def display_commands(self, *, forcehidden=False):
        entries = []
        for x in sorted(self.entries, key=lambda x: x.commandtype):
            if not forcehidden and x.is_hidden():
                continue
            entries.append(x)
        return entries

#
#
#
class NotAvailableCommandSet():
    def __init__(self, package_name, prefixes):
        self.name = package_name
        self.prefixes = prefixes
    
    def match(self, target):
        return ()
    
    def get_name(self):
        return self.name
    
    def get_description(self):
        raise ValueError("Undefined: Not available command set")
    
    def get_prefixes(self):
        return self.prefixes
    
    def get_entries(self):
        raise ValueError("Undefined: Not available command set")
    
    def display_commands(self, *a, **kw):
        return []

#
class NotYetInstalledCommandSet(NotAvailableCommandSet):
    pass

#
class LoadFailedCommandSet(NotAvailableCommandSet):
    def __init__(self, package_name, prefixes, *, error=None):
        super().__init__(package_name, prefixes)
        self.error = "'{}' {}".format(type(error).__name__, error) or ""


#
# コマンド解釈の候補
#
class CommandExecutionEntry():
    def __init__(self, target, spirit, parameter, argsource):
        self.target = target
        self.spirit = spirit
        self.parameter = parameter
        self.argsource = argsource
    
    def command_string(self):
        return (self.target.get_prog() + " " + self.parameter).strip()
    
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
    
    def push_objects(self, objects):
        for typename, obj in objects:
            self.objstack[typename].append(obj)
    
    def add_command_set(self, commandset) -> int:
        self.commandsets.append(commandset)
        return len(self.commandsets)-1
    
    def get_command_set(self, index):
        return self.commandsets[index]
    
    def replace_command_set(self, index, cmdset):
        self.commandsets[index] = cmdset
    
    def command_sets(self):
        return self.commandsets
    
    # 先頭文字列が示すコマンドエントリを選び出す
    def expand_command_head(self, commandhead) -> List[Tuple[CommandEntry, str]]: # [(entry, optioncompound)...]
        possible_commands: List[Tuple[CommandEntry, str]] = []

        cmdtarget = commandhead
        cmdsetspec = None
        if cmdsetspec_sigil in commandhead:
            cmdtarget, _, cmdsetspec = [x.strip() for x in commandhead.partition(cmdsetspec_sigil)]

        for cmdset in self.commandsets:
            matches = cmdset.match(cmdtarget, cmdsetspec)
            possible_commands.extend(matches)
        return possible_commands

    # コマンドを解析して実行エントリの候補を生成する
    def parse_command(self, commandstr: str, spirit: Spirit) -> List[CommandExecutionEntry]:
        commandhead, commandargs = split_command(commandstr)

        # 引数を生成するコマンドか
        yieldargname = None
        if "." in commandhead:
            commandhead, yieldargname = commandhead.split(".", maxsplit=1)
        
        # オプションと引数を解析し、全ての可能なコマンド解釈を生成する
        possible_commands = self.expand_command_head(commandhead) # コマンドエントリの解釈
        possible_entries: List[CommandExecutionEntry] = []
        for commandentry, optioncompound in possible_commands:
            action = commandentry.load_action()
            if action is None:
                raise ValueError("CommandEntry '{}' の構築に失敗".format(commandentry.get_prog()))

            spirit = action.inherit_spirit(spirit)
            action.load_lazy_describer(spirit)

            # 引数生成アクションであるなら、さらに生成する
            if yieldargname:
                argdef = action.find_argument(yieldargname)
                if argdef is None:
                    raise ValueError("コマンド'{}'の引数ではありません: {}".format(commandentry.get_prog(), yieldargname))
                action = self.objectdesk.create_yield_action(argdef.get_typename())
                if action is None:
                    raise ValueError("Fail to create")

            # 引数をまとめる
            parameter = " ".join([x for x in (optioncompound, *commandargs) if x])
            argsources = self.objectdesk.stack
            entry = CommandExecutionEntry(action, spirit, parameter, argsources)

            possible_entries.append(entry)
        
        return possible_entries
        
    # 候補からひとつを選択する
    def select_command_entry(self, spirit, possible_entries: Sequence[CommandExecutionEntry]) -> Optional[CommandExecutionEntry]:
        if not possible_entries:
            return None
        elif len(possible_entries) > 1:
            # 一つ選択
            spirit.create_data(possible_entries)
            spirit.dataview()
            # 今はとりあえず先頭を採用
            return possible_entries[0]
        else:
            return possible_entries[0]
    
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

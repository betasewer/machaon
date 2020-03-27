#!/usr/bin/env python3
# coding: utf-8
import argparse
import glob
from collections import defaultdict  
from itertools import product
from typing import Sequence
    
#
# ########################################################
#  Command Parser
# ########################################################
#
InitArg = 0
TargetArg = 1
ExitArg = 2
PositTargetArg = 5 # 1+4
FilepathArg = 0x10
JoinListArg = 0x20
ColorCodeArg = 0x100

#
SpecArgSig = "?"
    
#
# argparseを継承しいくつかの挙動を書き換えている。
#
class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        self.parent = kwargs.pop("parentparser")
        super().__init__(*args, **kwargs)
        
    def exit(self, status=0, message=None):
        raise ArgumentParserExit(status, message)

    def error(self, message):
        raise BadCommand(message)
        
    def print_usage(self, file=None):
        self.parent.push_parser_message(self.format_usage())
    
    def print_help(self, file=None):
        self.parent.push_parser_message(self.format_help())
        
#
class ArgumentParserExit(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message

#
class BadCommand(Exception):
    def __init__(self, error):
        self.error = error
       
#
# argparseをラップする
#
class CommandParser():
    __debugdisp__ = False
    #
    # __init__(["targets"], ("--template","-t"), ...)
    #
    def __init__(self, **kwargs):
        kwargs["parentparser"] = self
        self.argp = ArgumentParser(**kwargs)
        self.argnames = []
        self._parsermsgs = None
        self._compoptions = CompoundOptions()
        self._compoptions.add_option("h")
        self.enable_compound_options = True
        self.sole_positional = None
       
    # argparse.add_argumentの引数に加え、以下を指定可能：
    #  files = True/False : ファイルパス/globパターンを受け入れ、ファイルパスのリストに展開する
    #  const_option = Object : action=store_const + const=Object
    #  append_const_option = Object : action=append_const + const=Object
    #  take_remainder : nargs=argparse.REMAINDER
    def add_arg(self, argtype, *names, **kwargs):
        if not names:
            raise ValueError("option names must be specified")

        isfile = kwargs.pop("files", False)
        if isfile:
            kwargs["nargs"] = "+"
            argtype |= FilepathArg
        
        cstopt = kwargs.pop("const_option", None)
        if cstopt is not None:
            kwargs["action"] = "store_const"
            kwargs["const"] = cstopt
        
        apcstopt = kwargs.pop("append_const_option", None)
        if apcstopt is not None:
            kwargs["action"] = "append_const"
            kwargs["const"] = apcstopt
        
        remopt = kwargs.pop("take_remainder", False)
        if remopt:
            kwargs["nargs"] = argparse.REMAINDER
            argtype |= JoinListArg

        act = self.argp.add_argument(*names, **kwargs)
        if not any(x for (_,x) in self.argnames if x == act.dest):
            self.argnames.append((argtype, act.dest))

        # sole positional argument will be handled specially
        if not names[0].startswith("-"):
            if self.sole_positional:
                self.sole_positional = False
            elif self.sole_positional is None:
                self.sole_positional = act.dest
        #    self.argnames.append((methodtype|PositTargetArg, act.dest))

        # trie
        for name in names:
            if name.startswith("--"):
                pass
            elif name.startswith("-"):
                self._compoptions.add_option(name[1:])
        
    def init_arg(self, *args, **kwargs):
        self.add_arg(InitArg, *args, **kwargs)
        
    def target_arg(self, *args, **kwargs):
        self.add_arg(TargetArg, *args, **kwargs)
    
    def exit_arg(self, *args, **kwargs):
        self.add_arg(ExitArg, *args, **kwargs)
    
    # 引数解析
    def split_singleline_query(self, q):
        splitting = True
        parts = []
        for ch in q:
            # -- によるエスケープ
            if splitting and ch.isspace():
                if len(parts)>0:
                    if parts[-1] == "--":
                        parts[-1] = ""
                        splitting = False
                    elif len(parts[-1])>0:
                        parts.append("")
            else:
                if len(parts)==0:
                    parts.append("")
                parts[-1] += ch
        return parts
    
    def split_multiline_query(self, qs):
        parts = []
        for q in qs:
            if q.startswith("-"): # オプションで開始する行は通常通り空白で区切る
                parts.extend(self.split_singleline_query(q))
            else:
                parts.append(q.strip()) # 行の内部では区切らない
        return parts
    
    def split_query(self, q):
        if "\n" in q:
            return self.split_multiline_query(q.splitlines())
        else:
            return self.split_singleline_query(q)

    #
    def parse_args(self, commandarg, commandoption=""):
        # 抱合語的オプションの展開
        expandedopts = []
        if self.enable_compound_options:
            expandedopts = self._compoptions.expand(commandoption)
        if not expandedopts and commandoption:
            expandedopts.append(commandoption)

        # コマンド候補を一つずつためす
        results = []
        bad = None
        for expandedopt in expandedopts:
            # クエリの分割
            headoptions = self.split_query(expandedopt)
            tailoptions = self.split_query(commandarg)
            commands = [*headoptions, *tailoptions]
            expanded_command = (" ".join(headoptions) + " " + commandarg).replace("\n", "<br>").strip()
            # パーサーによる解析
            self.new_parser_message_queue()
            try:
                if self.sole_positional:
                    parsedargs, remained = self.argp.parse_known_args(commands)
                    if remained:
                        # 一つの位置引数にすべてを結合する
                        solepos = []
                        value = getattr(parsedargs, self.sole_positional)
                        if value:
                            solepos.append(value)
                        solepos.extend([x for x in remained if not x.startswith("-")])
                        setattr(parsedargs, self.sole_positional, " ".join(solepos))
                else:
                    parsedargs = self.argp.parse_args(commands)
                
                # 引数の構築
                res = self.build_parse_result(expanded_command, parsedargs)
                results.append(res)
            except ArgumentParserExit as e:
                res = CommandParserResult(expanded_command, messages=self._parsermsgs)
                results.append(res)
            except BadCommand as b:
                bad = b
                pass
            except Exception as e:
                raise e
            
        if bad is not None:
            raise bad
        return results
        
    #
    def list_argspecs(self):
        for argtype, name in self.argnames:
            yield argtype, name

    def build_parse_result(self, expanded_command, kwargs):
        if isinstance(kwargs, dict):
            getter = lambda a, k: a.get(k, None)
        else:
            getter = lambda a, k: getattr(a, k, None)
            
        res = CommandParserResult(expanded_command)
        for argtype, name in self.argnames:
            value = getter(kwargs, name)
            if argtype&JoinListArg and value is not None:
                value = " ".join(value)
            res.add_arg(argtype, name, value)
        return res
    
    # 
    def get_description(self):
        return self.argp.description or ""
    
    def get_prog(self):
        return self.argp.prog or ""

    def get_help(self):
        queue = self.new_parser_message_queue()
        self.argp.print_help()
        return queue
        
    def new_parser_message_queue(self):
        self._parsermsgs = []
        return self._parsermsgs
        
    def push_parser_message(self, msg):
        self._parsermsgs.append(msg)

#
#
#
class CommandParserResult():
    def __init__(self, expandedcmd, *, argvalues=None, messages=None):
        self.expandedcmd = expandedcmd
        self.messages = messages
        self.argvalues = argvalues
        self.argmap = defaultdict(dict)
        self.specarg_descriptors = [] # (argtype, name, desc, descargs...)
        self.target_filepath_arg = None
        
    def get_expanded_command(self):
        return self.expandedcmd
    
    def reproduce_command(self):
        # expandedcmd + argmapからコマンドを再現する
        head = self.expandedcmd.split()[0]
        raise NotImplementedError()

    def count_command_part(self):
        return len(self.expandedcmd.split())
    
    def has_exit_message(self):
        return True if self.messages else False
    
    def get_exit_messages(self):
        return self.messages
        
    def add_arg(self, argtype, name, value):
        if argtype & FilepathArg:
            self.target_filepath_arg = (argtype&0xF, name)

        if isinstance(value, str) and value.startswith(SpecArgSig):
            self.specarg_descriptors.append((argtype, name, value[1:]))
        elif isinstance(value, list) and len(value)==1 and value[0].startswith(SpecArgSig):
            self.specarg_descriptors.append((argtype, name, value[0][1:], "list"))
        elif argtype & FilepathArg:
            self.specarg_descriptors.append((argtype, name, "filename_pattern"))
        
        self.argmap[argtype&0xF][name] = value

    # 呼び出し引数を展開する
    def prepare_arguments(self, label):
        at = {"init":InitArg, "target":TargetArg, "exit":ExitArg}[label]
        targs = self.argmap[at]

        multitarget = None
        if self.target_filepath_arg:
            tgat, name = self.target_filepath_arg
            if tgat == at:
                multitarget = self.argmap[tgat][name]
        
        if multitarget:
            for a_target in multitarget:
                targs["target"] = a_target
                yield targs
        else:
            yield targs

    # パス引数を展開する
    def expand_special_arguments(self, spirit):
        for argtype, argname, descvalue, *islist in self.specarg_descriptors:
            preexpand = self.argmap[argtype&0xF][argname]

            expanded = None
            if descvalue.startswith(SpecArgSig):
                # エスケープ
                expanded = descvalue[1:]

            if descvalue == "":
                # 現在選択中のデータから展開
                expanded = self.expand_from_data_selection(spirit, islist)
            
            elif descvalue in ("dlg", "dialog"):
                # タイプに沿ったダイアログボックスを表示する
                if argtype & ColorCodeArg:
                    expanded = self.expand_from_colorpicker(spirit, argname)
                elif argtype & FilepathArg:
                    expanded = self.expand_from_openfilename(spirit, argname, islist)
                else:
                    expanded = self.expand_from_opendirname(spirit, argname)
            
            elif descvalue == "filename_pattern":
                # ファイルパターンから対象となるすべてのファイルパスを展開する
                patterns = preexpand
                paths = []
                for fpath in patterns:
                    fpath = spirit.abspath(fpath)
                    globs = glob.glob(fpath)
                    if len(globs)>0:
                        paths.extend(globs)
                    else:
                        paths.append(fpath)
                expanded = paths

            else:
                continue

            self.argmap[argtype&0xF][argname] = expanded

        self.specarg_descriptors = []
    
    #
    def expand_from_data_selection(self, spi, islist):
        item = None
        chm = spi.select_process_chamber()
        if chm:
            data = chm.get_bound_data()
            if data:
                item = data.selection_item()
                
        if not item:
            raise ValueError("no item selected")

        if islist:
            return [item.get_link()]
        else:
            return item.get_link()
    
    def expand_from_openfilename(self, spi, argname, islist):
        if islist:            
            paths = spi.ask_openfilename(title="ファイルを選択[{}]".format(argname), multiple=True)
            return list(paths)
        else:
            return spi.ask_openfilename(title="ファイルを選択[{}]".format(argname))
        
    def expand_from_opendirname(self, spi, argname):
        return spi.ask_opendirname(title="ディレクトリを選択[{}]".format(argname))

    def expand_from_colorpicker(self, spi, argname):
        return "<colorpicker-not-implemented-yet>"

    #
    def preview_handlers(self):
        funcnames = {
            InitArg : "init_process",
            TargetArg : "process_target",
            ExitArg : "exit_process"
        }
        lines = []
        for argtype, args in self.argmap.items():
            lines.append("{}({})".format(funcnames[argtype], ", ".join(["self"] + [str(x) for x in args])))
        return lines

#
# ###############################################################
#　　抱合語的オプション文字列を解析する
# ###############################################################
#
class CompoundOptions:
    def __init__(self, allow_multiple_option=False):
        self.trie = {}
        self._allow_multiple_option = allow_multiple_option
    
    def add_option(self, name):
        d = self.trie
        for ch in name+" ":
            if ch == " ":
                d["$"] = True
                break
            elif ch not in d:
                d[ch] = {}
            d = d[ch]
        
    #
    def expand(self, optionstr):            
        sprouts = [] # tree, begpos
        def add_new_sprout(tree, begin):
            if sprouts and sprouts[-1][0] is None:
                sprouts[-1] = [tree, begin]
            else:
                sprouts.append([tree, begin])
        
        def grow_sprout(tree, ch):
            if ch in tree:
                # grow sprout
                return tree[ch]
            else:
                # kill sprout
                return None
        ranges = []
        
        i = 0
        loop = True
        while loop:
            if i == len(optionstr):
                loop = False
                ch = None
            else:
                ch = optionstr[i]
                if ch.isspace():
                    loop = False

            add_new_sprout(self.trie, i)
            
            # 苗木をたどる
            firstlen = len(sprouts)
            for si in range(firstlen):
                spr = sprouts[si]
                tree = spr[0]
                if tree is None:
                    continue
                    
                if "$" in tree:
                    begin = spr[1]
                    ranges.append((begin, i))                    
                    if len(tree) > 1:
                        add_new_sprout(tree, begin)
                    spr[0] = None
                else:
                    spr[0] = grow_sprout(tree, ch)
            
            # 途中で追加された苗木をたどる
            for si in range(firstlen, len(sprouts)):
                spr = sprouts[si]
                spr[0] = grow_sprout(spr[0], ch)
            
            i = i + 1
                
        # オプション文字列の可能な全ての組み合わせを導出する
        righties = defaultdict(list)
        for r in ranges:
            _, end = r
            righties[r] = [(rbeg, _) for (rbeg, _) in ranges if end <= rbeg]
            
        combis = defaultdict(list)
        for r in ranges:
            rset = tuple(righties[r])
            combis[rset].append(r)
        
        lines = []
        for rangeline in product(*combis.values()):
            line = []
            disallow = False
            start = 0
            end = None
            for beg, end in rangeline:
                if start<beg:
                    line.append(optionstr[start:beg])
                option = "-" + optionstr[beg:end]
                if not self._allow_multiple_option and option in line:
                    disallow = True
                    break
                line.append(option)
                start = end
            if disallow:
                continue
            rest = optionstr[end:].strip()
            if rest:
                line.append(rest)
            lines.append(line)
        
        return [" ".join(x) for x in lines]

#
# ###############################################################
#  CommandDialogSpec
# ###############################################################
#
class CommandDialogSpec():
    use_command_dialog = True

    def __init__(self, parser, commandhead):
        self.parser = parser
        self.commandhead = commandhead
    
    def get_expanded_command(self):
        return "-?"
    
#
# ###############################################################
#  CommandLauncher
# ###############################################################
#
# 文字列から対応するコマンドを見つけ出す
#
class CommandEngine:
    def __init__(self):
        self.commandsets = []
        self.parsefails = []
        self.prefix = ""
        
    def install_commands(self, commandset):
        self.commandsets.append(commandset)
    
    def command_sets(self):
        return self.commandsets
    
    def set_command_prefix(self, prefix):
        self.prefix = prefix

    # コマンドを解析する
    def parse_command(self, commandhead, commandtail, app):
        self.parsefails = []

        # 文字列が示すコマンドエントリを選び出す
        possible_commands = [] # (entry, reststr)
        for cmdset in self.commandsets:
            matches = cmdset.match(commandhead)
            possible_commands.extend(matches)
            if self.prefix:
                matches = cmdset.match(self.prefix + commandhead)
                possible_commands.extend(matches)

        use_dialog = False
        
        # オプションと引数を解析し、全ての可能なコマンド解釈を生成する
        possible_entries = []
        for commandentry, commandoptions in possible_commands:
            target = commandentry.load()
            spirit = target.invoke_spirit(app)

            if commandoptions.endswith("?"):
                use_dialog = True
                commandoptions = commandoptions[:-1]
            
            # 引数コマンドを解析
            possible_syntaxes = []
            target.load_lazy_describer(spirit)
            apser = target.get_argparser()
            try:
                possible_syntaxes = apser.parse_args(commandtail, commandoptions)
            except BadCommand as b:
                self.parsefails.append((target, b.error))
            
            if use_dialog:
                break
            
            # 可能性のある解釈として追加
            for parseresult in possible_syntaxes:                
                possible_entries.append((target, spirit, parseresult))
        
        #
        if not possible_commands:
            return []
        elif not possible_entries or use_dialog:
            # ダイアログモードで選択
            commandverb = commandentry.get_keywords()[0]
            parseresult = CommandDialogSpec(apser, commandverb)
            self.parsefails = []
            return [(target, spirit, parseresult)]
        else:
            # 最も長く入力コマンドにマッチしている解釈の順に並べ直す
            possible_entries.sort(key=lambda x:x[2].count_command_part())
            return possible_entries

    # 
    def get_first_parse_command_fail(self):
        if not self.parsefails:
            return None, None
        return self.parsefails[0] # process, error

    #
    def test_command_head(self, commandhead):
        for cmdset in self.commandsets:
            if cmdset.match(commandhead):
                return True
        return False
        
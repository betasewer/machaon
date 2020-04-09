#!/usr/bin/env python3
# coding: utf-8
import glob
from collections import defaultdict
from typing import List, Sequence, Optional, Any, Tuple
    
#
# ########################################################
#  Command Parser
# ########################################################
#
SpecArgSig = "?"

#
OPT_ACCUMULATE = 0x0001
OPT_REMAINDER = 0x0002
OPT_OPTIONAL = 0x0004
OPT_METHOD_TYPE = 0xF000
OPT_METHOD_INIT = 0x1000
OPT_METHOD_TARGET = 0x2000
OPT_METHOD_EXIT = 0x4000

#
ARG_TYPE_STRING = 1
ARG_TYPE_FILEPATH = 2
ARG_TYPE_DIRPATH = 3
ARG_TYPE_COLORCODE = 4

#
class BadCommand(Exception):
    pass

#
#
#
class OptionContext():
    def __init__(self, 
        *names, 
        valuetype=None,
        min=1, 
        max=1, 
        value=None,
        default=None,
        dest=None,
        flags=0,
        help="",
    ):
        self.topname = None
        for name in names:
            if not name.startswith("-") or name.startswith("--"):
                self.topname = name
                break
        else:
            raise ValueError("long name needed")

        self.names = names
        self.min_args = min
        self.max_args = max
        self.dest = dest or self.get_name().lstrip("-")
        self.value = value
        self.default = default
        self.valuetype = valuetype
        self.flags = flags
        self.help = help
    
    def __repr__(self):
        return "<OptionContext '{}'>".format(self.get_name())
    
    def get_keys(self):
        return self.names

    def get_name(self):
        return self.topname
    
    def get_dest(self):
        return self.dest
    
    def get_dest_method(self):
        return self.flags & OPT_METHOD_TYPE
    
    def is_positional(self):
        return not self.names[0].startswith("-")

    def is_optional(self):
        return (self.flags & OPT_OPTIONAL) > 0
    
    def consumes_remainder(self):
        return (self.flags & OPT_REMAINDER) > 0
    
    def is_accumulate(self):
        return (self.flags & OPT_ACCUMULATE) > 0
    
    def is_nullary(self):
        return self.max_args == 0

    def is_ready(self, args):
        if self.min_args is None:
            return True
        return len(args) >= self.min_args

    def is_full(self, args):
        if self.max_args is None:
            return False
        return len(args) >= self.max_args

    def parse_arg(self, args, outputs):
        value = outputs.get(self.dest, None)
        if not args:
            value = self.valuetype.convert(self.value)
        elif self.is_accumulate():
            value = self.valuetype.generate(*args, prev=value)
        else:
            value = self.valuetype.generate(*args)
        outputs[self.dest] = value
        
    def parse_default(self, outputs):   
        if self.default is None:
            value = None # Noneは変換しない
        else:
            value = self.valuetype.convert(self.default)
        outputs[self.dest] = value

    def get_value_type(self):
        return self.valuetype

    def get_value_typename(self):
        return self.valuetype.get_typename()
    
    def get_help(self):
        return self.help

#
#
#
class OptionValueType():
    def __init__(self, valtype=None):
        if valtype is None:
            self.type = str
        elif isinstance(valtype, type):
            self.type = valtype
        elif isinstance(valtype, str):
            self.type = str
            
    def get_typename(self):
        if isinstance(self.type, type):
            return self.type.__name__
        else:
            return str(self.type)

    def generate(self, *args):
        return self.type(*args)
    
    def convert(self, v):
        if not isinstance(v, self.type):
            v = self.type(v)
        return v

#
class OptionValueList(OptionValueType):
    def __init__(self, valtype):
        super().__init__(valtype)
    
    def generate(self, *args):
        return [*args]

#
class OptionValueJoiner(OptionValueType):
    def __init__(self, valtype):
        super().__init__(valtype)
    
    def generate(self, *args):
        return " ".join(args)

#
class OptionValueAccumulator(OptionValueType):
    def __init__(self, valtype, listtype):
        super().__init__(valtype)
        self.listtype = listtype
    
    def generate(self, *args, prev=None):
        v = self.type(*args)
        part = self.listtype((v,))
        if prev is None:
            return part
        else:
            return prev + part

    def convert(self, v):
        if not v:
            return self.listtype()
        elif isinstance(v, self.listtype):
            return v
        else:
            return self.listtype((v,))

#
#
# argparseをラップする
#
#
class CommandParser():
    __debugdisp__ = False
    #
    # __init__(["targets"], ("--template","-t"), ...)
    #
    def __init__(self, *, description, prog):
        self.description = description
        self.prog = prog

        self._optiontrie = CompoundOptions()
        self._optiontrie.add_option("h", None)
        self.enable_compound_options = True

        self.positionals = []
        self.options = {}
        self.argnames = {}
       
    #
    #
    #
    def add_arg(self,
        *names, 
        valuetype=None,
        flag=False,
        const=None,
        variable=False, # 任意の数の引数をとる
        joinspace=False, # 値を結合する
        remainder=False, # 書式を無視して以降をすべて引数とする
        accumulate=False, # 重複するオプションをリストに集積する
        optional=None, # 省略可能な位置引数
        typespec=None,
        arity=None,
        min=-1,
        max=-1,
        value=None,
        default=None,
        dest=None,        
        methodtype=None,
        help=""
    ):
        if not names:
            raise ValueError("option names must be specified")

        minarg = 1
        maxarg = 1
        flags = 0

        option = names[0].startswith("-")
        if optional is None and option:
            optional = True
        
        if flag:
            const = True
            default = False

        if const is not None:
            minarg = 0
            maxarg = 0
            value = const
            
        if variable or remainder:
            minarg = 0
            maxarg = None
            if valuetype is None:
                typespec = OptionValueList(valuetype)
            else:
                typespec = OptionValueType(valuetype)
            flags |= OPT_OPTIONAL
            default = [] if default is None else default
        
        if joinspace:
            maxarg = None
            typespec = OptionValueJoiner(str)
            default = ""
        
        if remainder:
            typespec = OptionValueJoiner(str)
            default = ""
            flags |= OPT_REMAINDER
        
        if accumulate:
            flags |= OPT_ACCUMULATE
            flags |= OPT_OPTIONAL
            default = [] if default is None else default
            typespec = OptionValueAccumulator(valuetype, type(default))
        
        if optional:
            minarg = 0
            flags |= OPT_OPTIONAL

        if typespec is None:
            if valuetype is None:
                if value is not None:
                    typespec = OptionValueType(type(value))
                else:
                    typespec = OptionValueType()
            else:
                typespec = OptionValueType(valuetype)
        
        if min != -1:
            minarg = min
        
        if max != -1:
            maxarg = max
        
        if arity is not None:
            minarg = arity
            maxarg = arity

        if isinstance(methodtype, int):
            flags |= methodtype
        elif methodtype == "init":
            flags |= OPT_METHOD_INIT
        elif methodtype == "target":
            flags |= OPT_METHOD_TARGET
        elif methodtype == "exit":
            flags |= OPT_METHOD_EXIT
            
        #
        cxt = OptionContext(*names, 
            valuetype=typespec, min=minarg, max=maxarg, value=value,
            default=default, dest=dest, flags=flags, 
            help=help
        )
        dest = cxt.get_dest()
        if cxt.is_positional():
            self.positionals.append(cxt)
            self.argnames[dest] = cxt
        else:
            for name in cxt.names:
                self.options[name] = cxt
            if dest not in self.argnames:
                self.argnames[dest] = cxt
        
        # trie
        for name in names:
            if name.startswith("--"):
                continue
            elif name.startswith("-"):
                sig = name[1:]
            else:
                continue
            self._optiontrie.add_option(sig, cxt)
        
        return cxt
    
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
    
    def generate_command_rows(self, command):
        # コマンド解釈の候補一覧を作成
        command_rows = [[]]
        commands = self.split_query(command)
        if self.enable_compound_options:
            for command in commands:
                if command.startswith("-") and not command.startswith("--"):
                    newrows = []
                    for newrow in self._optiontrie.parse(command[1:]):
                        for cmdrow in command_rows:
                            newrows.append(cmdrow + newrow)
                    command_rows = newrows
                else:
                    command_rows = [x+[command] for x in command_rows]
        else:
            command_rows = [commands]
        return command_rows

    def parse_args(self, commandrow):
        # コマンドを解析し結果を作成する     
        try:
            kwargs = self.do_parse_args(commandrow)
            res = self.build_parse_result(display_command_row(commandrow), kwargs)
        except BadCommand as e:
            raise e
        return res
    
    #
    def do_parse_args(self, args):
        kwargs = {}
        
        context = None
        positcontexts = [x for x in reversed(self.positionals)]

        stack = []
        appeared = set()
        def finish_context(cxt):
            # 値を生成する
            cxt.parse_arg(stack, kwargs)
            # 出現したコンテキストを記録する
            d = cxt.get_dest()
            appeared.add(d)            
            # スタックを空に
            stack.clear()

        for arg in args:
            if isinstance(arg, OptionContext):
                # 既に解析済みのオプション
                optcontext = arg
            elif arg.startswith("-") and arg in self.options:
                # オプションとして読み取る
                optcontext = self.options[arg]
            else:
                # 引数として読み取る
                optcontext = None
                stack.append(arg)
            
            if context is not None and context.consumes_remainder():
                # remainder属性の引数を処理する
                if optcontext:
                    optcontext = None
                    stack.append(arg)
                
            if optcontext is None and context is None:
                # 次の位置引数へ
                if not positcontexts:
                    if arg.startswith("-"):
                        raise BadCommand("undefined option: '{}'".format(arg))
                    else:
                        raise BadCommand("undefined positional argument: '{}'".format(arg))
                context = positcontexts.pop()

            if optcontext is not None:
                # 新たなオプションが開始した：前の引数を解決する
                if context is not None:
                    if context.is_ready(stack):
                        finish_context(context)
                    else:
                        raise BadCommand("too few option arguments for <{}>".format(context.get_name()))
                context = optcontext
            
            if context.is_full(stack):
                # 引数が満杯であれば即座に解決（0個も含めて）
                finish_context(context)
                context = None
        
        # 最後の引数を解決する
        if context:
            finish_context(context)

        #
        # デフォルト引数で埋める
        #
        # 指定のないオプション
        for name, cxt in self.argnames.items():
            if name not in appeared:
                if cxt.is_optional():
                    cxt.parse_default(kwargs)
                else:
                    raise BadCommand("too few positional arguments for <{}>".format(name))

        return kwargs
        
    #
    def build_parse_result(self, expanded_command, kwargs):
        res = CommandParserResult(expanded_command)
        for name, cxt in self.argnames.items():
            value = kwargs.get(name, None)
            res.add_arg(cxt, name, value)
        return res
        
    #
    def list_contexts(self):
        cxts = []
        for cxt in self.positionals:
            if cxt not in cxts:
                cxts.append(cxt)
        for cxt in self.options.values():
            if cxt not in cxts:
                cxts.append(cxt)
        return cxts
    
    # 
    def get_description(self):
        return self.description or ""
    
    def get_prog(self):
        return self.prog or ""

    def get_help(self):
        #queue = self.new_parser_message_queue()
        #self.argp.print_help()
        #return queue
        return "<help>"

#
#
#
class CommandParserResult():
    def __init__(self, expandedcmd, *, messages=None):
        self.expandedcmd = expandedcmd
        self.messages = messages
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
        
    def add_arg(self, cxt, name, value):        
        self.argmap[cxt.get_dest_method()][name] = value
        """
        if cxt.is_value_type(OPT_TYPE_FILEPATH):
            self.target_filepath_arg = (argtype&0xF, name)

        if isinstance(value, str) and value.startswith(SpecArgSig):
            self.specarg_descriptors.append((argtype, name, value[1:]))
        elif isinstance(value, list) and len(value)==1 and value[0].startswith(SpecArgSig):
            self.specarg_descriptors.append((argtype, name, value[0][1:], "list"))
        elif argtype & FilepathArg:
            self.specarg_descriptors.append((argtype, name, "filename_pattern"))
        
        self.argmap[argtype&0xF][name] = value
        """

    # 呼び出し引数を展開する
    def prepare_arguments(self, label):
        at = {
            "init":OPT_METHOD_INIT, 
            "target":OPT_METHOD_TARGET, 
            "exit":OPT_METHOD_EXIT
        }[label]
        targs = self.argmap[at]

        multitarget = None
        if self.target_filepath_arg is not None:
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
                if argtype & ARG_TYPE_COLORCODE:
                    expanded = self.expand_from_colorpicker(spirit, argname)
                elif argtype & ARG_TYPE_FILEPATH:
                    expanded = self.expand_from_openfilename(spirit, argname, islist)
                elif argtype & ARG_TYPE_DIRPATH:
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
            OPT_METHOD_INIT : "init_process",
            OPT_METHOD_TARGET : "process_target",
            OPT_METHOD_EXIT : "exit_process"
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
    def __init__(self):
        self.trie = {}
    
    def add_option(self, name, terminal):
        d = self.trie
        for ch in name+" ":
            if ch == " ":
                d["$"] = terminal
                break
            elif ch not in d:
                d[ch] = {}
            d = d[ch]
    
    #
    def compounds_to_rangelist(self, string):        
        # 辿っている木を保存するバッファ（苗木）     
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
            if i == len(string):
                loop = False
                ch = None
            else:
                ch = string[i]
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
                    context = tree["$"]
                    ranges.append((begin, i, context))
                    if not context.is_nullary(): # コンテキストが引数を取るなら、残りの文字列は引数とみなす
                        loop = False
                        break
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
        
        return ranges

    #
    def rangelist_to_passagelist(self, string, rangelist):
        # 座標リストを木構造に変換する
        range_and_its_righters = defaultdict(list)
        for r in rangelist:
            beg, end, _cxt = r
            range_and_its_righters[beg].append((end, r))

        # 木構造を経路リストに変換する
        def _walk_tree(rows, head, strend, currow=[], level=0):
            if level==99:
                raise ValueError("Maximum Depth Recursion {}, {}".format(head, strend))
                
            for end, rng in range_and_its_righters[head]:
                newrow = currow + [rng]
                if end == strend:
                    rows.append(newrow)
                else:
                    _walk_tree(rows, end, strend, newrow, level+1)
            
        passages = []
        if rangelist:
            begpoint = min([b for (b,e,_) in rangelist])
            endpoint = max([e for (b,e,_) in rangelist])
            _walk_tree(passages, begpoint, endpoint)
        return passages
        
    #
    def parse(self, optionstr):
        # 文字列を解析して経路リストへ
        rnglist = self.compounds_to_rangelist(optionstr)
        pathways = self.rangelist_to_passagelist(optionstr, rnglist)

        # 経路リストを解析する
        lines = []
        for rangerow in pathways:
            line = []
            disallow = False
            start = 0
            end = None
            for beg, end, cxt in rangerow:
                if start<beg:
                    line.append(optionstr[start:beg])
                option = optionstr[beg:end]
                if not cxt.is_accumulate() and option in line:
                    disallow = True
                    break
                line.append(cxt)
                start = end
            if disallow:
                continue
            rest = optionstr[end:].strip()
            if rest:
                line.append(rest)
            lines.append(line)
        
        return lines

#
#
#
def display_command_row(cmdrow):
    c = ""
    for cmd in cmdrow:
        if isinstance(cmd, str):
            c += cmd
        elif isinstance(cmd, OptionContext):
            c += cmd.get_name()
    return c.replace("\n", "<br>").strip()

#!/usr/bin/env python3
# coding: utf-8
import glob
from collections import defaultdict
from typing import List, Sequence, Optional, Any, Tuple, Dict, Union
    
#
# ########################################################
#  Command Parser
# ########################################################
SpecArgSig = "?"

#
OPT_ACCUMULATE = 0x0001
OPT_REMAINDER = 0x0002
OPT_POSITIONAL = 0x0004
OPT_NULLARY = 0x0010
OPT_OPTIONAL_UNARY = 0x0020
OPT_UNARY = 0x0040

#
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
PARSE_SEP = 0
PARSE_END = 1

#
class BadCommand(Exception):
    pass

#
#
#
class OptionContext():
    def __init__(self, 
        longnames: Sequence[str],
        shortnames: Sequence[str],
        valuetype: Any = None,
        value: Any = None,
        default: Any = None,
        dest: int = None,
        flags: int = 0,
        help: str = "",
    ):
        self.longnames = longnames
        self.shortnames = shortnames
        self.dest = dest
        self.value = value
        self.default = default
        self.valuetype = valuetype
        self.flags = flags
        self.help = help
    
    def __repr__(self):
        return "<OptionContext '{}'>".format(self.get_name())
    
    def get_name(self):
        return self.longnames[0]

    def match_name(self, key):
        return key in self.longnames or key in self.shortnames
    
    def make_key(self, prefix=None):
        return self.get_name() if not prefix else prefix*2 + self.longnames[0]
    
    def make_keys(self, prefix=None):
        lk = [x if not prefix else prefix*2+x for x in self.longnames]
        sk = [x if not prefix else prefix*1+x for x in self.shortnames]
        return lk + sk
    
    def get_dest(self):
        return self.dest
    
    def get_dest_method(self):
        return self.flags & OPT_METHOD_TYPE
    
    def is_positional(self):
        return (self.flags & OPT_POSITIONAL) > 0

    def is_unary(self):
        return (self.flags & OPT_UNARY) > 0

    def is_optional_unary(self):
        return (self.flags & OPT_OPTIONAL_UNARY) > 0
    
    def is_nullary(self):
        return (self.flags & OPT_NULLARY) > 0

    def consumes_remainder(self):
        return (self.flags & OPT_REMAINDER) > 0
    
    def is_accumulative(self):
        return (self.flags & OPT_ACCUMULATE) > 0

    def parse_arg(self, arg, outputs):
        defval = None
        use_defval = not arg
        if use_defval:
            if self.value is not None: # Noneは変換しない
                defval = self.valuetype.convert(self.value) # valueがデフォルト値になる
        
        if hasattr(self.valuetype, "accumulate"):
            if use_defval:
                va = defval
            else:
                va = self.valuetype.convert(arg)
            prevvalue = outputs.get(self.dest, None)
            value = self.valuetype.accumulate(va, prevvalue)
        else:
            if use_defval:
                value = defval
            else:
                value = self.valuetype.convert(arg)

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
    
    def convert(self, v):
        if not isinstance(v, self.type):
            v = self.type(v)
        return v

#
class OptionValueList(OptionValueType):
    def __init__(self, valtype):
        super().__init__(valtype)
    
    def convert(self, arg):
        return arg.split()

#
class OptionValueAccumulator(OptionValueType):
    def __init__(self, valtype, listtype):
        super().__init__(valtype)
        self.listtype = listtype
    
    def convert(self, v):
        if not v:
            return self.listtype()
        elif isinstance(v, self.listtype):
            return v
        else:
            vc = super().convert(v)
            return self.listtype((vc,))

    def accumulate(self, arg, prev):
        if prev is None:
            return arg
        else:
            return prev + arg

#
#
Token = Union[str, int, OptionContext]
TokenRow = List[Token]

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
    def __init__(self, *, description, prog, prefix_chars=("-",)):
        self.description = description
        self.prog = prog
        self.prefix_chars = prefix_chars

        self._optiontrie = CompoundOptions()
        self._optiontrie.add_option("h", None)
        self.enable_compound_options = True

        self.positional: Optional[OptionContext] = None
        self.options: List[OptionContext] = []
        self.argnames: Dict[str, OptionContext] = {} 

    #
    # valuetype int []
    #
    def add_arg(self,
        *names, 
        valuetype=None,
        flag=False,
        const=None,
        defarg=None,
        arg=1,            # 引数の数 [1: 引数を1つ取る（デフォルト）, 0: 引数なし, ?: 1つ取るが省略可能（キー自体が存在する場合はvalueの値がデフォルト値になる）]
        remainder=False,  # 書式を無視して以降をすべて引数とする
        accumulate=False, # 重複するオプションをリストに集積する
        typespec=None,
        default=None,
        value=None,
        dest=None,
        methodtype=None,
        help=""
    ):
        if not names:
            raise ValueError("At least 1 name must be specified")

        flags = 0

        if flag:
            const = True
            default = False

        if const is not None:
            arg = 0
            value = const
        
        if defarg is not None:
            arg = "?"
            value = defarg
        
        if valuetype is None:
            if value is not None:
                valuetype = type(value)

        if remainder:
            arg = "?"
            flags |= OPT_REMAINDER
            default = ""
            typespec = OptionValueType(str)
        
        if accumulate:
            flags |= OPT_ACCUMULATE
            default = [] if default is None else default
            typespec = OptionValueAccumulator(valuetype, type(default))
        
        if arg == "?":
            flags |= OPT_OPTIONAL_UNARY
        elif arg == 0 or arg == "0":
            flags |= OPT_NULLARY
        elif arg == 1 or arg == "1":
            flags |= OPT_UNARY
        else:
            raise ValueError("bad arity '{}'".format(arg))

        if typespec is None:
            typespec = OptionValueType(valuetype)

        if isinstance(methodtype, int):
            flags |= methodtype
        elif methodtype == "init":
            flags |= OPT_METHOD_INIT
        elif methodtype == "target":
            flags |= OPT_METHOD_TARGET
        elif methodtype == "exit":
            flags |= OPT_METHOD_EXIT
            
        longnames = []
        shortnames = []
        for name in names:
            leng = self._prefix_length(name)
            if leng == 0:
                flags |= OPT_POSITIONAL
                longnames = [name]
                break
            elif leng == 1:
                shortnames.append(name[1:])
            elif leng == 2:
                longnames.append(name[2:])
        
        if not longnames:
            raise ValueError("option '{}': at least 1 long name needed".format("/".join(names)))
        
        if dest is None:
            dest = longnames[0]

        #
        cxt = OptionContext(longnames, shortnames, 
            valuetype=typespec, value=value, default=default, 
            dest=dest, flags=flags, 
            help=help
        )

        dest = cxt.get_dest()
        if cxt.is_positional():
            if self.positional is not None:
                raise ValueError("positional argument has already existed")
            self.positional = cxt
            self.argnames[dest] = cxt
        else:
            self.options.append(cxt)
            if dest not in self.argnames:
                self.argnames[dest] = cxt
        
            # trie木に登録
            for name in cxt.shortnames:
                self._optiontrie.add_option(name, cxt)
        
        return cxt
    
    # おもにデバッグ用
    def find_context(self, name) -> Optional[OptionContext]:
        for cxt in self.options:
            if cxt.match_name(name):
                return cxt
        if self.positional and self.positional.match_name(name):
            return self.positional
        return None
    
    #
    # 引数解析
    #
    def split_query(self, q):
        if "\n" in q:
            return self._multiline_query(q)
        else:
            return self._singleline_query(q)
    
    def _singleline_query(self, q):
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
    
    def _multiline_query(self, q):
        parts = []
        for i, line in enumerate(q.splitlines()):
            if i == 0: # 先頭行はそのまま値とする
                parts.append(line.strip())
            else:
                spl = line.split(maxsplit=1)
                if not spl:
                    continue
                elif len(spl) == 2:
                    option, value = spl
                    if self._prefix_length(option) == 0:
                        option = self.add_option_prefix(option, autolength=True) # オプション記号が一つもなければ着ける
                    parts.extend([option, value]) # 先頭をオプションとみなし、一度だけ区切る
                else:
                    parts.append(spl[0])
        return parts
    
    def _prefix_length(self, command):
        leng = 0
        for ch in command:
            if ch not in self.prefix_chars or leng>=2:
                break
            else:
                leng += 1
        return leng
    
    def generate_command_rows(self, command: str) -> List[TokenRow]:
        # コマンド解釈の候補一覧を作成
        command_rows: List[TokenRow] = [[]]
        commands = self.split_query(command)
        if self.enable_compound_options:
            for command in commands:
                if self._prefix_length(command) == 1:
                    newrows = []
                    for newrow in self._optiontrie.parse(command[1:]):
                        for cmdrow in command_rows:
                            newrows.append(cmdrow + newrow)
                    if commands and not newrows:
                        raise BadCommand("抱合オプション'{}'を解釈できません".format(command))
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
            res = self.build_parse_result(self.display_command_row(commandrow), kwargs)
        except BadCommand as e:
            raise e
        return res
    
    #
    def do_parse_args(self, args):        
        # 区切られた文字列のリストを解析する
        argstack = []
        curcxt = None 
        contexts: List[Tuple[OptionContext, str]] = [] 
        tokens = [*args, PARSE_END]
        for token in tokens:
            newcxt = None
            pfxlen = None
            if token == PARSE_SEP:
                # コンテキストを即座に終了し、新しいコンテキストを開始する
                contexts.append((curcxt, argstack))
                argstack = []
                curcxt = None
                continue

            elif isinstance(token, OptionContext):
                # 既に解析済みのオプション
                newcxt = token

            elif isinstance(token, str):
                arg = token
                foundcxt = None
                pfxlen = self._prefix_length(arg)
                if pfxlen > 0:
                    for cxt in self.options:
                        if cxt.match_name(arg[pfxlen:]):
                            foundcxt = cxt
                            break

                consuming_remainder = curcxt and curcxt.consumes_remainder()
                if foundcxt is not None and not consuming_remainder: #remainder属性の文脈ではない
                    # オプションとして読み取る
                    newcxt = foundcxt
                elif arg:
                    # 引数として読み取る
                    argstack.append(arg)
            
            elif token == PARSE_END:
                # 終端まで来た
                newcxt = "<end>"
                
            # 新たなオプションが開始した：前の引数を解決する
            if newcxt:
                if curcxt is None:
                    # 位置引数を解決する
                    if self.positional is not None:
                        curcxt = self.positional
                    else:
                        if argstack: # 位置引数が存在せず、かつ解決不能な引数が置かれている
                            raise BadCommand("予期しない引数'{}'を解釈できません".format(arg))
                        curcxt = newcxt
                        continue
                        
                # 現在のコンテキストを終了し、新しいコンテキストを開始する
                contexts.append((curcxt, argstack))
                argstack = []
                curcxt = newcxt

        # 引数をチェックする
        postposit = self.positional is not None
        missing_posit_arg = None
        for i, (cxt, stack) in enumerate(contexts):   
            if self.positional is not None:     
                # 一つ目は位置引数
                if i == 0 and cxt is not self.positional:
                    raise BadCommand("positional argument must come at first or last")

                if cxt is self.positional:
                    if cxt.is_unary() and not stack:
                        # 中間に置かれていると考える
                        continue
                    postposit = False

            if cxt.is_nullary() and stack:
                # 引数が多すぎる
                if i == len(contexts)-1 and postposit:
                    missing_posit_arg = stack.copy() # 後置された位置引数と考える
                    stack.clear()
                else:
                    raise BadCommand("予期しない引数'{}'を解釈できません".format(arg))

            elif cxt.is_unary() and not stack:
                # 引数が少なすぎる
                raise BadCommand("オプション<{}>に必要な引数がありません".format(cxt.make_key(self.prefix_chars[0])))

        if postposit:
            # 後置の位置引数
            contexts = [(x,a) for x,a in contexts if x is not self.positional]
            if missing_posit_arg:
                contexts.append((self.positional, missing_posit_arg))
            elif not any(x is self.positional for x,_ in contexts):
                # 位置引数が無い
                raise BadCommand("位置引数<{}>に相当する引数がありません".format(self.positional.make_key()))

        # 引数の文字列を値へと変換する
        kwargs = {}
        appeared = set()
        for cxt, stack in contexts:  
            # 値を生成する
            argstring = " ".join(stack)
            cxt.parse_arg(argstring, kwargs)
            # 出現したコンテキストを記録する
            appeared.add(cxt.get_dest())
        
        # デフォルト引数で埋める
        for name, cxt in self.argnames.items():
            if name not in appeared:
                cxt.parse_default(kwargs)

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
        if self.positional:
            cxts.append(self.positional)
        for cxt in self.options:
            if cxt not in cxts:
                cxts.append(cxt)
        return cxts
    
    def add_option_prefix(self, option: str, *, long=False, autolength=False) -> str:
        pfx = self.prefix_chars[0]
        if autolength:
            # 存在するオプション名として、プレフィックスの長さを確かめる
            cxt: Optional[OptionContext] = next((x for x in self.options if x.match_name(option)), None)
            if cxt is None:
                raise ValueError("No such option exists: '{}'".format(option))
            long = option in cxt.longnames

        if long:
            return pfx*2 + option
        else:
            return pfx*1 + option
            
    #
    def display_command_row(self, commandrow: Sequence[TokenRow]):
        parts: List[str] = []
        for i, cmd in enumerate(commandrow):
            if isinstance(cmd, str):
                parts.append(cmd)
            elif isinstance(cmd, OptionContext):
                parts.append(cmd.make_key(self.prefix_chars[0]))
            elif isinstance(cmd, int):
                if cmd == PARSE_END:
                    continue
                elif cmd == PARSE_SEP and i < len(commandrow)-1:
                    parts.append("|")

        return " ".join(parts).replace("\n", "<br>").strip()

    
    # 
    def get_description(self):
        return self.description or ""
    
    def get_prog(self):
        return self.prog or ""

    def get_help(self):
        #queue = self.new_parser_message_queue()
        #self.argp.print_help()
        #return queue
        return ["<help>"]

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
                if not cxt.is_accumulative() and option in line:
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


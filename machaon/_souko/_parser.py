#!/usr/bin/env python3
# coding: utf-8
import os
import glob
from collections import defaultdict
from typing import List, Sequence, Optional, Any, Tuple, Dict, Union, Callable, DefaultDict
from inspect import signature

#
# ########################################################
#  Command Parser
# ########################################################
SpecialArgChar = "?"

#
OPT_POSITIONAL = 0x0001
OPT_REMAINDER = 0x0002
OPT_NULLARY = 0x0010
OPT_OPTIONAL_UNARY = 0x0020
OPT_UNARY = 0x0040
OPT_SEQUENCEFOREACH = 0x0100
OPT_SEQUENCETOP = 0x0200
OPT_SEQUENCEASVALUE = 0x0400

#
OPT_METHOD_TYPE = 0xF000
OPT_METHOD_INIT = 0x1000
OPT_METHOD_TARGET = 0x2000
OPT_METHOD_EXIT = 0x4000

def OPT_METHOD(label):
    return {
        "init":OPT_METHOD_INIT, 
        "target":OPT_METHOD_TARGET, 
        "exit":OPT_METHOD_EXIT
    }.get(label, label)

#
PARSE_SEP = 0
PARSE_END = 1

#
class BadCommand(Exception):
    pass

#
class ARGSTRING_NO_SPLIT():
    pass

#
# もともとの区切りを記録したオプション引数
#
class ArgString():
    def __init__(self, argparts):
        self.argparts = argparts
    
    def empty(self):
        return not self.argparts
    
    def contains(self, ch):
        return any(ch in x for x in self.argparts)
    
    def joined(self):
        return " ".join(self.argparts)
    
    def __str__(self):
        return self.joined()
        
    def __repr__(self):
        return "<{}>".format(" ".join(["ArgString:", self.joined()]))

    def split(self, sep=ARGSTRING_NO_SPLIT, maxsplit=-1):
        if sep is not ARGSTRING_NO_SPLIT:
            # 最優先される区切り
            total = self.joined()
            if sep in total:
                return total.split(sep=sep, maxsplit=maxsplit)

        # 元の区切りそのまま
        if maxsplit > -1:
            return [*self.argparts[:maxsplit], " ".join(self.argparts[maxsplit:])]
        else:
            return self.argparts

#
#
#
class OptionContext():
    def __init__(self, 
        longnames: Sequence[str],
        shortnames: Sequence[str],
        valuetype: Any,
        dest: str,
        value: Any = None,
        default: Any = None,
        flags: int = 0,
        accumulator: Any = None,
        help: str = "",
    ):
        self.longnames: Sequence[str] = longnames
        self.shortnames: Sequence[str] = shortnames
        self.valuetype: Any = valuetype
        self.dest: str = dest
        self.value: Any = value
        self.default: Any = default
        self.flags: int = flags
        self.help: str = help
        self.accumulator: Optional[Callable[[Any, Any, Any], Any]] = accumulator
    
    def __repr__(self):
        return "<OptionContext '{}'>".format(self.get_name())
    
    def get_name(self):
        return self.longnames[0]

    def match_name(self, key):
        return key in self.longnames or key in self.shortnames
    
    def make_key(self, prefix):
        if self.is_positional():
            return self.get_name()
        else:
            return prefix*2 + self.longnames[0]
    
    def make_keys(self, prefix):
        if self.is_positional():
            lk = self.longnames
            sk = self.shortnames
        else:
            lk = [prefix*2+x for x in self.longnames]
            sk = [prefix*1+x for x in self.shortnames]
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
        return self.accumulator is not None
    
    def expands_foreach(self):
        return (self.flags & OPT_SEQUENCEFOREACH) > 0
    
    def expands_top(self):
        return (self.flags & OPT_SEQUENCETOP) > 0

    def parse_arg(self, arg: ArgString, outputs, spirit=None):
        if arg.empty():
            value = self.make_default_value(self.value, spirit)
        else:
            if self.valuetype.is_simplex_type():
                value = self.valuetype.convert(str(arg), spirit) # 引数を変換
            else:
                value = self.valuetype.convert(arg, spirit)

        if self.accumulator is not None:
            if self.dest in outputs:
                prevvalue = outputs[self.dest]  
            else:
                prevvalue = self.default() # このデフォルト値は各試行ごとに生成する必要がある
            value = self.accumulator(value, prevvalue, self)

        outputs[self.dest] = value
        return value
    
    def parse_default(self, outputs, spirit=None):
        if self.accumulator is not None:
            value = self.default()
        else:
            value = self.make_default_value(self.default, spirit)
        outputs[self.dest] = value
        return value
    
    def make_default_value(self, value, spirit):
        if value is None: 
            # Noneは変換しない
            if (self.flags & (OPT_SEQUENCEFOREACH|OPT_SEQUENCETOP))>0:
                v = ()
            else:
                v = None
        else:
            if isinstance(value, str) and self.valuetype.is_compound_type():
                value = ArgString([value])
            v = self.valuetype.convert(value, spirit)
        return v

    def get_value_type(self):
        return self.valuetype

    def get_value_typename(self):
        return self.valuetype.typename
    
    def get_help(self):
        return self.help

#
# accumulator
#
# リストに追加する
def ArgAppender(value, prev, _cxt, *, initial=list):
    prev.append(value)
    return prev

# 数を数える
def ArgCounter(_value, prev, _cxt, *, initial=int):
    return prev + 1

#
# #######################################################################
#  パーサー
# #######################################################################
#
Token = Union[str, int, OptionContext]
TokenRow = List[Token]

#
#
#
class CommandParser():
    __debugdisp__ = False
    #
    #
    #
    def __init__(self, *, description, prog, prefix_chars=("-",)):
        self.description = description
        self.prog = prog
        self.prefix_chars = prefix_chars

        self._optiontrie = CompoundOptions()

        self.positional: Optional[OptionContext] = None
        self.options: List[OptionContext] = []
        self.argnames: Dict[str, OptionContext] = {} 

    #
    def _prefix_length(self, command):
        leng = 0
        for ch in command:
            if ch not in self.prefix_chars or leng>=2:
                break
            else:
                leng += 1
        return leng

    #
    #
    #
    def add_arg(self,
        *names, 
        valuetype=None,
        flag=False,
        const=None,
        defarg=None,
        arg=1,            # 引数の数 [1: 引数を1つ取る（デフォルト）, 0: 引数なし, ?: 1つ取るが省略可能（キー自体が存在する場合はvalueの値がデフォルト値になる）]
        remainder=False,  # 書式を無視して以降をすべて引数とする
        accumulate=False, # オプションの重複を許し、値を集積する方法を指定する
        default=None,     # キーが存在しない場合のデフォルト値
        value=None,       # キーに対する引数のデフォルト値
        dest=None,
        methodtype=None,
        foreach=None,     # OPT_FOREACHTARGETを付すかトルか：valuetypeのデフォルト値を上書きする
        help=""
    ):
        if not names:
            raise ValueError("At least 1 name must be specified")

        flags = 0
        typespec = None
        accumulatespec = None

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
            typespec = typeof_argument("str")
            
        if accumulate:
            if accumulate is True:
                accumulatespec = ArgAppender
            elif callable(accumulate):
                accumulatespec = accumulate
            elif accumulate == "count":
                accumulatespec = ArgCounter
                arg = 0 # 引数は無視される
            else:
                raise ValueError("Bad argument for 'accumulate': must be boolean or callable")
            
            if default is None:
                sig = signature(accumulatespec)
                if "initial" in sig.parameters:
                    default = sig.parameters["initial"].default
            elif not callable(default):
                raise ValueError("Bad default value for 'accumulative' option: must be nullary callable")

        if arg == "?":
            flags |= OPT_OPTIONAL_UNARY
        elif arg == 0 or arg == "0":
            flags |= OPT_NULLARY
        elif arg == 1 or arg == "1":
            flags |= OPT_UNARY
        else:
            raise ValueError("bad arity '{}'".format(arg))

        if typespec is None:
            if isinstance(valuetype, ArgType):
                typespec = valuetype
            else:
                typespec = typeof_argument(valuetype)

        if methodtype is not None:
            flags |= OPT_METHOD(methodtype)
        else:
            flags |= OPT_METHOD_TARGET
        
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

        if typespec.is_sequence_type():
            if foreach is None and (flags & OPT_POSITIONAL) > 0:
                flags |= OPT_SEQUENCEFOREACH
            elif foreach:
                flags |= OPT_SEQUENCEFOREACH
            elif not foreach:
                flags |= OPT_SEQUENCETOP
        elif typespec.is_compound_type():
            if foreach:
                flags |= OPT_SEQUENCEFOREACH
            else:
                flags |= OPT_SEQUENCEASVALUE
    
        #
        cxt = OptionContext(longnames, shortnames, 
            valuetype=typespec, value=value, default=default, 
            dest=dest, flags=flags, accumulator=accumulatespec,
            help=help
        )

        dest = cxt.get_dest()
        if cxt.is_positional():
            if self.positional is not None:
                raise ValueError("positional argument must be one")
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
    def generate_parsing_candidates(self, commands: Sequence[str], compound=False) -> List[TokenRow]:
        # 可能な全てのコマンド解釈を展開する
        command_rows: List[TokenRow] = []

        for command in commands:
            if self._prefix_length(command) == 1:
                addrows = self._optiontrie.parse(command[1:])
                if not addrows:
                    # オプションとして解釈できなくても、そのままにしておく
                    addrows = [[command]]
            elif compound:
                addrows = self._optiontrie.parse(command)
                if not addrows:
                    # 抱合オプションが解釈できなかった場合、引数と考える
                    addrows = [[command]]
            else:
                # 長いオプション名や値はそのまま追加する
                addrows = [[command]]

            command_rows = product_candidates(command_rows, (), addrows)
        
        return command_rows

    def parse_args(self, commandrow, spirit=None):
        # コマンドを解析し結果を作成する     
        try:
            kwargs = self.do_parse_args(commandrow, spirit)
            res = self.build_parse_result(self.display_command_row(commandrow), kwargs)
        except BadCommand as e:
            raise e
        return res
    
    def do_parse_args(self, args, spirit=None):        
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
                newcxt = "<eval>"

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
                newcxt = "<eval>"
                
            # 新たなオプションが開始した：前のコンテキストと引数を解決する
            if newcxt:
                if curcxt is None and argstack:
                    # コマンドの先頭に置かれた引数
                    if self.positional is not None:
                        # 位置引数とみなす
                        curcxt = self.positional
                    else:
                        # 位置引数が存在しないので、解決不能
                        raise BadCommand("予期しない引数'{}'を解釈できません".format(arg))
                
                if curcxt is not None:
                    # 現在のコンテキストを終了し、新しいコンテキストを開始する
                    contexts.append((curcxt, argstack))
                    argstack = []
                
                if newcxt == "<eval>":
                    curcxt = None
                else:
                    curcxt = newcxt

        # 引数をチェックする
        postposit = True
        missing_posit_arg = None
        for i, (cxt, stack) in enumerate(contexts):   
            if cxt is self.positional and self.positional is not None:
                if cxt.is_unary() and not stack:
                    # 中間に置かれていると考える
                    continue
                postposit = False

            if cxt.is_nullary() and stack:
                # 引数が多すぎる
                if i == len(contexts)-1 and postposit:
                    missing_posit_arg = stack.copy() # 後置された位置引数とみなし、移し返る
                    stack.clear()
                else:
                    raise BadCommand("予期しない引数'{}'を解釈できません".format(arg))

            elif cxt.is_unary() and not stack:
                # 引数が少なすぎる
                raise BadCommand("オプション<{}>に必要な引数がありません".format(cxt.make_key(self.prefix_chars[0])))

        if postposit and self.positional is not None:
            # 後置の位置引数
            contexts = [(x,a) for x,a in contexts if x is not self.positional]
            if missing_posit_arg:
                contexts.append((self.positional, missing_posit_arg))
            elif not any(x is self.positional for x,_ in contexts) and self.positional.is_unary():
                # 必要な位置引数が無い
                raise BadCommand("位置引数<{}>に相当する引数がありません".format(self.positional.get_name()))

        # 引数の文字列を値へと変換する
        kwargs = {}
        appeared = set()
        for cxt, stack in contexts:  
            # 値を生成する
            argstring = ArgString(stack)
            cxt.parse_arg(argstring, kwargs, spirit)
            # 出現したコンテキストを記録する
            appeared.add(cxt.get_dest())
        
        # デフォルト引数で埋める
        for name, cxt in self.argnames.items():
            if name not in appeared:
                cxt.parse_default(kwargs, spirit)

        return kwargs
        
    def build_parse_result(self, expanded_command, kwargs):
        # パース済みの値を操作するクラスを作成
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
        # TODO: flagsで指定される属性も含めて、明記するよう、完成させること
        lines = []
        for cxt in self.list_contexts():
            line = "{} [{}]  {}".format(" ".join(cxt.make_keys("-")), cxt.get_value_typename(), cxt.get_help())
            lines.append(line)
        return lines

#
def product_candidates(head: Sequence[TokenRow], midvalues: Sequence[Token], tail: Sequence[TokenRow]) -> List[TokenRow]:
    newrows: List[TokenRow] = []
    for headrow in (head or [[]]):
        for tailrow in (tail or [[]]):
            newrows.append([*headrow, *midvalues, *tailrow])
    return newrows

#
# O
#
class CommandParserResult():
    def __init__(self, expandedcmd, *, messages=None):
        self.expandedcmd: str = expandedcmd
        self.messages: List[str] = messages or []
        self.argmap: DefaultDict[int, Dict[str, Tuple[OptionContext, str]]] = defaultdict(dict)
        self.foreach_expands_context: Optional[OptionContext] = None
    
    def get_expanded_command(self):
        return self.expandedcmd
    
    def reproduce_command(self):
        # expandedcmd + argmapからコマンドを再現する
        head = self.expandedcmd.split()[0]
        raise NotImplementedError()

    def has_exit_message(self):
        return True if self.messages else False
    
    def get_exit_messages(self):
        return self.messages
        
    def add_arg(self, cxt, name, value):
        if cxt.expands_foreach():
            if self.foreach_expands_context is None:
                self.foreach_expands_context = cxt
            else:
                raise ValueError("argument foreach expansion is allowed only once (for now)")
        elif cxt.expands_top():
            value = next(iter(value), None)
            
        at = cxt.get_dest_method()
        self.argmap[at][name] = (cxt, value)
    
    def reproduce_arg(self, name):
        entry = None
        for _destmethod, argmap in self.argmap.items():
            if name in argmap:
                entry = argmap[name]
                break
        else:
            return None, None
        
        cxt, value = entry
        if cxt.expands_foreach() and cxt is self.foreach_expands_context:
            v = "\n".join([str(x) for x in value])
        elif cxt.expands_top():
            v = next(iter(value), None)
        else:
            v = value
        return str(v), cxt

    def get_values(self, label = None, *, argmap = None):
        if argmap is None:
            argmap = self.argmap[OPT_METHOD(label)]
        return {key:val for key,(_cxt,val) in argmap.items()}

    # 呼び出し引数を展開する
    def prepare_arguments(self, label):
        at = OPT_METHOD(label)
        argmap = self.argmap[at].copy()

        foreach_expansion = None
        if self.foreach_expands_context and self.foreach_expands_context.get_dest_method() == at:
            valuename = self.foreach_expands_context.get_dest()
            _, values = argmap[valuename]
            foreach_expansion = iter(values) # require Iterable value. If not, exception is raised here.

        if foreach_expansion is not None:
            for a_target in foreach_expansion:
                argmap[valuename] = (self.foreach_expands_context, a_target)
                yield self.get_values(argmap=argmap)
        else:
            yield self.get_values(argmap=argmap)

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

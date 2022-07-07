#!/usr/bin/env python3
# coding: utf-8

import inspect
import sys
import dis
import traceback
import types
import pprint

from machaon.core.message import InternalMessageError
from machaon.cui import collapse_text, composit_text
from machaon.core.symbol import full_qualified_name

class ErrorObject():
    """ @type [Error]
    プロセスの実行時に起きたエラー。
    """
    def __init__(self, error, *, context=None):
        self.error = error
        self.context = context
    
    def get_error(self):
        if isinstance(self.error, InternalMessageError):
            return self.error.error
        else:
            return self.error
    
    def get_error_typename(self):
        """ @method alias-name [error_typename]
        例外の型名。
        Returns:
            Str:
        """
        err = self.get_error()
        return err.__class__.__name__
    
    def traceback(self, level=0):
        """ @method [tb]
        トレースバック
        Params:
            level?(int): トレースバックの深度
        Returns:
            TracebackObject:
        """
        err = self.get_error()
        if level == 0:
            return TracebackObject(err)
        else:
            return TracebackObject(err).dive(level)
    
    def lasttraceback(self):
        """ @method [lasttb]
        最も深いトレースバック
        Returns:
            TracebackObject:
        """
        err = self.get_error()
        return TracebackObject(err).dive()

    def get_context(self):
        """ @method alias-name [context]
        関連づけられたコンテキストを得る。
        Returns:
            Context:
        """
        return self.context

    def display(self):
        """ @method 
        エラー内容を表示する。
        Returns:
            Str:
        """
        excep = self.get_error()
        return "".join(traceback.format_exception(type(excep), excep, excep.__traceback__))
    
    def display_exception(self):
        """ @method 
        一行で例外名のみを表示する。
        Returns:
            Str:
        """
        excep = self.get_error()
        return traceback.format_exception_only(type(excep), excep)[0]
        
    def short_display(self):
        """ @method 
        例外名と、最初と最後のフレームのみを表示する。
        Returns:
            Str:
        """
        excep1 = self.get_error()

        lines = []
        errlines = traceback.format_exception_only(type(excep1), excep1)
        lines.extend([x.rstrip() for x in errlines])
        
        excep2 = self.cause().get_error()
        if excep1 is excep2:
            frames = traceback.extract_tb(excep1.__traceback__)
            first = frames[0]
            last = frames[-1]
        else:
            frames1 = traceback.extract_tb(excep1.__traceback__)
            first = frames1[0]
            frames2 = traceback.extract_tb(excep2.__traceback__)
            last = frames2[-1]
        
        lines.extend([x.rstrip() for x in traceback.format_list([first])])
        lines.append("    ...    ")
        lines.extend([x.rstrip() for x in traceback.format_list([last])])
        return "\n".join(lines)
    
    def cause(self):
        """ @method 
        元のエラーを取得する。
        Returns:
            Error:
        """
        err = self.get_error()
        while True: 
            cause = err.__cause__
            if cause is None:
                break
            err = cause
        return ErrorObject(err, context=self.context)

    def log(self, app):
        """ @task
        メッセージ解析器のログを表示する。
        """
        if self.context is None:
            raise ValueError("コンテキストが関連づけられていません")
        self.context.pprint_log_as_message(app)

    def constructor(self, context, value):
        """ @meta context
        例外オブジェクトからの変換をサポート
        Params:
            builtins.Exception:
        """
        return ErrorObject(value, context=context)
    
    def stringify(self):
        """ @meta """
        p, lno = self.lasttraceback().location()
        if isinstance(self.error, InternalMessageError):
            error = self.cause().get_error()
            return "文法エラー：{}[{}] ({}, {})".format(str(error), self.get_error_typename(), p, lno)
        else:
            error = self.cause().get_error()
            return "実行エラー：{}[{}] ({}, {})".format(str(error), self.get_error_typename(), p, lno)

    def summarize(self):
        """ @meta """
        return self.stringify() # 文字幅による省略を行わない

    def pprint(self, app):
        """ @meta """
        if isinstance(self.error, InternalMessageError):
            title = "（内部エラー）"
        else:
            title = ""
        
        excep = self.cause().get_error()
        app.post("error", self.display_exception())

        app.post("message-em", "スタックトレース{}：".format(title))
        msg = verbose_display_traceback(excep, app.get_ui_wrap_width(), "short")
        app.post("message", msg + "\n")

        app.post("message-em", "詳細情報は次のメソッドで：".format(title))
        app.post("message", "log")
        app.post("message", "tb [level]")
        app.post("message", "tb [level] var [varname]")
        app.post("message", "tb [level] showall")


#
#
#
class TracebackObject():
    """ @type
    トレースバック。
    """
    def __init__(self, tb_or_error, error=None):        
        if isinstance(tb_or_error, Exception):
            self._tb = tb_or_error.__traceback__
            self._error = tb_or_error
        else:
            self._tb = tb_or_error
            self._error = error

        if not isinstance(self._tb, types.TracebackType):
            raise TypeError("TracebackObject requires TracebackType, but {}".format(self._tb))
    
    def error(self):
        """ @method
        発生したエラー
        Returns:
            Error:
        """
        return self._error
    
    def dive(self, level=None):
        """ @method
        任意の深さのトレースバックを得る
        Params:
            level(int): Noneで最後まで潜る
        Returns:
            TracebackObject:
        """
        if level is None:
            tb = self._tb
            for _, tb, _ in self.walk(): pass
            return tb
        else:
            if level < 1:
                raise ValueError("レベルは1から開始します")
            for l, tb, _ in self.walk():
                if level == l:
                    return tb
            raise ValueError("トレースバックの深さの限界に到達")
        
    def next(self):
        """ @method
        1つ深いトレースバックを得る
        Returns:
            TracebackObject:
        """
        return self.dive(1)

    def walk(self):
        """ 深いトレースバックをめぐる 
        Yields:
            Int, TracebackObject, TracebackObject
        """
        def next_nested_traceback(exc):
            if hasattr(exc, "child_exception"):
                e = exc.child_exception()
                if e:
                    return e.__traceback__, e
            return None, exc

        tb = self._tb
        exception = self._error

        if tb is None and exception is not None:
            tb, exception = next_nested_traceback(exception)
        
        level = 0
        while tb:
            nexttb = tb.tb_next
            yield level, TracebackObject(tb, exception), (TracebackObject(nexttb) if nexttb else None)
            if nexttb is None and exception is not None:
                nexttb, exception = next_nested_traceback(exception)
            tb = nexttb
            level += 1

    def frame(self):
        """ @method
        トレースバックのフレームオブジェクト
        Returns:
            FrameObject:
        """
        return FrameObject(self._tb.tb_frame)
    
    def func(self):
        """ @method
        関数名
        Returns:
            Str:
        """
        return self.frame().funcname()

    def get_variable(self, name):
        """ @method [var]
        変数を取得する
        Params:
            name(str):
        Returns:
            Any:
        """
        return self.frame().get_variable(name)

    def get_variables(self, lastoffset=None):
        """ @method [vars]
        フレームで使用された変数の一覧 
        Returns:
            ObjectCollection:
        """
        return self.frame().get_variables(lastoffset)

    def get_variable_names(self, lastoffset=None):
        """ @method [var-names]
        フレームで使用された変数の一覧 
        Returns:
            Tuple:
        """
        return self.frame().get_variable_names(lastoffset)

    def location(self):
        """ @method
        現在実行中のファイル内の場所
        Returns:
            TextPath:
        """
        return (self.frame().filepath(), self._tb.tb_lineno)
    
    def lasti(self):
        """ @method
        現在実行中のバイトコードのインデックス
        Returns:
            Int:
        """
        return self._tb.tb_lasti

    def instructions(self):
        """ @method
        現在の実行箇所までのバイトコード
        Returns:
            Sheet[ObjectCollection](op, arg, location):
        """
        return self.frame().instructions(self._tb.tb_lasti)

    def showthis(self, app):
        """ @task
        このトレースバックの情報を表示する
        """
        for line in display_this_traceback(self, app.get_ui_wrap_width()):
            app.post("message", line)        

    def showall(self, app):
        """ @task
        全ての下位のトレースバックの情報を表示する
        """
        excep = self._error
        msg = verbose_display_traceback(excep, app.get_ui_wrap_width())
        app.post("message", msg)

    def display(self, app):
        excep = self._error
        return verbose_display_traceback(excep, app.get_ui_wrap_width())

    def constructor(self, value):
        """ @meta
        Params:
            types.TracebackType | Exception
        """
        return TracebackObject(value)
    
    def stringify(self):
        """ @meta
        """
        return "<TracebackObject at {}, {}>".format(*self.location())

    def pprint(self, app):
        """ @meta
        """
        self.showthis(app)


class FrameObject:
    """ @type
    フレームオブジェクトおよびコードオブジェクト
    """
    def __init__(self, frame):
        self._fr = frame
    
    def code(self):
        """ コードオブジェクト """
        return self._fr.f_code

    def back(self):
        """ @method
        呼び出し元のフレームオブジェクト
        Returns:
            FrameObject:
        """
        return FrameObject(self._fr.f_back)

    def filepath(self):
        """ @method
        実行中のモジュールのファイル名
        Returns:
            Path:
        """
        return self._fr.f_code.co_filename
    
    def lastline(self):
        """ @method
        フレームの最後の行番号
        Returns:
            TextPath:
        """
        return self._fr.f_lineno
    
    def lastinstr(self):
        """ """
        return self._fr.f_lasti

    def funcname(self):
        """ @method
        関数名
        Returns:
            Str:
        """
        return self._fr.f_code.co_name

    def _loader_context(self):
        return _InstrContext(
            locals=self._fr.f_locals, 
            globals=self._fr.f_globals, 
            builtins=self._fr.f_builtins
        )

    def get_variable(self, name):
        """ @task [var] 
        変数を取得する。
        Params:
            name(str): 変数名、ピリオドで区切った属性名
        Returns:
            Any:
        """
        ins = None
        for attr in name.split("."):
            if ins is None:
                ins = _InstrGetVar(attr)
            else:
                ins = _InstrGetAttr(ins, attr)
        cxt = self._loader_context()
        return ins.resolve(cxt)

    def get_variables(self, lastoffset=None):
        """ @task [vars]
        フレームで使用されたすべての変数を取得する 
        Returns:
            ObjectCollection:
        """
        dic = {}
        cxt = self._loader_context()
        for va in disasm_variable_instructions(self._fr.f_code, lastoffset):
            va.loadvar(dic, cxt)
        return dic

    def get_variable_names(self, lastoffset=None):
        """ @task [var-names]
        フレームで使用されたすべての変数の名前を取得する 
        Returns:
            Tuple[Str]:
        """
        for va in disasm_variable_instructions(self._fr.f_code, lastoffset):
            yield va.name()

    def get_local_variables(self):
        """ @method [locals]
        ローカル変数を取得する
        Returns:
            ObjectCollection:
        """
        return self._fr.f_locals

    def get_global_variables(self):
        """ @method [globals]
        グローバル変数を取得する
        Returns:
            ObjectCollection:
        """
        return self._fr.f_globals

    def instructions(self, lastoffset=None):
        """ @method
        バイトコードの命令を表示する
        Returns:
            Sheet[ObjectCollection](op, arg, location):
        """
        check_cpython()
        lines = []
        for instr in dis.get_instructions(self._fr.f_code):
            if lastoffset is not None and instr.offset > lastoffset:
                break
            location = ""
            if instr.starts_line is not None:
                location = "line {} at {}".format(instr.starts_line, self._fr.f_code.co_filename)
            lines.append({
                "op" : instr.opname,
                "arg" : instr.argrepr,
                "location" : location
            })
        return lines

    def constructor(self, value):
        """ @meta
        Params:
            types.FrameType:
        """
        return FrameObject(value)
    
    def stringify(self):
        """ @meta
        """
        return "<FrameObject at {}, {}>".format(self.filepath, self.lastline)


def display_this_traceback(tb: TracebackObject, linewidth, showtype=None, level=None, printerror=False):
    """
    トレースバックオブジェクトの情報を表示する。
    Params:
        tb(TracebackObject): トレースバックオブジェクト
        linewidth(Optional[int]): 折り返しの幅
        showtype(Optional[str]): 表示タイプ [None(full)|short]
    """
    frame = tb.frame()

    # ソースファイルにおける場所
    filename, lineno = tb.location()
    msg_location = "{}, {}行目".format(filename, lineno)
    if level is not None:
        msg_location = "[{}] {}".format(level, msg_location)

    import linecache
    msg_line = linecache.getline(filename, lineno).strip()

    # selfなどから実行関数のシグニチャを得る
    fnname = frame.funcname()
    fn = find_code_function(frame.code(), fnname, frame.get_local_variables(), frame.get_global_variables())
    if fn is None or fn.is_property():
        msg_fn = "{}:".format(fnname)
    else:
        try:
            msg_fn = "{}{}:".format(fn.display_funcname(), fn.display_parameters())
        except Exception as e:
            msg_fn = "{}(<inspect error: {}>):".format(fnname, e)

    # 例外の発生を表示する
    msg_excep = ""
    if printerror:
        msg_excep = ErrorObject(tb.error()).display_exception()

    indent = "  "
    lines = []

    # 行
    lines.append(msg_location)
    if showtype is None:
        # ソース
        lines.append(indent + msg_fn)
        lines.append("")
        lines.append(indent + indent + msg_line)
        lines.append("")
        
        # インストラクション
        #for instr in frame.instructions(tb.lasti()):
        #    line = "{op:12} ({arg:})    {location:}".format(**instr)
        #    lines.append(indent + indent + line)
        #lines.append("")
        
        # ローカル変数
        lines.append(indent + "-" * 30)

        tb_vars = frame.get_variables(tb.lasti())
        for name, val in tb_vars.items():
            for l in display_variable(name, val, linewidth):
                lines.append(indent + l)
        
        lines.append(indent + "-" * 30)

        # 発生した例外
        if msg_excep:
            lines.append("E" + indent[1:] + msg_excep)
    
    elif showtype == "short":
        # ソース
        lines.append(indent + msg_fn)
        lines.append(indent + indent + msg_line)

        # インストラクション
        if printerror:
            instrs = frame.instructions(tb.lasti())
            if instrs:
                line = "{op} ({arg:})".format(**instrs[-1])
                lines.append(indent + indent + line)

        # 発生した例外
        if msg_excep:
            lines.append("E" + indent[1:] + msg_excep)

    return lines


def verbose_display_traceback(exception, linewidth=0xFFFFFF, showtype=None):
    """
    Params:
        exception(Exception): 例外オブジェクト
        linewidth(Optional[int]): 折り返しの幅
        showtype(Optional[str]): 表示タイプ [None(full)|short]
    """
    lines = []
    tbtop = TracebackObject(exception)
    for level, tb, nexttb in tbtop.walk():
        newls = display_this_traceback(tb, linewidth, showtype, level, printerror=(nexttb is None))
        lines.extend(newls)
        if showtype is None:
            lines.append("\n")
    return '\n'.join(lines)


def print_exception_verbose(exception, linewidth=0xFFFFFF):
    # デバッグ用
    line = ErrorObject(exception).display_exception()
    print(line)
    
    print("スタックトレース：")
    disp = verbose_display_traceback(exception, linewidth) # フル
    print(disp)


#
#
# disasm
#
#

def check_cpython():
    if sys.implementation.name != "cpython":
        raise ValueError("CPython以外ではサポートされない動作です")


class UndefinedValue:
    def __init__(self, kind, name):
        self.msg = "{} '{}'".format(kind, name)
    
    def __repr__(self):
        return "<Undefined {}>".format(self.msg)


class _InstrContext:
    """ インストラクションの値を取得する """
    def __init__(self, *, locals, globals, builtins=None):
        self.locals = locals
        self.globals = globals
        if builtins is None:
            builtins = self.globals.get("__builtins__", {})
        self.builtins = builtins
        self.memo = {}

    def get_local(self, name):
        if name in self.locals:
            return self.locals[name]
        else:
            return UndefinedValue("local", name)

    def get_global(self, name):
        if name in self.globals:
            return self.globals[name]
        elif name in self.builtins:
            return self.builtins[name]
        else:
            return UndefinedValue("global", name)

    def get(self, name):
        v = self.get_local(name)
        if isinstance(v, UndefinedValue):
            return self.get_global(name)
        else:
            return v

    def get_memo(self, name):
        if name in self.memo:
            return self.memo[name]
        else:
            return UndefinedValue("","")
    
    def set_memo(self, name, value):
        self.memo[name] = value

class _InstrGetLocal:
    """ ローカル変数の参照 """
    def __init__(self, name):
        self.name = name

    def valname(self):
        return self.name

    def resolve(self, context):
        return context.get_local(self.name)

class _InstrGetGlobal:
    """ グローバル変数の参照 """
    def __init__(self, name):
        self.name = name

    def valname(self):
        return self.name

    def resolve(self, context):
        return context.get_global(self.name)

class _InstrGetVar:
    """ ローカル変数 -> グローバル変数の順に参照 """
    def __init__(self, name):
        self.name = name

    def valname(self):
        return self.name

    def resolve(self, context):
        return context.get(self.name)

class _InstrGetAttr:
    """ 属性値の参照 """
    def __init__(self, instr, name):
        self.instr = instr
        self.name = name

    def valname(self):
        parent = self.instr.valname()
        if parent is None:
            parent = "<error>"
        return "{}.{}".format(parent, self.name)

    def resolve(self, context):
        val = self.instr.resolve(context)
        if hasattr(val, self.name):
            return getattr(val, self.name)
        else:
            return UndefinedValue("getattr", self.name)

class _InstrConst:
    """ リテラル定数の参照 """
    def __init__(self, val):
        self.val = val
    
    def valname(self):
        return None

    def resolve(self, _context):
        return self.val
    

class _InstrStackError:
    def __init__(self):
        pass
    
    def valname(self):
        return None
    
    def resolve(self, _context):
        return UndefinedValue("<stack error>", "")
        

class VariableInstruction:
    def __init__(self, instr):
        self.instr = instr

    def name(self):
        return self.instr.valname()

    def load(self, context):
        name = self.instr.valname()
        if name is None:
            val = self.instr.resolve(self)
            return val

        val = context.get_memo(name)
        if isinstance(val, UndefinedValue):
            val = self.instr.resolve(context)
            context.set_memo(name, val)
        return val

    def loadvar(self, dict, context):
        dict[self.name()] = self.load(context)


def disasm_variable_instructions(code, last_instr_offset=None):
    """
    コードオブジェクトのバイトコードを解析し、ローカル・グローバル変数から命令で使用した変数を収集する
    Returns:
        List[VariableInstruction]
    """
    check_cpython()
    stack = []
    instrs = []
    for instr in dis.get_instructions(code):
        if last_instr_offset is not None and instr.offset > last_instr_offset:
            break

        if instr.opname == "LOAD_GLOBAL":
            varname = instr.argval
            var = _InstrGetGlobal(varname)
            stack.append(var)
            instrs.append(var)
        
        elif instr.opname == "LOAD_FAST":
            varname = instr.argval
            var = _InstrGetLocal(varname)
            stack.append(var)
            instrs.append(var)
        
        elif instr.opname == "LOAD_ATTR":
            varname = instr.argval
            if stack:
                top = stack.pop()
            else:
                top = _InstrStackError()
            var = _InstrGetAttr(top, varname)
            instrs.append(var)
            if stack:
                stack[-1] = var # スタックの頂点を置き換える
            else:
                stack.append(var)
                
        elif instr.opname == "LOAD_CONST":
            value = instr.argval
            stack.append(_InstrConst(value)) # 名前が無いのでinstrsには載せない

        elif instr.opname == "LOAD_DEREF": # 自由変数を参照する
            varname = instr.argval
            var = _InstrGetVar(varname)
            stack.append(var)
            instrs.append(var)

        else:
            # その他の命令は、スタックの増減だけ反映する
            try:
                stk = dis.stack_effect(instr.opcode, instr.arg)
            except:
                continue # 再帰的に呼び出されるとエラーになる？
            if stk > 0:
                stack.extend((_InstrStackError() for _ in range(stk)))
            elif stk < 0:
                stack = stack[:stk]
    
    return [VariableInstruction(x) for x in instrs]


def display_variable(name, value, linewidth):
    """
    与えられた変数を表示する
    Params:
        dictionary(dict[str, Any]): 変数の辞書
        linewidth(Optional[int]): 表示幅
    Returns:
        List[str]: 
    """
    try:
        if isinstance(value, UndefinedValue):
            val_str = "<undefined>"
        elif type(value).__repr__ is object.__repr__:
            if hasattr(value, "stringify"):
                val_str = "<{} {}>".format(full_qualified_name(type(value)), value.stringify())
            else:
                val_str = "<{}>".format(full_qualified_name(type(value)))
        else:
            val_str = pprint.pformat(value, width=linewidth)
        
    except Exception as e:
        err = collapse_text(str(e), width=linewidth)
        val_str = "<error on pprint.pformat: {}>".format(err)
    
    vallines = collapse_text(val_str, linewidth).splitlines()

    lines = []
    lines.append("{} = {}".format(name, vallines[0]))
    for l in vallines[1:]:
        lines.append(" " * (len(name) + 3) + l)
    return lines


def find_code_function(code, fnname, locals, globals):
    """
    Params:
        code(types.CodeType): コードオブジェクト
        fnname(str): 関数名
        locals(dict): ローカル変数の辞書
        globals(dict): グローバル変数の辞書
    """
    # インスタンスメソッド
    selfobj = locals.get("self", None)
    if selfobj is not None:
        # プロパティ
        selftype = type(selfobj)
        cfn = getattr(selftype, fnname, None)
        if cfn is not None:
            if isinstance(cfn, property):
                return FunctionInfo(cfn, 4, None, selfobj)
            # メソッド
            fn = getattr(selfobj, fnname, None)
            if fn.__code__ is code:
                return FunctionInfo(fn, 0, "self", selfobj)
    
    # クラスメソッド
    clsobj = None
    for candname in ("cls", "klass"):
        clsobj = locals.get(candname, None)
        if clsobj is not None: break
    if clsobj is not None:
        cfn = getattr(clsobj, fnname, None)
        if cfn and cfn.__code__ is code:
            return FunctionInfo(cfn, 1, candname, clsobj)

    # グローバル関数
    gfn = globals.get(fnname, None)
    if gfn and getattr(gfn,"__code__",None) is code:
        return FunctionInfo(gfn, 2)

    # staticmethodは検知できない
    return None


class FunctionInfo:
    def __init__(self, fn=None, type=2, bound_name=None, bound_object=None):
        self.fn = fn
        self.type = type
        if self.type < 0 or 4 < self.type:
            raise ValueError()
        self.bound_name = bound_name
        self.bound_object = bound_object
    
    def is_method(self):
        return self.type == 0
    
    def is_classmethod(self):
        return self.type == 1
    
    def is_function(self):
        return self.type == 2
    
    def is_staticmethod(self):
        return self.type == 3

    def is_property(self):
        return self.type == 4
    
    def display_funcname(self):
        if self.is_method() or self.is_property():
            return "{}.{}".format(type(self.bound_object).__name__, self.fn.__name__)
        elif self.is_classmethod():
            return "{}.{}".format(self.bound_object.__name__, self.fn.__name__)
        else:
            return self.fn.__name__

    def display_parameters(self):
        try:
            sig = inspect.signature(self.fn)
        except:
            return "<シンタックスを得られません>"
        params = []
        if self.bound_name:
            params.append(self.bound_name)
        for p in sig.parameters.values():
            if p.default == inspect.Parameter.empty:
                params.append(p.name)
            else:
                params.append("{} = {}".format(p.name, p.default))
        return "({})".format(", ".join(params))
        

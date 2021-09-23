#!/usr/bin/env python3
# coding: utf-8

import inspect
import sys
import dis
import traceback

from machaon.core.message import InternalMessageError
from machaon.cui import collapse_text, composit_text
from machaon.core.symbol import full_qualified_name

class ErrorObject():
    """
    プロセスの実行時に起きたエラー。
    """
    def __init__(self, context, error):
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
    
    def traceback(self, level):
        """ @method [tb]
        トレースバック
        Params:
            level(int): トレースバックの深度
        Returns:
            TracebackObject:
        """
        err = self.get_error()
        if level == 0:
            return TracebackObject(err)
        else:
            return TracebackObject(err).dive(level)

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
    
    def display_line(self):
        """ @method 
        一行でエラー内容を表示する。
        Returns:
            Str:
        """
        excep = self.get_error()
        return traceback.format_exception_only(type(excep), excep)[0]
    
    def parser_log(self, app):
        """ @task
        メッセージ解析器のログを表示する。
        """
        self.context.pprint_log_as_message(app)

    def constructor(self, context, value):
        """ @meta 
        例外オブジェクトからの変換をサポート
        Params:
            builtins.Exception:
        """
        return ErrorObject(context, value)
    
    def stringify(self):
        """ @meta """
        if isinstance(self.error, InternalMessageError):
            error = self.error.error
            return "文法エラー：{}[{}]".format(str(error), self.get_error_typename())
        else:
            error = self.error
            return "実行エラー：{}[{}]".format(str(error), self.get_error_typename())

    def pprint(self, app):
        """ @meta """
        if isinstance(self.error, InternalMessageError):
            excep = self.error.error
            title = "（内部エラー）"
        else:
            excep = self.error
            title = ""
        
        app.post("error", self.display_line())

        app.post("message-em", "スタックトレース{}：".format(title))
        msg = verbose_display_traceback(excep, app.get_ui_wrap_width(), "short")
        app.post("message", msg + "\n")

        app.post("message-em", "詳細情報は次のメソッドで：".format(title))
        app.post("message", "parser-log")
        app.post("message", "traceback [level]")
        app.post("message", "traceback [level] showall")


#
#
#
class TracebackObject():
    """
    トレースバックオブジェクト
    """
    def __init__(self, tb_or_error, error=None):        
        if isinstance(tb_or_error, Exception):
            self._tb = tb_or_error.__traceback__
            self._error = tb_or_error
        else:
            self._tb = tb_or_error
            self._error = error
    
    def error(self):
        """ @method
        Returns:
            Error:
        """
        return self._error
    
    def dive(self, level):
        """ @method
        Params:
            level(int):
        Returns:
            TracebackObject:
        """
        if level < 1:
            raise ValueError("レベルは1から開始します")
        for l, tb, _ in self.walk():
            if level == l:
                return tb
        raise ValueError("トレースバックの深さの限界に到達")
        
    def next(self):
        """ @method
        Returns:
            TracebackObject:
        """
        return self.dive(1)

    def walk(self):
        """ より深いトレースバックへ 
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
        トレースバックのフレームオブジェクトを返す
        Returns:
            FrameObject:
        """
        return FrameObject(self._tb.tb_frame)
    
    def location(self):
        """ @method
        現在実行中のファイル内の場所
        Returns:
            TextPath:
        """
        return (self.frame().filepath(), self._tb.tb_lineno)
    
    def lasti(self):
        """ @method
        現在実行中のファイル内の場所
        Returns:
            Int:
        """
        return self._tb.tb_lasti

    def cur_instructions(self):
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
        msg = display_this_traceback(self, app.get_ui_wrap_width())
        app.post("message", msg)        

    def showall(self, app):
        """ @task
        全ての下位のトレースバックの情報を表示する
        """
        excep = self._error
        msg = verbose_display_traceback(excep, app.get_ui_wrap_width())
        app.post("message", msg)

    def constructor(self, _context, value):
        """ @meta
        Params:
            types.TracebackType | Exception
        """
        return TracebackObject(value)
    
    def stringify(self):
        """ @meta
        """
        return "<TracebackObject at {}, {}>".format(*self.location())


class FrameObject:
    """
    フレームオブジェクト・コードオブジェクト
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
    
    def func(self):
        """ @method
        関数オブジェクト
        Returns:
            Any:
        """
        fn = self._fr.f_trace
        instr = None
        print("")

    def get_using_variables(self, lastoffset=None):
        """ @method [vars]
        フレームで使用した変数を取得する 
        Returns:
            ObjectCollection:
        """
        return disasm_instruction_variables(self._fr.f_code, self._fr.f_globals, self._fr.f_locals, lastoffset)

    def get_local_variables(self):
        """ @method [locals]
        ローカル変数を取得する
        Returns:
            ObjectCollection:
        """
        return self._fr.f_locals

    def get_global_variables(self):
        """ @method [locals]
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
            location = None
            if instr.starts_line is not None:
                location = "line {} at {}".format(instr.starts_line, self._fr.f_code.co_filename)
            lines.append({
                "op" : instr.opname,
                "arg" : instr.argrepr,
                "location" : location
            })
        return lines


def display_this_traceback(tb, linewidth, showtype=None, level=None, printerror=False):
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
    
    # 関連する変数を表示する
    tb_locals = frame.get_using_variables(tb.lasti())
    msg_locals = display_variables(tb_locals, linewidth)

    # 例外の発生を表示する
    msg_excep = ""
    if printerror:
        msg_excep = ErrorObject(None, tb.error()).display_line()

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
        # ローカル変数
        lines.append(indent + "-" * 30)
        for line in msg_locals:
            lines.append(indent + line)
        lines.append(indent + "-" * 30)
        # 発生した例外
        if msg_excep:
            lines.append("E" + indent[1:] + msg_excep)
    
    elif showtype == "short":
        # ソース
        lines.append(indent + msg_fn)
        lines.append(indent + indent + msg_line)
        # 発生した例外
        if msg_excep:
            lines.append("E" + indent[1:] + msg_excep)

    return lines


def verbose_display_traceback(exception, linewidth, showtype=None):
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


def check_cpython():
    if sys.implementation.name != "cpython":
        raise ValueError("CPython以外ではサポートされない動作です")


class UNDEFINED:
    pass

def disasm_instruction_variables(code, globaldict, localdict, last_instr_offset=None):
    """
    コードオブジェクトのバイトコードを解析し、ローカル・グローバル変数から命令で使用した変数を収集する
    Returns:
        Dict[str, Any]: 変数の辞書
    """
    check_cpython()
    stack = []
    vardict = {}
    for instr in dis.get_instructions(code):
        if last_instr_offset is not None and instr.offset > last_instr_offset:
            break

        if instr.opname == "LOAD_GLOBAL":
            varname = instr.argval
            if varname in vardict:
                varval = vardict[varname]
            else:
                if varname in globaldict:
                    varval = globaldict[varname]
                    vardict[varname] = varval
                else:
                    varval = UNDEFINED
            stack.append((varname, varval))
        
        elif instr.opname == "LOAD_FAST":
            varname = instr.argval
            if varname in vardict:
                varval = vardict[varname]
            else:
                if varname in localdict:
                    varval = localdict[varname]
                    vardict[varname] = varval
                else:
                    varval = UNDEFINED
            stack.append((varname, varval))
        
        elif instr.opname == "LOAD_ATTR":
            varname = instr.argval
            if not stack:
                varval = "<stack error>"
            if stack:
                top = stack.pop()
            else:
                top = UNDEFINED
            if top is UNDEFINED:
                varval = "<stack error>"
            else:
                n, v = top
                if not hasattr(v, varname):
                    varval = "<attr error>"
                else:
                    varval = getattr(v, varname)
                varname = "{}.{}".format(n,varname)
                if stack:
                    stack[-1] = (varname, varval) # スタックの頂点を置き換える
                else:
                    stack.append((varname, varval))
            vardict[varname] = varval

        else:
            # スタックの増減だけ反映する
            try:
                stk = dis.stack_effect(instr.opcode, instr.arg)
            except:
                continue # 再帰的に呼び出されるとエラーになる？
            if stk > 0:
                stack.extend((UNDEFINED for _ in range(stk)))
            elif stk < 0:
                stack = stack[:stk]
        
    return vardict


def display_variables(dictionary, linewidth):
    """
    与えられた変数を表示する
    Params:
        dictionary(dict[str, Any]): 変数の辞書
        linewidth(Optional[int]): 表示幅
    Returns:
        list[str]: 行のリスト
    """
    msg = []

    for name, value in sorted(dictionary.items()):
        try:
            if value is UNDEFINED:
                val_str = "<undefined>"
            elif type(value).__repr__ is object.__repr__:
                if hasattr(value, "stringify"):
                    val_str = "<{} {}>".format(full_qualified_name(type(value)), value.stringify())
                else:
                    val_str = "<{}>".format(full_qualified_name(type(value)))
            else:
                val_str = repr(value)
        except Exception as e:
            val_str = "<error on __repr__: {}>".format(str(e))
        val_str = collapse_text(val_str, linewidth)
        val_str = val_str.replace('\n', '\n{}'.format(' ' * (len(name) + 2)))
        msg.append("{} = {}".format(name, val_str))

    return msg


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
    if gfn and gfn.__code__ is code:
        return FunctionInfo(gfn, 2)

    # staticmethodは検知できない
    return None


class FunctionInfo:
    def __init__(self, fn=None, type=None, bound_name=None, bound_object=None):
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
        sig = inspect.signature(self.fn)
        params = []
        if self.bound_name:
            params.append(self.bound_name)
        for p in sig.parameters.values():
            if p.default == inspect.Parameter.empty:
                params.append(p.name)
            else:
                params.append("{} = {}".format(p.name, p.default))
        return "({})".format(", ".join(params))
        

def print_exception_verbose(exception, linewidth=0xFFFFFF):
    # デバッグ用
    line = ErrorObject(None, exception).display_line()
    print(line)
    
    print("スタックトレース：")
    disp = verbose_display_traceback(exception, linewidth) # フル
    print(disp)

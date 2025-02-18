from typing import DefaultDict, Any, List, Sequence, Dict, Tuple, Optional, Union, Generator, TYPE_CHECKING

from machaon.core.object import Object, ObjectCollection
from machaon.core.symbol import (
    BadTypename, 
    is_valid_object_bind_name, BadObjectBindName, full_qualified_name,
)
from machaon.core.type.alltype import (
    TypeProxy, Type, TypeModule, TypeAny, instantiate_type, 
    parse_type_declaration, PythonType, get_type_extension_loader
)
from machaon.core.invocation import (
    BasicInvocation, InvocationEntry
)
if TYPE_CHECKING:
    from machaon.app import AppRoot
    from machaon.process import Process, Spirit
    from machaon.core.message import MessageTokenizer, MessageEngine

#    
def instant_return_test(context, value, typename):
    """ メソッド返り値テスト用 """
    from machaon.core.invocation import BasicInvocation, InvocationEntry
    from machaon.core.method import MethodResult
    inv = BasicInvocation()
    decl = parse_type_declaration(typename)
    entry = InvocationEntry(inv, None, (), {}, MethodResult(decl))
    return entry.result_object(context, value=value)


INVOCATION_FLAG_PRINT_STEP     = 0x0001
INVOCATION_FLAG_RAISE_ERROR    = 0x0002
INVOCATION_FLAG_SEQUENTIAL     = 0x0004
INVOCATION_FLAG_INHERIT_BIT_SHIFT  = 16 # 0xFFFF0000
INVOCATION_FLAG_INHERIT_REMBIT_SHIFT = 32

#
#
#
class ContextLog:
    isnull = False

    def __init__(self):
        self.msg: 'MessageEngine' = None
        self.logs = [] # [int, ...args][]
        self.finished = False

    @property
    def started(self):
        return self.msg is not None
    
    @property
    def message(self):
        if not self.started:
            raise ValueError('not started log')
        return self.msg.source
    
    @property
    def tokens(self):
        if not self.started:
            raise ValueError('not started log')
        return self.msg.get_tokens()

    def message_start(self, message: 'MessageEngine'):
        self.msg = message

    def message_end(self):
        self.finished = True

    def message_code(self, code: Any, token: str, tokentype: int):
        self.logs.append(('code', code, token, tokentype))

    def message_ast(self, subcode: str, stackindex: int = None):
        self.logs.append(('ast', subcode, stackindex))

    def message_rsv(self, subcode: str, hint: str = None):
        self.logs.append(('rsv', subcode, hint))

    def message_evaluating(self, message_index: int, source: str):
        self.logs.append(('eval-ready', source, message_index))

    def message_eval_start(self, invocation_index: int):
        self.logs.append(('eval-start', invocation_index))

    def message_eval_end(self, invocation_index: int):
        self.logs.append(('eval-end', invocation_index))
        
    def message_start_sub(self, subcontext):
        self.logs.append(('begin-sub', subcontext))

    def pprint(self, context: 'InvocationContext', printer):
        from machaon.core.message import display_syntactic_token
        def put(level: int, s: str):
            indent = " " + (level-1) * "  "
            printer(indent + s)
        subindex = None
        for code, *args in self.logs:
            if code == 'code':
                ccode = args[0]
                token = args[1]
                stxtoken = display_syntactic_token(args[2])
                if stxtoken:
                    if token:
                        tokenchar = "{} [{}]".format(token, stxtoken)
                    else:
                        tokenchar = "[{}]".format(stxtoken)
                else:
                    tokenchar = token
                printer(" parse token: {}".format(tokenchar))
                for line in ccode.display_instructions():
                    printer("   do instruction:")
                    printer("     {}".format(line))

            elif code == 'ast':
                xcode = args[0]
                index = args[1]
                if xcode == 'msgbegin':
                    printer("   begin message<{}>".format(index))
                elif xcode == 'msgend':
                    printer("   end message<{}>".format(index))
                elif xcode == 'blockbegin':
                    printer("   begin block, from message<{}>".format(index))
                elif xcode == 'blockend':
                    printer("   end block, to message<{}>".format(index))
                elif xcode == 'allblockend':
                    printer("   end all block")
                elif xcode == 'conauto':
                    printer(" implicit message evaluation")
                elif xcode == 'conexpl':
                    printer(" explicit message evaluation")
                else:
                    raise ValueError("Unknown message-ast subcode: {}".format(xcode))
                
            elif code == 'rsv':
                xcode = args[0]
                hint = args[1]
                printer("   resolving:")
                if xcode == 'ctor':
                    printer("     constructor '{}'".format(hint))
                elif xcode == 'ex-method':
                    printer("     external method of {}".format(hint))
                elif xcode == 'method':
                    printer("     method {}".format(hint))
                elif xcode == 'common-method':
                    printer("     Object method {}".format(hint))
                elif xcode == 'dyn-method':
                    printer("     instance method {}".format(hint))
                else:
                    raise ValueError("Unknown log code: {}".format(xcode))

            elif code == 'eval-ready':
                src = args[0]
                printer("   message: {}".format(src))

            elif code == 'eval-start':
                invindex: int = args[0]
                printer("   invocation: {}".format(context.invocations[invindex].message.sexpr()))

            elif code == 'eval-end':
                invindex: int = args[0]
                printer("   invoked:")
                inv = context.invocations[invindex]
                if inv.is_failed():
                    printer("     error occurred:")
                    printer("     {}".format(inv.result.value.display_exception()))
                else:
                    printer("     return:")
                    printer("     {}".format(inv.result))
            
            elif code == 'begin-sub':
                if subindex is None: 
                    subindex = 0
                subindex += 1
                continue
            else:
                raise ValueError("Unknown log code: {}".format(code))
            
        if subindex is not None:
            title = "sub-contexts"
            if subindex > 1:
                line = "0-{}".format(subindex-1)
            else:
                line = "0"
            pad = 16-len(title)
            printer(" {}:{}{}".format(title, pad*" ", line))

    def get_instructions(self):
        for code, *values in self.logs:
            if code == 'code':
                yield values[0]


class NullContextLog:
    isnull = True

    def __getattr__(self, name):
        return self.nop

    def nop(self, *_args):
        pass



#
#
#
class InvocationContext:
    """ @type [Context]
    メソッドの呼び出しコンテキスト。
    """
    def __init__(self, *, input_objects, type_module, spirit=None, subject=None, flags=0, herepath=None, parent=None):
        self.type_module: TypeModule = type_module
        self.input_objects: ObjectCollection = input_objects  # 外部のオブジェクト参照
        self.subject_object: Union[None, Object, Dict[str, Object]] = subject       # 無名関数の引数とするオブジェクト
        self.spirit: 'Spirit' = spirit
        self.invocations: List[InvocationEntry] = []
        self.invocation_flags = flags
        self._extra_exception = None
        self._log = ContextLog()
        self.herepath = herepath
        self.parent = parent # 継承元のコンテキスト

    def get_spirit(self):
        return self.spirit
    
    @property
    def root(self) -> 'AppRoot':
        return self.spirit.root
    
    #
    def inherit(self, subject=None, herepath=None):
        # 予約されたフラグを取り出して結合する
        preserved_flags = 0xFFFF & (self.invocation_flags >> INVOCATION_FLAG_INHERIT_BIT_SHIFT)
        flags = (0xFFFF & self.invocation_flags) | preserved_flags
        remove_flags = 0xFFFF & (self.invocation_flags >> INVOCATION_FLAG_INHERIT_REMBIT_SHIFT)
        flags = flags & ~remove_flags
        # パス
        herepath = herepath or self.herepath
        # 他の要素は全て引き継がれる
        return InvocationContext(
            input_objects=self.input_objects, 
            type_module=self.type_module, 
            spirit=self.spirit,
            subject=subject,
            flags=flags,
            herepath=herepath,
            parent=self,
        )

    def inherit_sequential(self):
        """ 連続実行を行う呼び出しのコンテクストを生成する """
        cxt = self.inherit()
        cxt.remove_flags(INVOCATION_FLAG_PRINT_STEP)
        cxt.set_flags(INVOCATION_FLAG_SEQUENTIAL|INVOCATION_FLAG_RAISE_ERROR)
        cxt.disable_log()
        return cxt

    def set_flags(self, flags, inherit_set=False, inherit_remove=False):
        if isinstance(flags, str):
            flags = globals().get("INVOCATION_FLAG_" + flags)

        if inherit_remove:
            # 以降の継承コンテキストで削除されるフラグをセット
            self.invocation_flags |= (flags << INVOCATION_FLAG_INHERIT_REMBIT_SHIFT)
        elif inherit_set:
            # 以降の継承コンテキストで有効化されるフラグをセット
            self.invocation_flags |= (flags << INVOCATION_FLAG_INHERIT_BIT_SHIFT)
        else:
            self.invocation_flags |= flags
    
    def remove_flags(self, flags):
        if isinstance(flags, str):
            flags = globals().get("INVOCATION_FLAG_" + flags)
        
        self.invocation_flags &= ~flags

    def is_set_print_step(self) -> bool:
        return (self.invocation_flags & INVOCATION_FLAG_PRINT_STEP) > 0
    
    def is_set_raise_error(self) -> bool:
        return (self.invocation_flags & INVOCATION_FLAG_RAISE_ERROR) > 0
    
    def is_sequential_invocation(self) -> bool: 
        return (self.invocation_flags & INVOCATION_FLAG_SEQUENTIAL) > 0

    #
    def get_herepath(self):
        return self.herepath

    #
    def get_object(self, name) -> Optional[Object]:
        elem = self.input_objects.get(name)
        if elem:
            return elem.object
        return None
    
    def get_process_object(self, id: int = None) -> Optional[Object]:
        if id is None:
            proc = self.spirit.get_process()
            if proc is None:
                return None
            id = proc.get_index()
        return self.get_object(str(id))
        
    def get_previous_process_object(self, delta) -> Optional[Object]:
        proc = self.spirit.get_process()
        if proc is None:
            return None
        dest = proc.get_index() - delta
        if dest < 1:
            return None
        return self.get_object(str(dest))

    def get_selected_objects(self) -> List[Object]:
        li = [] # type: List[Object]
        for x in self.input_objects.pick_all():
            if x.selected:
                li.append(x.object)
        return list(reversed(li))

    def push_object(self, name: str, obj: Object):
        self.input_objects.push(name, obj)

    def push_process_object(self, id: int, obj: Object):
        self.push_object(str(id), obj)
        
    def bind_object(self, name: str, obj: Object):
        if not is_valid_object_bind_name(name):
            raise BadObjectBindName(name)
        self.input_objects.push(name, obj)
    
    def store_object(self, name: str, obj: Object):
        self.input_objects.store(name, obj)

    def remove_object(self, name: str):
        self.input_objects.delete(name)

    def remove_process_object(self, id: int):
        self.remove_object(str(id))
    
    #
    def set_subject(self, subject: Object):
        self.subject_object = subject

    def clear_subject(self):
        self.subject_object = None
    
    #    
    def select_type(self, typecode, describername=None, resolver=None) -> TypeProxy:
        """ 型名を渡し、型定義を取得する。関連するパッケージをロードする """
        if isinstance(typecode, TypeProxy):
            return typecode
        return self.type_module.select(typecode, describername, resolver=resolver)

    def get_type(self, typecode) -> TypeProxy:
        """ 型名を渡し、型定義を取得する """
        t = self.type_module.get(typecode)
        if t is None:
            raise BadTypename(typecode)
        return t
    
    def get_py_type(self, type) -> PythonType:
        """ Pythonの型 """
        return PythonType(type)

    def is_tuple(self, value):
        """ 型の一致: タプル """
        from machaon.types.tuple import ObjectTuple
        return isinstance(value, ObjectTuple)
    
    def is_path(self, value):
        """ 型の一致: パス """
        from machaon.types.shell import Path
        return isinstance(value, Path)
    
    def is_instance(self, value, typename):
        """ 型の一致: 任意の型 """
        t = self.get_type(typename)
        return t.check_value_type(type(value))

    def is_error(self, value):
        """ 型の一致: エラー """
        from machaon.types.stacktrace import ErrorObject
        return isinstance(value, ErrorObject)
    
    def deduce_type(self, value: Any) -> TypeProxy:
        """ 値から型を推定する """
        if isinstance(value, Object):
            return value.type
        value_type = type(value) 
        t = self.type_module.deduce(value_type)
        if t is not None:
            return t
        return PythonType(value_type)

    def define_type(self, typecode, *, fallback=False) -> Type:
        """ 型を定義する """
        return self.type_module.define(typecode, fallback=fallback)

    def define_temp_type(self, describer: Any) -> Type:
        """ 新しい型を作成するが、モジュールに登録しない """
        return Type(describer).load()

    def instantiate_type(self, conversion, *args) -> TypeProxy:
        """ 型をインスタンス化する """
        return instantiate_type(conversion, self, *args)
    
    def new_object(self, value: Any, *args, type=None, conversion=None, module=None) -> Object:
        """ 型名と値からオブジェクトを作る。値の型変換を行う 
        Params:
            value(Any): 値; Noneの場合、デフォルトコンストラクタを呼び出す
            args(Sequence[Any]): 追加のコンストラクタ引数
        KeywordParams:
            type(Any): 型を示す値（型名、型クラス、型インスタンス）
            conversion(str): 値の変換方法を示す文字列
        """
        if isinstance(value, dict):
            extension = get_type_extension_loader(value)
            if extension is not None:
                basic = self.new_object(extension.get_basic(), type=type, conversion=conversion)
                return extension.load(basic.type).new_object(basic.value)

        if type and not isinstance(type, TypeAny):
            t = self.select_type(type, module)
            if t is None:
                if isinstance(type, str):
                    raise BadTypename(type)
                else:
                    t = self.define_type(type) # 無ければ定義して返す 
            if value is None and not args:
                convobj = t.construct_obj(self, None) # デフォルトコンストラクタ
            else:
                convobj = t.construct_obj(self, value, *args)
            return convobj
        elif conversion:
            tins = self.instantiate_type(conversion)
            return tins.construct_obj(self, value, *args)
        else:
            if isinstance(value, Object):
                return value
            if value is None:
                return self.get_type("None").new_object(value)
            valtype = self.deduce_type(value)
            return valtype.construct_obj(self, value)
    
    def new_invocation_error_object(self, exception=None, objectType=None):
        """ エラーオブジェクトを作る """
        if exception is None: 
            exception = self.get_last_exception()
        if objectType is None:
            objectType = Object
        from machaon.types.stacktrace import ErrorObject
        if isinstance(exception, Exception):
            exception = ErrorObject(exception, context=self)
        elif not isinstance(exception, ErrorObject):
            raise TypeError('exception')
        return objectType(self.get_type("Error"), exception)
    
    def begin_invocation(self, entry: InvocationEntry):
        """ 呼び出しの直前に """
        if self.is_sequential_invocation():
            # 上書きする
            if not self.invocations:
                self.invocations.append(entry)
            else:
                self.invocations[-1] = entry 
        else:
            self.invocations.append(entry)
        index = len(self.invocations)-1
        self.log.message_eval_start(index)
        return index

    def finish_invocation(self):
        """ 呼び出しの直後に """
        index = len(self.invocations)-1
        self.log.message_eval_end(index)
        return index
    
    def get_last_invocation(self) -> Optional[InvocationEntry]:
        if self.invocations:
            return self.invocations[-1]
        return None

    def get_last_exception(self) -> Optional[Exception]:
        """ @method alias-name [error]
        直前の呼び出しで発生した例外を返す。
        Returns:
            Error:
        """
        if self._extra_exception:
            return self._extra_exception
        inv = self.get_last_invocation()
        if inv:
            return inv.exception
        return None
    
    def is_failed(self):
        """ @method
        エラーが発生したか
        Returns:
            bool:
        """
        return self.get_last_exception() is not None

    def raise_if_failed(self, value=None):
        """ """
        err = self.get_last_exception()
        if err is not None:
            raise err
        if value and self.is_error(value):
            err = value.get_error()
            raise err
    
    def push_extra_exception(self, exception):
        """ 呼び出し以外の場所で起きた例外を保存する """
        self._extra_exception = exception

    def pop_exception(self):
        """ コンテキストを使いまわす場合にエラーをクリアする """
        excep = self.get_last_exception()
        self._extra_exception = None
        return excep

    def get_process(self):
        """ @method alias-name [process]
        紐づけられたプロセスを得る。
        Returns:
            Process:
        """
        return self.spirit.process
    
    def enable_log(self):
        if self._log.isnull:
            self._log = ContextLog()

    def disable_log(self):
        """ ログを蓄積しない """
        if not self._log.isnull:
            self._log = NullContextLog()

    @property
    def log(self):
        return self._log

    def pprint_log(self, printer=None):
        """ 蓄積されたログを出力する """
        if printer is None: 
            printer = print

        if not self._log:
            printer(" --- no log ---")
            return
        
        printer(" start.")
        printer("   {}".format(self._log.message))
        
        self._log.pprint(self, printer)

        if self._extra_exception:
            from machaon.types.stacktrace import ErrorObject
            names = []
            for err in ErrorObject(self._extra_exception, context=self).chain():
                names.append(err.get_error_typename())
            printer("  ERROR: {}".format(" <- ".join(names)))

        if self._log.finished:
            printer(" end.")
        
    def get_message(self):
        """ @method alias-name [message] 
        実行されたメッセージ。
        Returns:
            Str:
        """
        if self._log is not None and self._log.started:
            return self._log.message
        raise ValueError("実行ログに記録がありません")
    
    def get_invocations(self):
        """ @method alias-name [invocations invs]
        呼び出された関数のリスト。
        Returns:
            Sheet[]:
        Decorates:
            @ view: message-expression result
        """ 
        vals = []
        for inv in self.invocations:
            vals.append({
                "#extend" : inv,
                "message-expression" : inv.message.sexpr()
            })
        return vals
    
    def get_errors(self, _app):
        """ @task alias-name [errors]
        サブコンテキストも含めたすべてのエラーを表示する。
        Returns:
            Sheet[]:
        Decorates:
            @ view: context-id message-expression error
        """
        errors = []

        cxts = []
        cxts.append(("", self))
        i = 0
        while i < len(cxts):
            l, cxt = cxts[i]
            err = cxt.get_last_exception()
            if err:
                errors.append({
                    "#extend" : cxt,
                    "context-id" : l,
                    "message-expression" : cxt.get_message(),
                    "error" : err,
                })
            
            for j, subcxt in enumerate(cxt.get_subcontext_list()):
                if not l:
                    sublevel = "{}".format(j)
                else:
                    sublevel = "{}-{}".format(l,j)
                cxts.append((sublevel, subcxt))
            i += 1

        return errors

    def get_instructions(self):
        """ @method alias-name [instructions instrs]
        コンパイルされた内部命令
        Returns:
            Sheet[Any]:
        Decorates:
            @ view: display-instructions
        """
        if self._log.isnull:
            return
        yield from self._log.get_instructions()

    def get_subcontext(self, index):
        """ @method alias-name [sub-context sub]
        呼び出しの中でネストしたコンテキストを取得する。
        Params:
            index(str): ネスト位置を示すインデックス。(例:0-4-1)
        Returns:
            Context:
        """
        if isinstance(index, str):
            indices = [int(x) for x in index.split("-")]
        else:
            indices = [index]
        
        subcxt = None
        logs = self._log
        for idx in indices:
            submessages = [x for x in logs if x[0] == LOG_MESSAGE_BEGIN_SUB]
            if idx<0 or idx>= len(submessages):
                raise IndexError("'{}'に対応する子コンテキストはありません".format(index))
            subcxt = submessages[idx][1]
            # 次のレベルへ
            logs = subcxt._log 
        return subcxt
    
    def get_subcontext_list(self):
        """ @method alias-name [sub-contexts subs]
        サブコンテキストの一覧。
        Returns:
            Sheet[Context]:
        Decorates:
            @ view: is-failed message last-result
        """
        rets = []
        submessages = [x for x in self._log if x[0] == LOG_MESSAGE_BEGIN_SUB]
        for values in submessages:
            subcxt = values[1]
            rets.append(subcxt)
        return rets
    
    def get_depth(self):
        """@method
        サブコンテクストとしての深さを計算する
        Returns:
            Int: 1で始まる深さの数値
        """
        level = 1
        p = self.parent
        while p:
            level += 1
            p = p.parent
        return level
    
    def get_last_result(self):
        """ @method alias-name [last-result]
        最後に返されたメッセージの実行結果。
        Returns:
            Any:
        """
        inv = self.get_last_invocation()
        if inv:
            return inv.result
        return None

    def pprint_log_as_message(self, app):
        """ @method spirit alias-name [log]
        ログを表示する。
        """ 
        self.pprint_log(lambda x: app.post("message", x))

    def display_log(self, sep="\n"):
        """ @method 
        Returns:
            Str:
        """
        lines = []
        self.pprint_log(lambda x: lines.append(x))
        if sep is None:
            return lines
        else:
            return sep.join(lines)
        
    def display_error_part(self):
        """ @method
        Returns:
            Str:
        """
        if self._log is not None and self._log.started:
            readed, unreaded = self._log.tokens.get_readed(self._log.message)
            return readed.rstrip() + " <<ここでエラー>> " + unreaded.strip() + ' [end]'
        return "<undefined message source>"

    def constructor(self, context, value):
        """ @meta context 
        Params:
            value(Int|Str):
        """
        if isinstance(value, int):
            from machaon.process import Process
            proc = Process.constructor(Process, context, value)
            cxt = proc.get_last_invocation_context()
            if cxt is None:
                raise ValueError("プロセス'{}'にコンテキストが紐づいていません".format(value))
            return cxt
        elif isinstance(value, str):
            procindex, sep, sublevel = value.partition("-")
            cxt = InvocationContext.constructor(self, context, int(procindex))
            if sep:
                return cxt.get_subcontext(sublevel)
            else:
                return cxt
        else:
            raise TypeError(value)

# ログを無へ流す
def _context_no_log(*a, **kw):
    pass

_instant_context_types = None

def instant_context(subject=None, root=None):
    """ 即席実行用のコンテキスト """
    global _instant_context_types
    if _instant_context_types is None:
        t = TypeModule()
        t.add_fundamentals()
        errs = t.add_default_module_types()
        if errs:
            raise errs[0]
        t.check_loading()
        _instant_context_types = t

    from machaon.process import TempSpirit
    spi = TempSpirit(root)
    
    return InvocationContext(
        input_objects=ObjectCollection(),
        type_module=_instant_context_types,
        subject=subject,
        spirit=spi
    )


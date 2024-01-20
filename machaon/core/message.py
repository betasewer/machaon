
from itertools import zip_longest

from machaon.core.symbol import (
    BadTypename,
    PythonBuiltinTypenames,
    SIGIL_OBJECT_ID,
    SIGIL_OBJECT_LAMBDA_MEMBER,
    SIGIL_OBJECT_ROOT_MEMBER,
    SIGIL_OBJECT_PREVIOUS,
    SIGIL_QUOTERS,
    SIGIL_LINE_QUOTER,
    SIGIL_BEGIN_USER_QUOTER,
    SIGIL_SELECTOR_NEGATE_RESULT,
    SIGIL_SELECTOR_BASIC_RECIEVER,
    SIGIL_SELECTOR_TRAILING_ARGS,
    SIGIL_SELECTOR_CONSUME_ARGS,
    SIGIL_SELECTOR_SHOW_HELP,
    SIGIL_SELECTOR_IGNORE_ARGS,
    SIGIL_OPERATOR_MEMBER_AT,
    SIGIL_CONSTRUCTOR_SELECTOR,
    SIGIL_BEGIN_MESSAGE,
    SIGIL_BEGIN_MESSAGE_BLOCK,
    SIGIL_BEGIN_MESSAGE_DEFERRED,
    SIGIL_END_MESSAGE,
    SIGIL_DISCARD_MESSAGE,
    QUOTE_ENDPARENS,
    is_triming_control_char,
    is_modifiable_selector,
)
from machaon.core.object import Object
from machaon.core.method import MethodParameter, enum_methods_from_type_and_instance
from machaon.core.invocation import (
    BasicInvocation,
    FunctionInvocation,
    TypeMethodInvocation,
    InstanceMethodInvocation,
    MessageInvocation,
    TypeConstructorInvocation,
    Bind1stInvocation,
)
from machaon.core.type.declparser import TypeDeclError
from machaon.core.type.typemodule import TypeModuleError
from machaon.core.type.instance import ObjectType


#
# ----------------------------------------------------------------------------
#
#
#
# ----------------------------------------------------------------------------
#
class BadExpressionError(Exception):
    """ メッセージの構文のエラー """
    pass

class InternalMessageError(Exception):
    """ メッセージの実行中に起きたエラー """
    def __init__(self, error, message, context):
        self.error = error
        self.message = message
        self.context = context
        if hasattr(self.error, "__traceback__"):
            self.with_traceback(self.error.__traceback__) # トレース情報を引き継ぐ
            self.__cause__ = self.error

    def __str__(self):
        lines = []
        lines.append("メッセージ実行中にエラー発生：")
        lines.append(str(self.error))
        lines.append("  メッセージ：")
        done, notdone = self.message.split_read_expression()
        if notdone:
            msg = done.rstrip() + " <<!!ここでエラー!!>> " + notdone.lstrip()
        else:
            msg = done
        lines.append("    {}".format(msg))
        lines.append("  実行ログ：")
        for l in self.context.display_log(None):
            lines.append("  {}".format(l))
        return "\n".join(lines)

#
#
#
class Message:
    def __init__(self, 
        reciever = None, 
        selector = None, 
        args = None
    ):
        self.reciever = None # Object
        self.selector = None # Invocation
        self.args = args or []   # List[Object]
        self.selector_mods = set()
        self._conclude = False
        if reciever:
            self.set_reciever(reciever)
        if selector:
            self.set_selector(selector)
    
    def __repr__(self):
        return "<Message {}>".format(self.sexpr())
    
    def set_reciever(self, reciever):
        if reciever is None:
            raise TypeError()
        self.reciever = reciever

    def set_selector(self, selector):
        if selector is None:
            raise TypeError()
        self.selector = selector

    def set_selector_modifier(self, modifier):
        if self.is_selector_specified():
            self.selector.modifier.add(modifier)
        else:
            self.selector_mods.add(modifier)

    def add_arg(self, arg):
        if arg is None:
            raise TypeError()
        self.args.append(arg)
    
    def is_reciever_specified(self):
        return self.reciever is not None
    
    def is_selector_specified(self):
        return self.selector is not None and isinstance(self.selector, BasicInvocation)

    def is_max_arg_specified(self):
        if self.selector:
            return len(self.args) >= self.selector.get_max_arity()
        return False
    
    def is_min_arg_specified(self):        
        if self.selector:
            return len(self.args) >= self.selector.get_min_arity()
        return False

    def is_selector_arg_trailing(self):
        if self.selector:
            return "TRAILING_ARGS" in self.selector.modifier
        return False
    
    def is_selector_parameter_consumer(self):
        if self.selector:
            return self.selector.is_parameter_consumer()
        return False

    def is_task(self):
        if self.selector:
            return self.selector.is_task()
        return False
    
    def get_next_parameter_spec(self):
        if self.selector is None:
            raise BadExpressionError("セレクタがありません")
    
        index = len(self.args) # 次に入る引数
        spec = self.selector.get_parameter_spec(index)
        if spec:
            return spec
        else:
            return MethodParameter("param{}".format(index), None, "引数{}".format(index))

    def get_reciever_value(self):
        if isinstance(self.reciever, BasicRef):
            return self.reciever.get_lastvalue()
        else:
            return self.reciever

    def _refs(self):
        return [x for x in (self.reciever, self.selector, *self.args) if isinstance(x, BasicRef)]
    
    def reset_ref(self):
        for ref in self._refs():
            ref.reset()

    def check_concluded(self, evalcontext):
        """ メッセージがすでに完成しているか """
        urefcount = len([x for x in self._refs() if not x.is_resolved()])
        if evalcontext.locals.count() < urefcount:
            if self._conclude:
                raise BadExpressionError("必要な値の数がスタック上に足りていません")
            else:
                return False
        
        if self._conclude:
            self.complete_explicit_conclusion(evalcontext)
            return True
        else:
            return self.check_auto_conclusion(evalcontext)
        
    def check_auto_conclusion(self, evalcontext):
        """ メッセージ実行に必要な最小の要素があるか確認 """
        if not self.is_reciever_specified():
            return False
        
        if not self.resolve_selector(evalcontext):
            return False
        
        if self.is_selector_arg_trailing():
            if not self.is_max_arg_specified():
                return False
        else:
            if not self.is_min_arg_specified():
                return False
        
        return True

    def complete_explicit_conclusion(self, evalcontext):
        """ メッセージを完成させ、要素が足りなければ例外を投げる """
        if not self.is_reciever_specified():
            # レシーバが無い場合はエラー
            raise BadExpressionError("レシーバがありません：{}".format(self.sexpr()))
        
        # セレクタを解決する
        if not self.resolve_selector(evalcontext):
            # セレクタが無い場合はレシーバを返すセレクタを補う
            self.selector = select_method("=")

        if not self.is_min_arg_specified():
            # 引数が足りない場合
            if len(self.args) > 0:   
                # 引数がゼロ以上あり、足りない場合はエラー         
                spec = self.get_next_parameter_spec()
                syntax = self.get_method_syntax(evalcontext.context)
                raise BadExpressionError("引数'{}'が足りません：{} ".format(spec.get_name(), syntax))
            else:
                # ゼロの場合はセレクタを返す
                self.as_selector_returner(evalcontext)

    def conclude_explicit(self):
        """ メッセージ完成のフラグを明示的に立てる """
        self._conclude = True

    def resolve_selector(self, evalcontext):
        """ セレクタを呼び出しへと解決する。 """
        if self.reciever is None or self.selector is None:
            return False

        sel = self.selector
        if isinstance(sel, BasicInvocation):
            return True
        if isinstance(sel, BasicRef):
            obj = sel.pick_object(evalcontext)
            sel = ObjectSelectorResolver(obj)
        if isinstance(sel, SelectorResolver):
            sel = sel.resolve(evalcontext, self.reciever)

        self.selector = sel

        if self.selector_mods:
            self.selector.modifier |= self.selector_mods
            self.selector_mods.clear()
        
        return True
    
    def eval(self, evalcontext):
        """ 
        完成したメッセージを実行する。
        Params:
            evalcontext(EvalContext):
        Returns:
            Object: 返り値
        """
        if self.reciever is None or self.selector is None:
            raise BadExpressionError("レシーバとセレクタがありません")

        args = []

        # コンテキスト引数を取り出す。スタックにあるかもしれないので、逆順に
        for argobj in [*reversed(self.args), self.reciever]:
            if isinstance(argobj, BasicRef):
                args.append(argobj.pick_object(evalcontext))
            else:
                args.append(argobj)
        args.reverse() # 元の順番に戻す

        # 実行する
        context = evalcontext.context
        invocation = self.selector.prepare_invoke(context, *args)
        invocation.set_message(self)

        retobj = invocation.invoke(context)

        if retobj is None:
            raise ValueError("No return value exists on the context stack")
        return retobj

    def as_selector_returner(self, evalcontext):
        """ セレクタを返すメッセージに変える """ 
        if self.reciever is None or self.selector is None:
            raise BadExpressionError("レシーバやセレクタがありません")
        # セレクタを解決する
        self.resolve_selector(evalcontext)
        # メッセージを組み替える
        self.reciever = self.selector
        self.selector = select_method("=")
        self.args.clear()
    
    #
    # デバッグ用
    #
    def sexpr(self):
        # S式風に表示：不完全なメッセージであっても表示する
        exprs = []

        def put(item):
            if isinstance(item, Object):
                exprs.append("<{} {}>".format(item.get_typename(), item.value_debug_str()))
            elif isinstance(item, BasicRef):
                exprs.append("<#{}: {}>".format(type(item).__name__, item.get_lastvalue()))
            elif isinstance(item, SelectorResolver):
                exprs.append("<selector {}>".format(item.selector))
            else:
                exprs.append(str(item))

        if self.is_reciever_specified():
            put(self.reciever)
        else:
            put("<レシーバ欠落>")

        if self.is_selector_specified():
            put(self.selector)
            if isinstance(self.selector, BasicInvocation):
                minarg = self.selector.get_min_arity()
                for elem, _ in zip_longest(self.args, range(minarg-1)):
                    if elem is not None:
                        put(elem)
                    else:
                        put("<引数欠落>")
            else:
                for a in self.args:
                    put(a)
        else:
            put("<セレクタ欠落>")
            put("<引数欠落（個数不明）>")

        return "({})".format(" ".join(exprs))
    
    def get_method_syntax(self, context):
        if self.reciever is None:
            raise ValueError("レシーバが指定されていません")
        if self.selector is None:
            raise ValueError("セレクタが指定されていません")
        
        reci = self.reciever
        if isinstance(reci, BasicRef):
            reci = reci.pick_object(context)
        
        if isinstance(self.selector, TypeMethodInvocation):
            sign = self.selector.get_method().get_signature()
            return "{}.{} = {}".format(reci.get_typename(), self.selector.get_method_name(), sign)

        args = [reci]
        inventry = self.selector.prepare_invoke(context, *args)
        
        from machaon.types.stacktrace import FunctionInfo
        fn = FunctionInfo(inventry.action)
        return "{}{}".format(self.selector.get_method_name(), fn.display_parameters())

#
#
#
class EvalContext:
    def __init__(self, context):
        self.context = context
        self.locals = LocalStack()

class LocalStack:
    """ 計算結果のスタック """
    def __init__(self):
        self.local_objects = [] 

    def count(self):
        return len(self.local_objects)

    def push_local_object(self, obj):
        """
        Params:
            obj(Object):
        """
        self.local_objects.append(obj)
    
    def top_local_object(self):
        """
        Returns:
            Optional[Object]:
        """
        if not self.local_objects:
            return None
        return self.local_objects[-1]

    def pop_local_object(self):
        if not self.local_objects:
            return
        self.local_objects.pop()

    def clear_local_objects(self):
        """
        Returns:
            List[Object]:
        """
        objs = self.local_objects
        self.local_objects = []
        return objs

# --------------------------------------------------------------------
#
# メッセージの構成要素
#
# --------------------------------------------------------------------
#
# オブジェクトへの参照
#
class BasicRef:
    def __init__(self, lastvalue=None):
        self._lastvalue = lastvalue

    def pick_object(self, evalcontext):
        if self._lastvalue is None:
            self._lastvalue = self.do_pick(evalcontext)
        return self._lastvalue
    
    def do_pick(self, evalcontext):
        raise NotImplementedError()
    
    def get_lastvalue(self):
        return self._lastvalue
    
    def reset(self):
        self._lastvalue = None

    def is_resolved(self):
        return True

class ResultStackRef(BasicRef):
    """ スタックにおかれた計算結果への参照 """
    def do_pick(self, evalcontext):
        value = evalcontext.locals.top_local_object()
        if value is None:
            raise BadExpressionError("ローカルスタックを参照しましたが、値がありません")
        evalcontext.locals.pop_local_object()
        return value
        
    def is_resolved(self):
        return self.get_lastvalue() is not None
    
class SubjectRef(BasicRef):
    """ 引数オブジェクトへの参照 """
    def do_pick(self, evalcontext):
        subject = evalcontext.context.subject_object
        if subject is None:
            raise BadExpressionError("無名関数の引数を参照しましたが、与えられていません")
        return subject

class ObjectRef(BasicRef):
    """ 任意のオブジェクトへの参照 """
    def __init__(self, ident, lastvalue=None):
        super().__init__(lastvalue)
        self._ident = ident
    
    def do_pick(self, evalcontext):
        obj = evalcontext.context.get_object(self._ident)
        if obj is None:
            raise BadExpressionError("オブジェクト'{}'は存在しません".format(self._ident))
        return obj

class PreviousObjectRef(BasicRef):
    """ 任意のオブジェクトへの参照 """
    def __init__(self, ident, lastvalue=None):
        super().__init__(lastvalue)
        self._ident = ident
    
    def do_pick(self, evalcontext):
        obj = evalcontext.context.get_previous_object(self._ident)
        if obj is None:
            raise BadExpressionError("参照'{}'に対応するオブジェクトは存在しません".format(self._ident))
        return obj

#
#
#
class SelectorResolver():
    """ セレクタを解決する """
    def __init__(self, selector):
        self.selector = selector

    def resolve(self, evalcontext, reciever):
        if isinstance(reciever, BasicRef):
            reciever = reciever.pick_object(evalcontext)
        return select_method(self.selector, reciever.type, reciever=reciever.value, context=evalcontext.context)

class ObjectSelectorResolver(SelectorResolver):
    """ 文字列ではないセレクタ名を解決する """
    def resolve(self, evalcontext, reciever):
        if isinstance(reciever, BasicRef):
            reciever = reciever.pick_object(evalcontext)
        return select_method_by_object(self.selector, reciever.type, reciever=reciever.value, context=evalcontext.context)


#
# リテラル
#
def select_type(context, typeexpr):
    """ 型 
    Params:
        typeexpr(str):
    Returns:
        Optional[Object]:
    """
    try:
        tt = context.instantiate_type(typeexpr)
    except (BadTypename, TypeDeclError, AttributeError, TypeModuleError):
        return None # 型定義が見つからなかった
    return context.get_type("Type").new_object(tt)

def select_literal(context, literal):
    """ 基本型の値 
    Params:
        literal(str):
    Returns:
        Object:
    """
    from ast import literal_eval
    try:
        value = literal_eval(literal)
    except Exception:
        value = literal
    
    # 値をオブジェクトに変換する
    typename = type(value).__name__
    if typename in PythonBuiltinTypenames.literals:
        return Object(context.get_type(typename), value)
    else:
        return Object(context.get_type("Str"), literal) # エラーにしないで、元の文字列のままスルーする


# メソッド
def select_method(name, typetraits=None, *, reciever=None, modbits=None, context=None) -> BasicInvocation:
    # モディファイアを分離する
    if modbits is None:
        if isinstance(name, AffixedSelector):
            s = name
        else:
            s = AffixedSelector.parse(name)
        name = s.selector()
        modbits = s.affixes()

    # 数字のみのメソッドは添え字アクセスメソッドにリダイレクト
    if name.isdigit():
        if not typetraits or not typetraits.is_object_collection_type(): # ObjectCollectionには対応しない
            return select_index_method(int(name), typetraits, reciever, modbits)

    # コンストラクタセパレータが含まれている
    if SIGIL_CONSTRUCTOR_SELECTOR in name and context:
        method, sep, typedecl = name.partition(SIGIL_CONSTRUCTOR_SELECTOR)
        if method and sep and typedecl and typedecl[0].isupper(): # 型らしき文字が続く
            method = expand_constructor_syntax(method, typedecl)
            return select_type_method(typedecl, method, modbits, reciever=reciever, context=context)

    # 先頭に型らしき大文字の識別子が来た
    if name[0].isupper():
        typedecl, sep, method = name.partition(SIGIL_OPERATOR_MEMBER_AT)
        if sep:
            # セパレータが含まれている場合、外部メソッド呼び出し
            return select_type_method(typedecl, method, modbits, reciever=reciever, context=context)
        else:
            # 型変換コンストラクタ
            return select_type_constructor(name, modbits, context=context)

    # この型のメソッド
    using_type_method = typetraits is not None
    if using_type_method:
        # 型メソッドを参照
        meth = typetraits.select_method(name)
        if meth is not None:
            return meth.make_invocation(modbits, typetraits)
    
    # 共通型定義の関数
    gmeth = ObjectType.select_method(name)
    if gmeth is not None:
        return gmeth.make_invocation(modbits, ObjectType)

    if using_type_method:
        if not typetraits.is_selectable_instance_method():
            err = "メソッド '{}' は '{}' に定義されていません:".format(name, typetraits.get_typename())
            raise BadExpressionError(err)
    
    # インスタンスメソッド
    return InstanceMethodInvocation(name, modifier=modbits)


def select_method_by_object(obj, typetraits=None, *, reciever=None, modbits=None, context=None) -> BasicInvocation:
    # 逆転モディファイアには専用の呼び出しを使う
    #if "REVERSE_MESSAGE" in modbits:
    tn = obj.get_typename()
    v = obj.value
    from machaon.core.function import FunctionExpression
    if tn == "Int" or tn == "Float":
        return select_index_method(int(v), typetraits, reciever, modbits)
    elif tn == "Type":
        return select_type_constructor(v, modbits)
    elif tn == "Str": 
        return select_method(v, typetraits, reciever=reciever, modbits=modbits, context=context)
    elif isinstance(v, BasicInvocation):
        return v
    elif tn == "Function" or isinstance(v, FunctionExpression):
        return MessageInvocation(v)
    elif callable(v):
        return select_py_callable(v)
    else:
        raise BadExpressionError("'{}'はメソッドセレクタとして無効な型です".format(obj))

def select_index_method(value, typetraits, reciever, modbits):
    inv = select_method("at", typetraits, reciever=reciever, modbits=modbits)
    return Bind1stInvocation(inv, value, "Int", modbits)

def select_type_constructor(name, modbits, context=None):
    return TypeConstructorInvocation(name, modbits)

def select_type_method(typedecl, name, modbits, reciever=None, context=None):
    if context is not None:
        tdef = context.instantiate_type(typedecl)
        return select_method(name, tdef, modbits=modbits, reciever=reciever, context=context)
    else:
        raise ValueError("context is not defined at this timing")

def select_py_callable(fn):
    # Pythonの任意の関数
    from machaon.core.method import (make_method_from_value, METHOD_INVOKEAS_BOUND_FUNCTION)
    mth = make_method_from_value(fn, "<unnamed>", METHOD_INVOKEAS_BOUND_FUNCTION) # 第一引数はレシーバオブジェクト
    return mth.make_invocation()

def expand_constructor_syntax(methodname, typename):
    return "from-" + methodname


#
# 
#
def enum_selectable_method(typetraits, instance=None):
    """
    型で利用可能なセレクタを列挙する
    Params:
        typetraits(Type): 型オブジェクト
        *instance(Any): インスタンス
    Yields:
        Tuple[List[str], Method|Exception, bool]: 名前と全エイリアス, メソッド（または読み込み時に起きたエラー）
    """
    # 型メソッドの列挙
    for names, meth in typetraits.enum_methods():
        yield names, meth
        
    if not typetraits.is_selectable_instance_method():
        return
    
    # インスタンスメソッドの列挙
    if instance is not None:
        valtype = type(instance)
    else:
        valtype = typetraits.get_value_type()
        instance = valtype

    for name, meth in enum_methods_from_type_and_instance(valtype, instance):
        # TypeMethodと被りがある場合はスキップ
        if typetraits.is_selectable_method(name):
            continue        
        yield [name], meth

#
#
#
class AffixedSelector:
    suffixes = [
        ("TRAILING_ARGS", SIGIL_SELECTOR_TRAILING_ARGS),
        ("CONSUME_ARGS", SIGIL_SELECTOR_CONSUME_ARGS),
        ("IGNORE_ARGS", SIGIL_SELECTOR_IGNORE_ARGS),
        ("NEGATE_RESULT", SIGIL_SELECTOR_NEGATE_RESULT),
        ("BASIC_RECIEVER", SIGIL_SELECTOR_BASIC_RECIEVER), 
        ("SHOW_HELP", SIGIL_SELECTOR_SHOW_HELP),
    ]
    sigils_suffixes = {ch:name for name,ch in suffixes}

    @classmethod
    def get_modifier(cls, ch, *, fallback=False):
        name = cls.sigils_suffixes.get(ch)
        if name is not None:
            return name
        if not fallback:
            raise ValueError("Invalid modifier character: " + ch)
        return None

    def __init__(self, selector, flags):
        self._selector = selector
        self._flags = set(flags)

    def __repr__(self):
        parts = [self._selector] + list(self._flags)
        return "<{}>".format(" ".join(parts))

    @classmethod
    def parse(cls, selector):
        if len(selector) < 2:
            return AffixedSelector(selector, set())

        flags = set()
        post_offset = None
        for name, token in cls.suffixes:
            if selector.endswith(token):
                flags.add(name)
                post_offset = -len(token)
                break
        
        sel = selector[0:post_offset]
        if is_modifiable_selector(sel):
            return AffixedSelector(sel, flags)
        else:
            return AffixedSelector(selector, set())

    def selector(self):
        return self._selector

    def affixes(self):
        return self._flags

    def has(self, sigil_name):
        return sigil_name in self._flags



# --------------------------------------------------------------------
#
# 文字列からメッセージを組み立てつつ実行する
#
# --------------------------------------------------------------------
# 文字列から文字の意味を決める
CHAR_END_TERM = 1
CHAR_END_QUOTE = 2

# 式の文字列をトークンへ変換
TOKEN_NOTHING               = 0
TOKEN_TERM                  = 0x01
TOKEN_FIRSTTERM             = 0x02
TOKEN_ENDTERM               = 0x04
TOKEN_STRING                = 0x08
TOKEN_SYNTACTIC             = 0x10
# 構文上の命令 - TOKEN_SYNTACTICと組み合わる
SYNTAX_CODE_MASK                 = 0xF0000
SYNTAX_CODE_BEGIN_MESSAGE        = 0x10000
SYNTAX_CODE_END_MESSAGE          = 0x20000
SYNTAX_CODE_DISCARD_MESSAGE      = 0x30000
# BEGIN_MESSAGEの下位ビット
SYNTAX_CODE_MESSAGE_BLOCK        = 0x01000
SYNTAX_CODE_MESSAGE_DEFERRED     = 0x02000

#  - 要素の種類
TERM_TYPE_MASK     = 0xF0
TERM_TYPE_RECIEVER = 0x10
TERM_TYPE_SELECTOR = 0x20
TERM_TYPE_ARGUMENT = 0x40

EXPECT_NOTHING = 0
EXPECT_RECIEVER = TERM_TYPE_RECIEVER
EXPECT_SELECTOR = TERM_TYPE_SELECTOR
EXPECT_ARGUMENT = TERM_TYPE_ARGUMENT


def testvoid(ch, issep):
    if ch is None or issep(ch):
        return True
    return False

def testchar(ch, *lch):
    if ch not in lch:
        return False
    return True

def teststring(ch, ch2, s):
    if ch == s[0] and ch2 == s[1]:
        return True
    return False


class MessageCharBuffer:
    def __init__(self):
        self.buffer = [] # type: list[str]
        self.quote_beg = None
        self.quote_end = None
        self.quote_buf = []
        self.lastflush = ""
        self._readlength = 0
        self._is_separator = str.isspace

    def flush(self):
        string = "".join(self.buffer)
        self.lastflush = string
        self.buffer.clear()
        return len(string) > 0

    def last(self):
        return self.lastflush
    
    def add(self, ch):
        self.buffer.append(ch)
    
    def quoting(self):
        return self.quote_beg is not None
    
    def begin_quote(self, newch, endch):
        self.quote_beg = newch
        self.quote_end = endch
        self.buffer.clear()

    def check_quote_end(self, ch):
        if not self.quoting() or self.quote_end is None:
            return False

        self.quote_buf.append(ch)
        if len(self.quote_buf) < len(self.quote_end):
            return False

        if self.quote_buf[-1] != self.quote_end[-1]:
            self.quote_buf.clear()
            return False
        
        if len(self.quote_end) > 1:
            for i in range(2, len(self.quote_end)):
                if self.quote_buf[-i] != self.quote_end[-i]:
                    self.quote_buf.clear()
                    return False
        
        self.quote_beg = None
        self.quote_end = None
        self.quote_buf.clear()
        return True

    def read_char(self, s):
        """
        文字列をメッセージで使う文字のタイプに分ける。
        """
        length = len(s)
        def char(i):
            if 0<=i and i<length:
                return s[i]
            return None
        issep = self._is_separator

        self._readlength = 0
        quote_symbol_waiting = False
        while True:
            i = self._readlength
            if i >= length:
                break
            self._readlength += 1

            ch = s[i]

            if is_triming_control_char(ord(ch)):
                continue

            if quote_symbol_waiting:
                if issep(ch):
                    self.begin_quote(ch, ch)
                else:
                    self.begin_quote(ch, QUOTE_ENDPARENS.get(ch,ch))
                quote_symbol_waiting = False
                continue # 引用符記号自体をスキップする

            pch = char(i-1)
            nch = char(i+1)
            
            pVOID = testvoid(pch, issep)
            nVOID = testvoid(nch, issep)

            if self.quoting():
                if nVOID and self.check_quote_end(ch): # 引用符の後ろにスペースを必要とする
                    yield CHAR_END_QUOTE
                    self._readlength += 1 # 次のスペースを一つ飛ばす
                else:
                    yield ch
                continue

            if pVOID and testchar(ch, *SIGIL_QUOTERS):
                # 引用符で囲まれた単語
                self.begin_quote(ch, ch)
            elif pVOID and teststring(ch, nch, SIGIL_BEGIN_USER_QUOTER):
                # ユーザー定義の引用符
                quote_symbol_waiting = True
                self._readlength += 1 # USER_QUOTERの次の文字へ
            elif pVOID and teststring(ch, nch, SIGIL_LINE_QUOTER):
                # 行末までの引用符
                self.begin_quote(SIGIL_LINE_QUOTER, None)
                self._readlength += 1 # LINE_QUOTERの次の文字へ
            else:
                # それ以外のメッセージを構成する文字
                if issep(ch):
                    yield CHAR_END_TERM
                else:
                    yield ch

    def get_read_length(self):
        return self._readlength

#
LEN_SIGIL_BEGIN_MESSAGE = len(SIGIL_BEGIN_MESSAGE)

class MessageTokenizer:
    """ 
    """
    def __init__(self):
        self.buffer = MessageCharBuffer()
        self._wait_firstterm = True
        self._last_read_length = 0

    def set_next_token_firstterm(self):
        self._wait_firstterm = True

    def pop_last_read(self, source):
        l = self.buffer.get_read_length()
        s = source[self._last_read_length:l]
        self._last_read_length = l
        return s
    
    def split_read(self, source):
        l = self.buffer.get_read_length()
        return source[0:l], source[l:]
    
    def parse_block_head(self, s):
        tokentype = TOKEN_SYNTACTIC | SYNTAX_CODE_BEGIN_MESSAGE
        if s == SIGIL_BEGIN_MESSAGE:
            pass
        elif s == SIGIL_BEGIN_MESSAGE_BLOCK:
            tokentype |= SYNTAX_CODE_MESSAGE_BLOCK
        elif s == SIGIL_BEGIN_MESSAGE_DEFERRED:
            tokentype |= SYNTAX_CODE_MESSAGE_DEFERRED
        else:
            return None, None
        return tokentype, ""
    
    def parse_block_tail(self, s):
        tokentype = TOKEN_SYNTACTIC | SYNTAX_CODE_END_MESSAGE
        rest = s[0:-len(SIGIL_END_MESSAGE)]
        mod = ""
        i = 0
        l = len(rest)
        if i+2 < l and rest[i] == "[" and rest[-1] == "]":
            mod = rest[i+1:-1]
            i = l
        if i != l:
            return None, None
        else:
            return tokentype, mod

    def new_token(self, s, tokentype=0):
        # 構文記号
        if tokentype & TOKEN_STRING == 0:
            if s == SIGIL_BEGIN_MESSAGE:
                tokentype |= TOKEN_SYNTACTIC | SYNTAX_CODE_BEGIN_MESSAGE
                s = ""
            elif s == SIGIL_BEGIN_MESSAGE_BLOCK:
                tokentype |= TOKEN_SYNTACTIC | SYNTAX_CODE_BEGIN_MESSAGE | SYNTAX_CODE_MESSAGE_BLOCK
                s = ""
            elif s == SIGIL_BEGIN_MESSAGE_DEFERRED:
                tokentype |= TOKEN_SYNTACTIC | SYNTAX_CODE_BEGIN_MESSAGE | SYNTAX_CODE_MESSAGE_DEFERRED
                s = ""
            elif s.endswith(SIGIL_END_MESSAGE):
                tt, ts = self.parse_block_tail(s)
                if tt is not None:
                    tokentype |= tt
                    s = ts
                else:
                    tokentype |= TOKEN_TERM
            elif s == SIGIL_DISCARD_MESSAGE:
                tokentype |= TOKEN_SYNTACTIC | SYNTAX_CODE_DISCARD_MESSAGE
                s = ""
        
        if s and tokentype & TOKEN_SYNTACTIC == 0:
            tokentype |= TOKEN_TERM
        
        if self._wait_firstterm: 
            tokentype |= TOKEN_FIRSTTERM
            if tokentype & TOKEN_TERM:
                self._wait_firstterm = False
        
        return (s, tokentype)
    
    def read_token(self, source):
        new_token = self.new_token
        buf = self.buffer
        for c in buf.read_char(source):
            if isinstance(c, int):
                if c == CHAR_END_TERM:
                    tokentype = 0
                elif c == CHAR_END_QUOTE:
                    tokentype = TOKEN_STRING
                else:
                    raise ValueError(c)
                if buf.flush(): 
                    yield new_token(buf.last(), tokentype)
            elif isinstance(c, str):
                # バッファに文字を追加する
                buf.add(c)
        
        # バッファに残っている文字を処理する
        buf.flush()
        term = buf.last()
        if buf.quoting():
            yield new_token(term, TOKEN_ENDTERM|TOKEN_STRING)
        else:
            yield new_token(term, TOKEN_ENDTERM)


#
#
#

# 内部コード関数に渡す引数の指定
_INTLCODE_ARG = 1
_INTLCODE_AST_ADDER = 2
_INTLCODE_AST = 3
_INTLCODE_AST_BLOCK = 4

def _intlcode_WITH_ARGOBJECTS(evalcontext, objs):
    return [evalcontext, objs]

def _intlcode_WITH_CONTEXT(evalcontext, objs):
    return [evalcontext.context]

def _intlcode_WITH_EVALCONTEXT(evalcontext, objs):
    return [evalcontext]


def _ast(fn):
    fn.argspec = lambda *a:()
    fn.rank = _INTLCODE_AST
    return fn

def _ast_ADDER(fn):
    fn.argspec = _intlcode_WITH_ARGOBJECTS
    fn.rank = _INTLCODE_AST_ADDER
    return fn

def _ast_BLOCK(fn):
    fn.argspec = _intlcode_WITH_EVALCONTEXT
    fn.rank = _INTLCODE_AST_BLOCK
    return fn

def _ast_ARG(fn):
    fn.argspec = _intlcode_WITH_CONTEXT
    fn.rank = _INTLCODE_ARG
    return fn


class InternalEngineCode:
    def __init__(self):
        self.arg_codes = []
        self.ast_codes = []

    def add(self, c, *args):
        entry = (c, args, c.argspec, c.rank)
        if c.rank == _INTLCODE_ARG:
            self.arg_codes.append(entry)
        else:
            self.ast_codes.append(entry)

    def run(self, evalcontext):
        """ コードを実行する """
        argobjs = []

        # 引数オブジェクトを構築する
        for (c, a, aspec, _) in self.arg_codes:
            ret = c(*aspec(evalcontext, argobjs), *a)
            if isinstance(ret, tuple):
                argobjs.extend(ret)
            else:
                argobjs.append(ret)

        # 構文を組み立てる
        for (c, a, aspec, _) in sorted(self.ast_codes, key=lambda x:x[3]):
            c(*aspec(evalcontext, argobjs), *a)

    def instructions(self):
        """ 命令の内容を表示する """
        
        args = [(x[0].__name__, x[1]) for x in self.arg_codes]

        i = 0
        for c, options, _aspec, _rank in sorted(self.ast_codes, key=lambda x:x[3]):
            if i == 0: # ADDER
                if options:
                    a = options[0]
                    if a == TERM_TYPE_RECIEVER:
                        a = "reciever"
                    elif a == TERM_TYPE_SELECTOR:
                        a = "selector"
                    elif a == TERM_TYPE_ARGUMENT:
                        a = "argument"
                    options = (a, *options[1:])
                yield (c.__name__, options, args)
            else:
                yield (c.__name__, options, None)
            i += 1

    def display_instructions(self):
        """ 文字列にまとめて返す """
        ls = []
        for instrname, options, args in self.instructions():
            parts = []
            parts.append(instrname)
            if options:
                opts = (str(x) for x in options)
                parts.append(" ".join(opts))
            if args is not None:
                argsline = []
                for argcode, vals in args:
                    arg = [str(x) for x in [argcode, *vals]]
                    argsline.append(" ".join(arg))
                parts.append("> " + " > ".join(argsline))
            ls.append(" ".join(parts))
        return ls


#
#
#
class MessageEngine:
    def __init__(self, expression="", messages=None):
        self.source = expression
        self._tokens = None  # type: MessageTokenizer
        self._readings = []  # type: list[Message]
        self._curblockstack = [] # type: list[int]
        self._closingblock = 0
        self._msgs = messages or []
        self._lastread = ""  # 最後に完成したメッセージの文字列
        self._lastevalcxt = None
        self._lastblockcomplete = False # メッセージが完結した直後である

    def __repr__(self) -> str:
        return "<MessageEngine ({})>".format(self.source)
    
    def get_expression(self) -> str:
        """ コード文字列を返す """
        return self.source
    
    def split_read_expression(self):
        """ 実行の済んだ部分と、未実行の部分を分けてコードを返す 
        Returns:
            str, str:
        """
        if self._tokens is None:
            raise ValueError("まだ実行が開始されていません")
        return self._tokens.split_read(self.source)
    
    def begin_message(self, evalcontext, *args):
        """ メッセージを未完成スタックに追加する """
        msg = Message(*args)
        self._readings.append(msg)
        # ログに残す
        index = len(self._readings)-1
        evalcontext.context.log_message_ast(index, 1)
        
    def begin_block(self, evalcontext):
        """ ブロックを開始する """
        newpos = self.current_message_top()  # 上でメッセージを追加済み
        self._curblockstack.append(newpos)   # 新しいブロックの番号を記録する
        evalcontext.context.log_message_ast(newpos, 10)

    def current_message_top(self):
        return len(self._readings)-1

    def current_block_top(self):
        if self._curblockstack:
            return self._curblockstack[-1]
        else:
            return -1 # トップレベルにある

    def current_block_messages(self):
        """ ブロックの先頭までのメッセージインデクスを取得する """
        top = self.current_block_top()
        i = len(self._readings)-1
        while i >= 0:
            if i < top:
                break 
            yield i, self._readings[i]
            i -= 1

    def check_within_current_block(self, message_index):
        """ 現在のブロック内にあれば、True """
        if self._curblockstack and self._curblockstack[-1] > message_index:
            return False
        return True
    
    def end_message(self):
        """ メッセージをスタックから取り除く """
        if self._readings:
            self._readings.pop()

    def end_block(self, count=None):
        """ ブロックを取り除く """
        if count is not None:
            del self._curblockstack[-count:]
        elif self._closingblock > 0:
            del self._curblockstack[-self._closingblock:]
            self._closingblock = 0

    def modify_last_block_selector(self, pos, modifier):
        """ メッセージにモディファイアを設定する """
        mod = AffixedSelector.get_modifier(modifier)
        index = pos - 1
        if len(self._readings) < -index:
            raise ValueError("Enough number of message does not exist")
        self._readings[index].set_selector_modifier(mod)

    # 
    def build_next_code(self, token: str, tokentype: int):
        """
        トークンから内部コードを生成する
        Params:
            token(str): 文字列
            tokentype(int): 文字列の意味(TOKEN_XXX)
        Returns:
            InternalEngineCode: 還元された命令コードと引数のセット
        """
        # 構築中のメッセージを取得する
        top = self.current_block_top()
        mindex = self.current_message_top()
        if 0 <= mindex and top <= mindex:
            reading = self._readings[mindex]
        else:
            reading = None
        
        if reading is None:
            expect = EXPECT_NOTHING
        elif not reading.is_reciever_specified():
            expect = EXPECT_RECIEVER
        elif not reading.is_selector_specified():
            expect = EXPECT_SELECTOR
        else:
            expect = EXPECT_ARGUMENT

        #
        code = InternalEngineCode()

        # ブロックの最後のトークンである
        if tokentype & TOKEN_ENDTERM:
            code.add(self.ast_END_ALL_BLOCKS)

        # エスケープされた文字列
        isstringtoken = tokentype & TOKEN_STRING > 0

        # 構文用の特殊な記号
        if tokentype & TOKEN_SYNTACTIC > 0:
            sycode = tokentype & SYNTAX_CODE_MASK
            # 明示的なブロックの開始
            if sycode == SYNTAX_CODE_BEGIN_MESSAGE:
                if expect == EXPECT_NOTHING:
                    if tokentype & TOKEN_FIRSTTERM:
                        # レシーバのメッセージとする
                        code.add(self.ast_ADD_NEW_MESSAGE)
                    else:
                        # 先行する値をレシーバとするセレクタのメッセージとする
                        code.add(self.arg_STACK_REF)
                        code.add(self.ast_ADD_TWIN_NEW_MESSAGE)
                else:
                    # 前のメッセージの要素とする
                    code.add(self.ast_ADD_ELEMENT_AS_NEW_MESSAGE, expect)
                if tokentype & SYNTAX_CODE_MESSAGE_DEFERRED > 0:
                    code.add(self.ast_BEGIN_BLOCK, "deferred")
                elif tokentype & SYNTAX_CODE_MESSAGE_BLOCK > 0:
                    code.add(self.ast_BEGIN_BLOCK)
                return code
            # 引数リストの終わり
            elif sycode == SYNTAX_CODE_END_MESSAGE:
                if top == mindex and top != -1:
                    # ブロックを終了しようとしている（トップレベルは閉じない）
                    code.add(self.ast_END_BLOCK, mindex, token)
                elif top > mindex:
                    # 直ちにブロックを削除する
                    code.add(self.ast_END_LAST_BLOCK, mindex, top, token)
                elif top < mindex:
                    # 引数リストを終了する
                    if expect == EXPECT_ARGUMENT:
                        code.add(self.ast_END_MESSAGE, mindex, top, token)
                    else:
                        raise BadExpressionError("メッセージを閉じようとしましたが、要素が足りていません")
                    if token:
                        raise BadExpressionError("ブロックモディファイアは、ブロックの終わりでのみ有効です")
                elif top == mindex and self._lastblockcomplete:
                    if expect == EXPECT_NOTHING:
                        return None # 何もしない
                    else:
                        raise BadExpressionError("メッセージを閉じようとしましたが、要素が足りていません")
                else:
                    raise BadExpressionError("メッセージの閉じ記号を解釈できません")

            # メッセージの連鎖をリセットする
            elif sycode == SYNTAX_CODE_DISCARD_MESSAGE:
                if expect == EXPECT_NOTHING:
                    code.add(self.ast_DISCARD_LAST_BLOCK_MESSAGE)
                    return code
                raise BadExpressionError("メッセージの要素が足りません")

        # メッセージの要素ではない
        if (tokentype & TOKEN_TERM) == 0:
            return code

        #
        # 以下、メッセージの要素として解析
        # 

        # オブジェクト参照
        if not isstringtoken and token.startswith(SIGIL_OBJECT_ID):
            if expect == EXPECT_SELECTOR:
                raise BadExpressionError("セレクタが必要です") 

            def new_block_bits(c):
                if expect == EXPECT_NOTHING:
                    c.add(self.ast_ADD_NEW_MESSAGE)
                else:
                    c.add(self.ast_ADD_ELEMENT_AS_NEW_MESSAGE, expect)
                return c

            objid = token[1:]
            if not objid: 
                # 無名関数の引数オブジェクト
                code.add(self.arg_LAMBDA_ARG_MEMBER)
            
            elif SIGIL_OBJECT_LAMBDA_MEMBER in objid:
                # 引数オブジェクトのメンバ参照
                objid, _, memberid = token.partition(SIGIL_OBJECT_LAMBDA_MEMBER)
                if not memberid:
                    raise BadExpressionError("'{}'のあとにセレクタが必要です".format(SIGIL_OBJECT_LAMBDA_MEMBER))
                code.add(self.arg_LAMBDA_ARG_MEMBER, memberid)

                return new_block_bits(code)
                
            elif objid[0] == SIGIL_OBJECT_ROOT_MEMBER:
                # ルートオブジェクトの参照
                memberid = token[2:]
                if memberid:
                    # メンバ参照
                    code.add(self.arg_ROOT_MEMBER, memberid)
                else:
                    # ルートオブジェクト自体を参照
                    code.add(self.arg_ROOT_MEMBER)
                return new_block_bits(code)
                
            elif objid[0] == SIGIL_OBJECT_PREVIOUS:
                # 逆順のインデックスによるオブジェクトの参照
                memberid = objid[1:]
                if memberid == "":
                    memberid = "1"
                if memberid.isdigit():
                    index = int(memberid) # 数値を取得する
                    code.add(self.arg_REF_PREVIOUS, index)
                else:
                    code.add(self.arg_REF_NAME, objid)
                
            elif objid.isdigit():
                # 数値名称のオブジェクト
                objid = str(int(objid)) # 数値表現を正規化
                code.add(self.arg_REF_NAME, objid)
            
            else:
                # 通常の名称のオブジェクト
                code.add(self.arg_REF_NAME, objid)

            if expect == EXPECT_NOTHING:
                code.add(self.ast_ADD_NEW_MESSAGE) # 新しいメッセージのレシーバになる
            else:
                code.add(self.ast_ADD_ELEMENT_TO_LAST_MESSAGE, expect) # 前のメッセージの要素になる
            return code

        # 何も印のない文字列
        #  => メソッドかリテラルか、文脈で判断
        if expect == EXPECT_SELECTOR and reading:
            self._add_selector_code(code, token)
            code.add(self.ast_ADD_ELEMENT_TO_LAST_MESSAGE, expect) # 前のメッセージのセレクタになる
            return code

        if expect == EXPECT_ARGUMENT:           
            # メソッドの型要求に従って解釈する 
            spec = reading.get_next_parameter_spec()
            typename = spec.typename if spec else None
            if typename == "Type":
                code.add(self.arg_TYPE, token)
            elif typename == "Tuple":
                code.add(self.arg_TUPLE, token)
            elif spec.is_type_unspecified():
                if isstringtoken:
                    code.add(self.arg_STRING, token)
                else:
                    code.add(self.arg_LITERAL, token)
            else:
                code.add(self.arg_TYPED_VALUE, token, spec)            
            # 前のメッセージの引数になる
            code.add(self.ast_ADD_ELEMENT_TO_LAST_MESSAGE, expect) 
            return code

        if expect == EXPECT_RECIEVER:
            if isstringtoken:
                code.add(self.arg_STRING, token)
            else:
                code.add(self.arg_RECIEVER_VALUE, token)
            code.add(self.ast_ADD_ELEMENT_TO_LAST_MESSAGE, expect)
            return code

        if expect == EXPECT_NOTHING:
            if tokentype & TOKEN_FIRSTTERM:
                # メッセージの先頭のみ、レシーバオブジェクトのリテラルとする
                if isstringtoken:
                    code.add(self.arg_STRING, token)
                else:
                    code.add(self.arg_RECIEVER_VALUE, token)
                code.add(self.ast_ADD_NEW_MESSAGE)
                return code
            else:
                # 先行するメッセージの返り値をレシーバとするセレクタとする
                code.add(self.arg_STACK_REF)
                self._add_selector_code(code, token)
                code.add(self.ast_ADD_NEW_MESSAGE)
                return code
        
        raise BadExpressionError("Could not parse")

    def _add_selector_code(self, code, selector_token):
        selector = AffixedSelector.parse(selector_token)
        if selector.has("SHOW_HELP"):
            code.add(self.ast_SET_AS_SELECTOR_RETURNER)
        code.add(self.arg_SELECTOR_VALUE, selector)


    #
    #  メッセージを構築する
    #
    @_ast_ADDER
    def ast_ADD_ELEMENT_TO_LAST_MESSAGE(self, _evalcontext, objs, ttpcode):
        """ """
        if ttpcode == TERM_TYPE_RECIEVER:
            i = 0
        elif ttpcode == TERM_TYPE_SELECTOR:
            i = 1
        elif ttpcode == TERM_TYPE_ARGUMENT:
            i = 2
        else:
            i = 0

        for obj in objs:
            if i == 0:
                self._readings[-1].set_reciever(obj)
            elif i == 1:
                self._readings[-1].set_selector(obj)
            elif i > 1:
                self._readings[-1].add_arg(obj)
            i += 1

    @_ast_ADDER
    def ast_ADD_ELEMENT_AS_NEW_MESSAGE(self, evalcontext, objs, ttpcode):
        """ """
        if ttpcode == TERM_TYPE_RECIEVER:
            self._readings[-1].set_reciever(ResultStackRef())

        elif ttpcode == TERM_TYPE_SELECTOR:
            self._readings[-1].set_selector(ResultStackRef())
        
        elif ttpcode == TERM_TYPE_ARGUMENT:
            self._readings[-1].add_arg(ResultStackRef())
        
        self.begin_message(evalcontext, *objs)

    @_ast_ADDER
    def ast_ADD_NEW_MESSAGE(self, evalcontext, objs):
        """ """
        self.begin_message(evalcontext, *objs)

    @_ast_ADDER
    def ast_ADD_TWIN_NEW_MESSAGE(self, evalcontext, objs):
        """ """
        self.begin_message(evalcontext, *objs, ResultStackRef()) # 最後の要素が次のメッセージ
        self.begin_message(evalcontext) # 空のメッセージを追加する

    @_ast_BLOCK
    def ast_BEGIN_BLOCK(self, evalcontext, blocktype=None):
        """  """
        self.begin_block(evalcontext)

    @_ast_BLOCK
    def ast_END_MESSAGE(self, evalcontext, index, top, modifier=None):
        """ 引数リストを終了するか、何もしない """        
        self._readings[index].conclude_explicit()
        evalcontext.context.log_message_ast("{}, {}".format(index, top), 2)

    @_ast_BLOCK
    def ast_END_BLOCK(self, evalcontext, index, modifier=None):
        """ ブロックを終了しようとしている """
        for i, msg in self.current_block_messages():
            msg.conclude_explicit()
            evalcontext.context.log_message_ast(i, 2)
        self._closingblock += 1
        evalcontext.context.log_message_ast(index, 20)
        # 一つ上のメッセージにモディファイアを設定
        if modifier:
            self.modify_last_block_selector(-1, modifier)

    @_ast_BLOCK
    def ast_END_LAST_BLOCK(self, evalcontext, index, top, modifier=None):
        """ 直ちにブロックを削除する """
        # 直ちにブロックを削除する
        self.end_block(1)
        # 現在のメッセージにモディファイアを設定
        if modifier:
            self.modify_last_block_selector(0, modifier)
        evalcontext.context.log_message_ast("{}, {}".format(index, top), 21)

    @_ast_BLOCK
    def ast_END_ALL_BLOCKS(self, evalcontext):
        """ """
        for i, msg in enumerate(reversed(self._readings)):
            j = len(self._readings) - i - 1
            msg.conclude_explicit()
            evalcontext.context.log_message_ast(j, 2) 
        self._closingblock = len(self._curblockstack)
        evalcontext.context.log_message_ast(None, 22)

    @_ast
    def ast_DISCARD_LAST_BLOCK_MESSAGE(self):
        """ """
        if self._tokens is None:
            raise ValueError("Any message has not been read")
        self._tokens.set_next_token_firstterm() # 次にバッファから読みだすトークンはfirsttermになる
    
    @_ast
    def ast_SET_AS_SELECTOR_RETURNER(self, evalcontext):
        """ 直前のメッセージをセレクタを返すメッセージに変える """
        self._readings[-1].as_selector_returner(evalcontext)
    
    ast_SET_AS_SELECTOR_RETURNER.argspec = _intlcode_WITH_EVALCONTEXT

    #
    #  引数を構築する
    #
    @_ast_ARG
    def arg_REF_NAME(self, context, name):
        """ """
        return ObjectRef(name)

    @_ast_ARG
    def arg_REF_PREVIOUS(self, context, name):
        """ """
        return PreviousObjectRef(name)

    @_ast_ARG
    def arg_STRING(self, context, value):
        """ """
        return context.new_object(value, type="Str")

    @_ast_ARG
    def arg_TYPE(self, context, typeexpr):
        """ """
        return select_type(context, typeexpr)

    @_ast_ARG
    def arg_TUPLE(self, context, value):
        """ """
        elems = value.split() # 文字列を空白で区切る
        return context.get_type("Tuple").construct_obj(context, elems)

    @_ast_ARG
    def arg_LITERAL(self, context, value):
        """ """
        return select_literal(context, value)

    @_ast_ARG
    def arg_TYPED_VALUE(self, context, value, spec):
        """ """
        type = spec.get_typedecl().instance(context)
        return type.construct_obj(context, value)

    @_ast_ARG
    def arg_RECIEVER_VALUE(self, context, reciever):
        """ """
        if reciever and reciever[0].isupper():
            if reciever.endswith(SIGIL_SELECTOR_TRAILING_ARGS):
                tt = select_type(context, reciever[:-1])
                if tt:
                    return (tt, SelectorResolver("instance"+SIGIL_SELECTOR_TRAILING_ARGS))
            else:
                tt = select_type(context, reciever)
                if tt:
                    return (tt,)
            
        return (select_literal(context, reciever),)

    @_ast_ARG
    def arg_SELECTOR_VALUE(self, context, selector):
        """ """
        return SelectorResolver(selector)

    @_ast_ARG
    def arg_STACK_REF(self, context):
        """ """
        return ResultStackRef()

    @_ast_ARG
    def arg_LAMBDA_ARG_MEMBER(self, context, name=None):
        """ """
        reciever = SubjectRef()
        if name:
            return (reciever, SelectorResolver(name))
        else:
            return (reciever, )

    @_ast_ARG
    def arg_ROOT_MEMBER(self, context, member_id=None):
        """ """
        rt = context.get_type("RootObject")
        root = rt.new_object(rt.value_type(context))
        if member_id:
            return (root, SelectorResolver(member_id))
        else:
            return (root, )
    
    #
    #
    #
    def produce_message(self, evalcontext):
        """ コードから構文を組み立てつつ随時実行 """
        self._msgs = []
        self._tokens = MessageTokenizer()
        self._closingblock = 0
        for token, tokentype in self._tokens.read_token(self.source):
            completed = len(self._msgs)

            intlcode = self.build_next_code(token, tokentype)
            if intlcode is not None:
                evalcontext.context.log_message_code(intlcode)
                
                # 内部コードを実行し、メッセージを組み立てる
                intlcode.run(evalcontext)

                # 組みあがったメッセージから実行する
                index = len(self._readings)-1
                while index >= 0:
                    # ブロック外の評価を遅延する
                    if not self.check_within_current_block(index):
                        break
                    # メッセージが完成していなければスキップする
                    msg = self._readings[index]
                    if not msg.check_concluded(evalcontext):
                        break
                    
                    # これから評価するメッセージ式の文字列
                    msgsrc = self._tokens.pop_last_read(self.source)
                    evalcontext.context.log_message_eval(index, msgsrc, msg)

                    yield msgsrc # 文字列を排出
                    yield msg    # 組み立てたメッセージを排出
                    self._msgs.append(msg) # 組みあがったメッセージを保存

                    # メッセージとブロックをスタックから取り除く
                    self.end_message()
                    self.end_block()

                    index -= 1
            
            # スタックから組みあがったメッセージを取り除く
            if len(self._msgs) == completed:
                self._lastblockcomplete = False
            else:
                self._lastblockcomplete = True
    
    def produce_message_cached(self, _evalcontext):
        """ キャッシュされたメッセージをクリアして返す """
        for msg in self._msgs:
            msg.reset_ref()
            yield msg

    def runner(self, context, cache=False):
        """
        メッセージをコンパイルしつつ実行するジェネレータ。
        Yields:
            Message: 実行直前のメッセージ
        """                    
        if cache and self._msgs:
            produce_message = self.produce_message_cached
        else:
            produce_message = self.produce_message

        context.log_message_begin(self.source)

        evalcxt = EvalContext(context)
        self._lastevalcxt = evalcxt
        try:
            for msg in produce_message(evalcxt):
                if isinstance(msg, str):
                    yield msg
                    continue
                else:
                    yield msg
                    result = msg.eval(evalcxt)

                    # 返り値をスタックに乗せる
                    evalcxt.locals.push_local_object(result)
                    if context.is_failed(): # エラーが発生したら実行を中断する
                        return

        except Exception as e:
            # メッセージ実行以外の場所でエラーが起きた
            err = InternalMessageError(e, self, context) # コード情報を付加し、トレース情報を引き継ぐ
            evalcxt.locals.push_local_object(context.new_invocation_error_object(err)) # スタックに乗せる
            context.push_extra_exception(err)
            return

        context.log_message_end()
    
    def finish(self) -> Object:
        """ 結果を取得し、スタックをクリアする """
        context = self._lastevalcxt.context
        
        if self._readings and not context.is_failed():
            raise BadExpressionError("Unconcluded messages remain: {}".format([str(x) for x in self._readings])) # 成功したのにメッセージが余っている
        self._readings.clear()

        returns = self._lastevalcxt.locals.clear_local_objects() # 返り値はローカルスタックに置かれている
        if not returns:
            raise BadExpressionError("At least 1 result must be returned, but none on stack")
        ret = returns[-1]
    
        if context.is_set_raise_error() and ret.is_error(): # エラーを伝播する
            raise ret.value.error

        return ret
    
    def start_subcontext(self, subject, context):
        """ 入れ子のコンテキストを開始する """
        subcontext = context.inherit(subject) # コンテキストが入れ子になる
        context.log_message_begin_sub(subcontext)
        return subcontext
    
    #
    #
    #
    def run(self, subject, context, *, cache=False):
        """ コンテキストを継承してメッセージを実行 """
        if subject is not None:
            # 主題オブジェクトを更新した派生コンテキスト
            subcontext = self.start_subcontext(subject, context)
        else:
            # コンテキストを引き継ぐ
            subcontext = context 
        for _ in self.runner(subcontext, cache=cache):
            pass
        return self.finish()

    def run_here(self, context, *, cache=False) -> Object:
        """ 現在のコンテキストでメッセージを実行 """
        for _ in self.runner(context, cache=cache):
            pass
        return self.finish()

    def run_step(self, subject, context, *, cache=False):
        """ 実行するたびにメッセージを返す """
        subcontext = self.start_subcontext(subject, context)
        for step in self.runner(subcontext, cache=cache):
            yield step
        yield self.finish() # Objectを返す
    
    def run_print_step(self, subject, context, *, cache=False):
        """ 実行過程を表示する """
        app = context.spirit
        indent = "  " * (context.get_depth()-1)
        for msg in self.run_step(subject, context, cache=cache):
            app.interruption_point()
            if isinstance(msg, Object):
                return msg
            elif isinstance(msg, str):
                app.post("message", indent + msg)
    
    def run_function(self, subject, context, *, cache=False) -> Object:
        """ 通常の実行方法：コンテキストのフラグによって実行方法を分岐する """
        if context.is_set_print_step():
            return self.run_print_step(subject, context, cache=cache)
        else:
            return self.run(subject, context, cache=cache)


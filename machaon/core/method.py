from typing import Any, Sequence, List, Dict, Union, Callable, ItemsView, Optional, DefaultDict, Tuple

import inspect
from collections import defaultdict

from machaon.core.symbol import normalize_typename, normalize_method_target, normalize_method_name, normalize_return_typename
from machaon.core.docstring import DocStringParser, parse_doc_declaration

# imported from...
# type
# operator
#
#

#
METHOD_CONTEXT_BOUND = 0x0001
METHOD_SPIRIT_BOUND = 0x0002
METHOD_TASK = 0x0004 | METHOD_SPIRIT_BOUND
METHOD_TYPE_BOUND = 0x0010
METHOD_CONSUME_TRAILING_PARAMS = 0x0020

METHOD_LOADED = 0x0100
METHOD_DECL_LOADED = 0x0200
METHOD_HAS_RECIEVER_PARAM = 0x0400 # レシーバオブジェクトもパラメータとして扱う

METHOD_PARAMETER_UNSPECIFIED = 0x1000
METHOD_RESULT_UNSPECIFIED = 0x2000
METHOD_KEYWORD_PARAMETER = 0x4000
METHOD_UNSPECIFIED_MASK = 0xF000

METHOD_FROM_INSTANCE = 0x10000 
METHOD_FROM_FUNCTION = 0x20000
METHOD_FROM_MASK = 0xF0000

METHOD_META_EXTRAARGS = 0x100000

#
PARAMETER_REQUIRED = 0x0100
PARAMETER_VARIABLE = 0x0200

#
RETURN_SELF = "<return-self>"

#
class BadMethodDeclaration(Exception):
    pass

class UnloadedMethod(Exception):
    pass

class MethodLoadError(Exception):
    def error(self):
        return self.args[0]
    def name(self):
        return self.args[1]

#
class MethodParameterNoDefault:
    pass

#
#
#
class Method():
    """
    メソッド定義。
    """
    def __init__(self, name = None, target = None, doc = "", flags = 0):
        self.name: str = name
        self.doc: str = doc

        self.target: str = target
        self._action = None
        
        self.flags = flags

        self.params: List[MethodParameter] = []
        self.result: Optional[MethodResult] = None

    def check_valid(self):
        if self.name is None:
            raise ValueError("name")
    
    def get_name(self):
        """ @method alias-name [name]
        メソッド名。
        Returns:
            Str:
        """
        if self.flags & METHOD_LOADED == 0:
            raise UnloadedMethod(self.name)
        return self.name
    
    def get_doc(self):
        """ @method alias-name [doc]
        メソッドの説明。
        Returns:
            Str:
        """
        if self.flags & METHOD_LOADED == 0:
            raise UnloadedMethod(self.name)
        return self.doc
    
    def get_action_target(self):
        """ @method alias-name [action-target]
        実装を表す文字列。
        Returns:
            Str:
        """
        if self.flags & METHOD_LOADED == 0:
            raise UnloadedMethod(self.name)
        return self.target
    
    def get_action(self):
        """ 実装オブジェクト。 """
        return self._action

    def is_type_bound(self):
        """ @method
        メソッドに型が渡されるか
        Returns:
            Bool:
        """
        return (self.flags & METHOD_TYPE_BOUND) > 0

    def is_context_bound(self):
        """ @method
        メソッドにコンテキストオブジェクトが渡されるか
        Returns:
            Bool:
        """
        return (self.flags & METHOD_CONTEXT_BOUND) > 0

    def is_spirit_bound(self):
        """ @method
        メソッドにスピリットオブジェクトが渡されるか
        Returns:
            Bool:
        """
        return (self.flags & METHOD_SPIRIT_BOUND) > 0
    
    def is_task(self):
        """ @method
        メソッドがタスク（非同期実行）か
        Returns:
            Bool:
        """
        return (self.flags & METHOD_TASK) == METHOD_TASK
        
    def is_trailing_params_consumer(self):
        """ @method
        可変長引数を持つか
        Returns:
            Bool:
        """
        return (self.flags & METHOD_CONSUME_TRAILING_PARAMS) > 0
    
    def has_reciever_param(self):
        """ レシーバオブジェクトの引数情報があるか """
        return (self.flags & METHOD_HAS_RECIEVER_PARAM) > 0

    # 仮引数を追加
    def add_parameter(self,
        name,
        typename,
        doc = "",
        default = MethodParameterNoDefault,
        variable = False,
        *,
        flags = 0,
        typeparams = None,
    ):
        """
        仮引数を追加する。
        Params:
            name(str): 引数名
            typename(str): 型名
            doc(str): *説明文
            default(Any): *デフォルト値
            variable(bool): *可変長引数であるか
            flags(int): *フラグ
            typeparams(str[]): *型パラメータ
        """
        f = 0
        if flags:
            f |= flags
        if variable:
            f |= PARAMETER_VARIABLE
        if default is MethodParameterNoDefault:
            default = None
            f |= PARAMETER_REQUIRED
        p = MethodParameter(name, typename, doc, default, f, typeparams)
        self.params.append(p)
    
    def get_params(self):
        """ @method alias-name [params]
        仮引数のリスト
        Returns:
            Sheet[MethodParameter]: (name, typename, doc)
        """
        if self.flags & METHOD_PARAMETER_UNSPECIFIED:
            raise UnloadedMethod(self.name)
        return self.params
    
    def get_param(self, index):
        """ 引数の定義を得る。 """
        if self.flags & METHOD_HAS_RECIEVER_PARAM: # func指定に対応
            if index == -1:
                return self.params[0]
            index = index + 1
        if index<0 or len(self.params)<=index:
            return None
        return self.params[index]
    
    def get_param_count(self):
        """ 仮引数の数 """
        if self.flags & METHOD_PARAMETER_UNSPECIFIED:
            raise UnloadedMethod(self.name)
        return len(self.params)

    # 返り値宣言を追加
    def add_result(self, 
        typename, 
        doc = "",
        typeparams = None
    ):
        """
        返り値宣言を追加
        Params:
            typename(str): 型名
            doc(str): *説明文
            typeparams(List[str]): *生成時に引数として与えられる追加の情報
        """
        r = MethodResult(typename, doc, typeparams)
        self.result = r
    
    def add_result_self(self, type):
        """ メソッドのselfオブジェクトを返す """
        r = MethodResult(type.typename, "selfオブジェクト", (RETURN_SELF,))
        self.result = r

    def get_result(self):
        """ @method alias-name [result]
        返り値のリスト
        Returns:
            Sheet[MethodResult]: (name, typename, doc)
        """
        if self.flags & METHOD_RESULT_UNSPECIFIED:
            raise UnloadedMethod(self.name)
        return self.result
    
    def get_acceptable_argument_max(self) -> Union[int, None]:
        """
        受け入れ可能な最大の引数の数を得る。
        Returns:
            int: 個数。Noneで無限を示す
        """
        if self.flags & METHOD_PARAMETER_UNSPECIFIED:
            raise UnloadedMethod(self.name)
        cnt = 0
        for p in self.params:
            if p.is_variable():
                return None
            cnt += 1
        if self.flags & METHOD_HAS_RECIEVER_PARAM:
            cnt -= 1
        return cnt
        
    # 必要な最小の引数の数を得る
    def get_required_argument_min(self) -> int:
        """
        実行に必要な最小の引数の数を得る。
        Returns:
            int: 個数
        """
        if self.flags & METHOD_PARAMETER_UNSPECIFIED:
            raise UnloadedMethod(self.name)
        cnt = 0
        for p in self.params:
            if not p.is_required():
                break
            cnt += 1
        if self.flags & METHOD_HAS_RECIEVER_PARAM:
            cnt -= 1
        return cnt
    
    def load(self, this_type):
        """
        実装をロードする。
        """
        if self.flags & METHOD_LOADED:
            return

        if self.target is None:
            self.target = normalize_method_target(self.name)

        # 実装コードを読み込む
        from machaon.core.importer import attribute_loader
        action = None
        source = None
        while True:
            callobj = None
            if self.target.startswith("."):
                # 外部モジュールから定義をロードする
                loader = attribute_loader(self.target)
                callobj = loader() # モジュールやメンバが見つからなければ例外が投げられる
                source = self.target
            else:
                # クラスに定義されたメソッドが実装となる
                typefn = this_type.delegate_method(self.target)
                if typefn is not None:
                    callobj = typefn
                    source = "{}:{}".format(this_type.get_scoped_typename(), self.name)
                    if this_type.is_methods_type_bound():
                        self.flags |= METHOD_TYPE_BOUND # 第1引数は型オブジェクト、第2引数はインスタンスを渡す
            
            # アクションオブジェクトの初期化処理
            if hasattr(callobj, "describe_method"):
                # アクションに定義されたメソッド定義処理があれば実行
                callobj.describe_method(self)
            elif hasattr(callobj, "__doc__") and callobj.__doc__ is not None:
                # callobjのdocstringsを解析する
                self.parse_syntax_from_docstring(callobj.__doc__, callobj)
            else:
                raise BadMethodDeclaration("メソッド定義がありません。メソッド 'describe_method' かドキュメント文字列で記述してください")
        
            if isinstance(callobj, type):
                callobj = callobj()
        
            if callobj is not None and callable(callobj):
                action = callobj
                break
            
            raise ValueError("無効なアクションです：{}".format(self.target))
        
        # 返り値が無い場合はレシーバ自身を返す
        if not self.result:
            self.add_result_self(this_type)
        
        if self.flags & METHOD_UNSPECIFIED_MASK:
            self._action = None
        else:
            self._action = action
        self.target = source
        self.flags |= METHOD_LOADED
    
    def is_loaded(self):
        """ ロードされているか。 """
        return self._action is not None

    def parse_syntax_from_docstring(self, doc: str, function: Callable = None):
        """ 
        docstringの解析で引数を追加する。
        Params:
            doc(str): docstring
            function(Callable): *関数の実態。引数デフォルト値を得る
        """
        # 1行目はメソッド宣言
        decl = parse_doc_declaration(doc, ("method", "task"))
        if decl is None:
            raise BadMethodDeclaration("宣言の構文に誤りがあります")   
        if self.flags & METHOD_DECL_LOADED == 0:         
            self.load_declaration_properties(decl.props)
        
        # 定義部
        sections = decl.create_parser((
            "Params Parameters Arguments Args",
            "Returns", 
        ))

        # 説明文
        desc = sections.get_string("Document")
        if desc:
            self.doc = desc.strip()

        # 関数シグネチャを取得し引数情報の参考にする
        funcsig = None
        if function:
            funcsig = inspect.signature(function)
        
        # 引数
        lines = sections.get_lines("Params")
        for line in lines:
            head, _, paramdoc = [x.strip() for x in line.partition(":")]
            if not head and not paramdoc:
                continue # 空の行

            flags = 0
            if head.startswith("*"):
                name, _, right = head[1:].partition("(")
                if right:
                    typename, _, _ = right.partition(")")
                    typename = typename.strip()
                else:
                    typename = "Any"
                flags |= PARAMETER_VARIABLE
            else:
                name, _, paren = head.partition("(")
                name = name.strip()
                typename, _, _ = paren.partition(")")
                typename = typename.strip()
            
            if not name or not typename:
                raise BadMethodDeclaration("引数'{}'の型指定が間違っています。「引数名(型名): 説明文」と指定してください".format(name))
        
            if typename.endswith("..."):
                self.flags |= METHOD_CONSUME_TRAILING_PARAMS
                typename = typename.rstrip(".")
            
            if funcsig:
                p = funcsig.parameters.get(name)
                if p is None:
                    raise BadMethodDeclaration("存在しない引数です：" + name)
                
                default = p.default
                if default is inspect.Signature.empty:
                    default = None
                    flags |= PARAMETER_REQUIRED
                
                if p.kind == p.VAR_KEYWORD or p.kind == p.KEYWORD_ONLY:
                    flags |= METHOD_PARAMETER_UNSPECIFIED | METHOD_KEYWORD_PARAMETER
                    break
            
            typename, paramdoc, typeparams = parse_typename_syntax(typename, paramdoc)
            self.add_parameter(name, typename, paramdoc, default, flags=flags, typeparams=typeparams)

        # 戻り値
        lines = sections.get_lines("Returns")
        for line in lines:
            typename, _, doc = [x.strip() for x in line.partition(":")]
            if not typename:
                continue

            typename, doc, typeparams = parse_typename_syntax(typename, doc)
            self.add_result(typename, doc, typeparams)
        
    def load_declaration_properties(self, props: Sequence[str]):
        """
        宣言の値を読み込んでフラグを設定する
        """
        if "spirit" in props:
            self.flags |= METHOD_SPIRIT_BOUND
        if "context" in props:
            self.flags |= METHOD_CONTEXT_BOUND
        if "reciever-param" in props:
            self.flags |= METHOD_HAS_RECIEVER_PARAM
        if "task" in props:
            self.flags |= METHOD_TASK
        if "nospirit" in props:
            self.flags &= ~METHOD_SPIRIT_BOUND
        
        self.flags |= METHOD_DECL_LOADED
            
    def load_from_function(self, fn, self_typename=None):
        """
        関数オブジェクトから引数を解析しアクションとしてロードする。
        Params:
            fn(Any): 関数オブジェクト
            self_typename(str): *インスタンスの（Pythonの）型名
        """
        if self.flags & METHOD_LOADED:
            return 
        
        self.doc = fn.__doc__ or ""
        
        # 戻り値
        self.add_result("Any") # 不明だが、値から推定する

        # シグネチャを関数から取得
        try:
            sig = inspect.signature(fn)
        except ValueError:
            # ビルトイン関数なので情報を取れなかった
            if self_typename:
                # 第一引数が指定されていれば設定しておく
                self.add_parameter("self", self_typename, flags=PARAMETER_REQUIRED)
                self.flags |= METHOD_HAS_RECIEVER_PARAM
            else:
                self.flags |= METHOD_PARAMETER_UNSPECIFIED
            self.flags |= METHOD_LOADED
            return 
        
        # 引数
        for i, p in enumerate(sig.parameters.values()):
            flags = 0
            
            if i==0 and self_typename:
                typename = self_typename
            else:
                typename = "Any" # 型注釈から推定できるかもしれないが、不明とする

            if p.default == inspect.Parameter.empty:
                flags |= PARAMETER_REQUIRED
                default = None
            else:
                default = p.default

            if p.kind == inspect.Parameter.VAR_POSITIONAL:
                flags |= PARAMETER_VARIABLE
            elif p.kind == p.VAR_KEYWORD or p.kind == p.KEYWORD_ONLY:
                flags |= METHOD_PARAMETER_UNSPECIFIED | METHOD_KEYWORD_PARAMETER
                break

            self.add_parameter(p.name, typename, "", default, flags=flags)
        
        self._action = fn
        self.target = "function:{}".format(fn.__name__)
        self.flags |= METHOD_LOADED

    def load_from_string(self, doc, action):
        """ 
        構文文字列と実装オブジェクトを直接指定してロードする。
        Params:
            doc(str): 構文文字列。@指定が無ければ、@methodとみなす
            action(Any): 実装オブジェクト
        """
        if self.flags & METHOD_LOADED:
            return 
        
        doc = doc.strip()
        if not doc.startswith("@"):
            doc = "@method\n" + doc
        
        self.parse_syntax_from_docstring(doc)

        self._action = action
        self.target = "function:{}".format(str(action))
        self.flags |= METHOD_LOADED
    
    def get_signature(self, *, fully=False, self_typename=None):
        """ @method alias-name [signature]
        メソッドの構文を返す。
        Returns:
            Str: 構文
        """
        # パラメータ
        params = []
        for p in self.params:
            ps = ""
            if p.is_required():
                ps = p.name
            elif p.is_variable():
                ps = "*" + p.name
            elif not p.is_required():
                if fully:
                    ps = "?{}={}".format(p.name, repr(p.default))
                else:
                    ps = "?{}".format(p.name)

            params.append(ps)

        if self.flags & METHOD_PARAMETER_UNSPECIFIED:
            params.append("...")

        # 戻り値
        results = []
        if self.result:
            re = self.result.typename
            results.append(re)
        
        if self.flags & METHOD_RESULT_UNSPECIFIED:
            results.append("...")
        
        parts = []
        if self_typename and (self.flags & METHOD_HAS_RECIEVER_PARAM) == 0:
            parts.append(self_typename)
        if fully:
            parts.append(self.name)
        if params:
            parts.append(" ".join(params))
        parts.append("->")
        parts.append(", ".join(results))
        return " ".join(parts)
    
    def pprint(self, app):
        """ @meta """
        sig = self.get_signature(fully=True)
        app.post("message", sig)
        app.post("message", self.doc)

        app.post("message", "引数:")
        if not self.params:
            app.post("message", "    なし")
        else:
            for p in self.params:
                l = "    {} [{}]: {}".format(p.get_name(), p.get_typename(), p.get_doc())
                app.post("message", l)

        app.post("message", "返値:")
        r = self.result
        if r:
            l = "    {}: {}".format(r.get_typename(), r.get_doc())
            app.post("message", l)


#
# Typename[Typename2]: (param1, param2, ...) document
#
def parse_typename_syntax(name, doc):
    if "[" in name:
        name1, _, name2 = name.partition("[")
        typename = normalize_typename(name1)
        name2 = name2.rstrip("]")
        secondtypename = normalize_typename(name2) if name2 else ""
    else:
        typename = normalize_typename(name)
        secondtypename = ""
    
    typeparams: List[str] = []
    if secondtypename:
        typeparams.append(secondtypename)
    
    if doc and doc[0] == "(":
        typeparamend = doc.find(")")
        if typeparamend != -1:
            typeparams.extend(x.strip() for x in doc[1:typeparamend].split(","))
            doc = doc[typeparamend+1:].lstrip()
    
    return typename, doc, typeparams

#
#
#
class MethodParameter():
    def __init__(self, name, typename, doc, default=None, flags=0, typeparams=None):
        self.name = name
        self.typename = typename
        self.doc = doc
        self.default = default
        self.flags = flags
        self.typeparams = typeparams
    
    def __str__(self):
        name = self.name
        if self.is_variable():
            name = "*" + name
        line = "Param '{}' [{}]".format(name, self.typename)
        if self.default:
            line = line + "= {}".format(self.default)
        return line

    def get_name(self):
        return self.name

    def get_typename(self):
        return self.typename
    
    def get_doc(self):
        return self.doc
    
    def is_any(self):
        return self.typename == "Any"
        
    def is_string(self):
        return self.typename == "Str"
    
    def is_object(self):
        return self.typename == "Object"

    def is_type(self):
        return self.typename == "Type"

    def is_required(self):
        return (self.flags & PARAMETER_REQUIRED) > 0

    def is_variable(self):
        return (self.flags & PARAMETER_VARIABLE) > 0
    
    def get_default(self):
        return self.default
    
    def get_typeparams(self):
        return self.typeparams or []

#
#
#
class MethodResult:
    def __init__(self, typename=None, doc="", typeparams=None):
        self.typename = typename
        self.doc = doc
        self.typeparams = typeparams

    def __str__(self):
        line = "Return [{}]".format(self.typename)
        return line
    
    def get_typename(self):
        return self.typename or "Any" 
    
    def get_typeparams(self):
        return self.typeparams or []

    def get_doc(self):
        return self.doc
    
    def is_any(self):
        return self.typename is None
    
    def is_return_self(self):
        return self.typeparams and self.typeparams[0] is RETURN_SELF

#
#
#
class MetaMethod():
    def __init__(self, target, flags=0):
        self.target = target
        self.flags = flags
    
    def get_action_target(self):
        return self.target
    
    def new(self, declprops):
        """ 特殊メソッドを構築 """
        flags = self.flags
        if "extra-args" in declprops:
            flags |= METHOD_META_EXTRAARGS
        if "context" in declprops:
            flags |= METHOD_CONTEXT_BOUND
        if "spirit" in declprops:
            flags |= METHOD_SPIRIT_BOUND
        return MetaMethod(self.target, flags)
    
    def has_extra_args(self):
        return (self.flags & METHOD_META_EXTRAARGS) > 0
    
    def is_type_bound(self):
        return (self.flags & METHOD_TYPE_BOUND) > 0
    
    def is_context_bound(self):
        return (self.flags & METHOD_CONTEXT_BOUND) > 0

    def is_spirit_bound(self):
        return (self.flags & METHOD_SPIRIT_BOUND) > 0


def make_method_prototype(attr, attrname) -> Tuple[Optional[Method], List[str]]:
    """ ドキュメントを解析して空のメソッドオブジェクトを構築 """ 
    decl = parse_doc_declaration(attr, ("method", "task"))
    if decl is None:
        return None, []

    mname = decl.name or attrname
    method = Method(name=normalize_method_name(mname), target=attrname)
    method.load_declaration_properties(decl.props)
    return method, decl.aliases

meta_method_prototypes = (
    MetaMethod("constructor", METHOD_TYPE_BOUND),
    MetaMethod("stringify"),
    MetaMethod("summarize"),
    MetaMethod("pprint"),
)


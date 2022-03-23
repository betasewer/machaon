from machaon.core.importer import ClassDescriber
from machaon.core.typedecl import METHODS_BOUND_TYPE_TRAIT_INSTANCE
from typing import (
    Any, Sequence, List, Dict, Union, Callable, 
    Optional, Tuple, Generator
)

import types
import inspect

from machaon.core.symbol import normalize_method_target, normalize_method_name
from machaon.core.docstring import parse_doc_declaration
from machaon.core.typedecl import TypeDecl, parse_type_declaration, TypeConversionError, make_conversion_from_value_type

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
METHOD_EXTERNAL_TARGET = 0x0040
METHOD_BOUND_TRAILING = 0x0080
METHOD_LOADED = 0x0100
METHOD_DECL_LOADED = 0x0200
METHOD_HAS_RECIEVER_PARAM = 0x0400 # レシーバオブジェクトもパラメータとして扱う

METHOD_PARAMETER_UNSPECIFIED = 0x1000
METHOD_RESULT_UNSPECIFIED = 0x2000
METHOD_UNSPECIFIED_MASK = 0x3000
METHOD_KEYWORD_PARAMETER = 0x4000

METHOD_INVOKEAS_FUNCTION = 0x10000
METHOD_INVOKEAS_BOUND_METHOD = 0x20000
METHOD_INVOKEAS_PROPERTY = 0x40000
METHOD_INVOKEAS_MASK = 0xF0000

METHOD_FROM_CLASS_MEMBER    = 0x100000  # クラスメンバから得た定義
METHOD_FROM_INSTANCE_MEMBER = 0x200000  # インスタンスメンバから得た定義
METHOD_FROM_USER_DEFINITION = 0x400000  # コメントや辞書による定義 
METHOD_DEFINITION_FROM_MASK = 0xF00000  

METHOD_META_NOEXTRAPARAMS = 0x1000000

#
PARAMETER_REQUIRED = 0x0100
PARAMETER_VARIABLE = 0x0200
PARAMETER_KEYWORD  = 0x0400

#
class RETURN_SELF:
    pass

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
    
    def child_exception(self):
        return self.args[0]

# メタメソッド呼び出し時のエラー
class BadMetaMethod(Exception):
    def __init__(self, error, type, method):
        super().__init__(error, type, method)
    
    def __str__(self):
        errtype = type(self.args[0]).__name__
        typename = self.args[1].get_typename()
        methname = self.args[2].get_action_target()
        return " {}.{}で{}が発生：{}".format(typename, methname, errtype, self.args[0])
    
    def child_exception(self):
        return self.args[0]

#
class MethodParameterNoDefault:
    pass

#
#
#
class Method():
    """ @type
    メソッド定義。
    """
    def __init__(self, name = None, target = None, doc = "", flags = 0, mixin = None):
        self.name: str = name
        self.doc: str = doc

        self.target: str = target
        self.mixin: int = mixin
        self.flags = flags

        self._action = None
        self.params = []    # List[MethodParameter]
        self.result = None  # Optional[MethodResult]

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
    
    def is_trailing_bound(self):
        """ @method
        メソッドに追加で束縛されるオブジェクトが、引数リストの後ろに付加される
        Returns:
            Bool:
        """
        return (self.flags & METHOD_BOUND_TRAILING) > 0
    
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

    def is_user_defined(self):
        """ @method
        ユーザー定義によるメソッド
        Returns:
            Bool: 
        """
        return (self.flags & METHOD_FROM_USER_DEFINITION) > 0

    def is_from_class_member(self):
        """ @method
        クラスメンバから定義されたメソッド
        Returns:
            Bool: 
        """
        return (self.flags & METHOD_FROM_CLASS_MEMBER) > 0

    def is_from_instance_member(self):
        """ @method
        インスタンスメンバから定義されたメソッド
        Returns:
            Bool: 
        """
        return (self.flags & METHOD_FROM_INSTANCE_MEMBER) > 0

    def get_describer(self, this_type):
        """ @method
        定義クラスを得る。
        Params:
            this_type(Type):
        Returns:
            Any: クラス型か辞書型
        """
        d = this_type.get_describer(self.mixin)
        if isinstance(d, ClassDescriber):
            return d.klass
        else:
            return d

    def get_describer_qualname(self, this_type):
        """ @method
        定義クラスを得る。
        Params:
            this_type(Type):
        Returns:
            Str:
        """
        return this_type.get_describer_qualname(self.mixin)
    
    def make_type_instance(self, this_type):
        """ 型を拘束する場合の実行時のインスタンスを得る """
        descclass = self.get_describer(this_type)
        if isinstance(descclass, dict):
            raise TypeError("dict describer cannot be type method instance")
        return descclass()
    
    # 仮引数を追加
    def add_parameter(self,
        name,
        typedecl,
        doc = "",
        default = MethodParameterNoDefault,
        variable = False,
        *,
        flags = 0,
    ):
        """
        仮引数を追加する。
        Params:
            name(str): 引数名
            typedecl(str|None): 型宣言
            doc(str): *説明文
            default(Any): *デフォルト値
            variable(bool): *可変長引数であるか
            flags(int): *フラグ
        """
        f = 0
        if flags:
            f |= flags
        if variable:
            f |= PARAMETER_VARIABLE
        if default is MethodParameterNoDefault:
            default = None
            f |= PARAMETER_REQUIRED
        if isinstance(typedecl, str):
            typedecl = parse_type_declaration(typedecl)
        p = MethodParameter(name, typedecl, doc, default, f)
        self.params.append(p)
    
    def get_params(self):
        """ @method alias-name [params]
        仮引数のリスト
        Returns:
            Sheet[MethodParameter](name, typename, doc):
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
        typedecl, 
        doc = ""
    ):
        """
        返り値宣言を追加
        Params:
            typedecl(str): 型宣言
            doc(str): *説明文
        """
        decl = parse_type_declaration(typedecl)
        r = MethodResult(decl, doc)
        self.result = r
    
    def add_result_self(self, type):
        """ メソッドのselfオブジェクトを返す """
        decl = TypeDecl(type)
        r = MethodResult(decl, "selfオブジェクト", RETURN_SELF)
        self.result = r

    def get_result(self):
        """ @method alias-name [result]
        返り値
        Returns:
            MethodResult:
        """
        if self.flags & METHOD_RESULT_UNSPECIFIED:
            raise UnloadedMethod(self.name)
        if self.result is None:
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
            if not p.is_required() or p.is_variable():
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
            if self.flags & METHOD_EXTERNAL_TARGET:
                # 外部モジュールから定義をロードする
                loader = attribute_loader(self.target)
                callobj = loader() # モジュールやメンバが見つからなければ例外が投げられる
                source = self.target
            else:
                # クラスに定義されたメソッドが実装となる
                typefn = this_type.delegate_method(self.target, self.mixin)
                if typefn is not None:
                    callobj = typefn
                    source = "{}:{}".format(this_type.get_scoped_typename(), self.name)
                    if this_type.get_methods_bound_type() == METHODS_BOUND_TYPE_TRAIT_INSTANCE:
                        self.flags |= METHOD_TYPE_BOUND # 第1引数は型オブジェクト、第2引数はインスタンスを渡す
                    elif self.is_mixin():
                        self.flags |= METHOD_TYPE_BOUND

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
    
    def is_mixin(self):
        return self.mixin is not None

    def parse_syntax_from_docstring(self, doc: str, function: Callable = None):
        """ 
        docstringの解析で引数を追加する。
        Params:
            doc(str): docstring
            function(Callable): *関数の実体。引数デフォルト値を得るのに使用する
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
        for line in sections.get_lines("Params"):
            typename, name, doc, flags = parse_parameter_line(line.strip())
            
            if typename.endswith("..."):
                self.flags |= METHOD_CONSUME_TRAILING_PARAMS
                typename = typename.rstrip(".")
            
            default = None
            if funcsig:
                p = funcsig.parameters.get(name)
                if p is None:
                    raise BadMethodDeclaration("存在しない引数です：" + name)
    
                default, pf = pick_parameter_default_value(p)
                if pf & PARAMETER_KEYWORD:
                    # キーワード引数には未対応
                    self.flags |= METHOD_PARAMETER_UNSPECIFIED | METHOD_KEYWORD_PARAMETER
                    break 
                if flags & PARAMETER_REQUIRED == 0 and pf & PARAMETER_REQUIRED:
                    # オプション引数の設定が食い違う場合、オプション引数として扱う
                    pf &= ~PARAMETER_REQUIRED
                flags |= pf
            else:
                flags |= PARAMETER_REQUIRED
        
            self.add_parameter(name, typename, doc, default, flags=flags)

        # 戻り値
        for line in sections.get_lines("Returns"):
            typename, doc, flags = parse_result_line(line.strip())
            self.add_result(typename, doc)
        
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
        if "trailing" in props:
            self.flags |= METHOD_BOUND_TRAILING
        
        self.flags |= METHOD_DECL_LOADED
            
    def load_from_function(self, fn, *, result_typename=None, action=None, self_to_be_bound=False):
        """
        関数オブジェクトから引数を解析しアクションとしてロードする。
        Params:
            fn(Any): 関数オブジェクト
            result_typename(str): 返り値の型指定
            action(Any): 別のアクションインスタンスを使用する場合
            self_to_be_bound(bool): selfの分の引数を1つ取り除く
        """
        if self.flags & METHOD_LOADED:
            return 
        
        self.doc = fn.__doc__ or ""
        
        # 戻り値
        self.add_result(result_typename or "Any") # 不明、値から推定する

        # シグネチャを関数から取得
        try:
            sig = inspect.signature(fn)
        except ValueError:
            # ビルトイン関数なので情報を取れなかった
            self.flags |= METHOD_PARAMETER_UNSPECIFIED
            self.flags |= METHOD_LOADED
            return 
        
        # 引数
        for i, p in enumerate(sig.parameters.values()):
            if i==0 and self_to_be_bound:
                continue # 第一引数を飛ばす
            
            typename = "Any" # 型注釈から推定できるかもしれないが、不明とする
            default, f = pick_parameter_default_value(p)        

            if f & PARAMETER_KEYWORD:
                self.flags |= METHOD_PARAMETER_UNSPECIFIED | METHOD_KEYWORD_PARAMETER
                break # キーワード引数には未対応

            self.add_parameter(p.name, typename, "", default, flags=f)
        
        target = getattr(fn, "__name__", None)
        if target is None:
            target = repr("<function name cannot be retrieved>")

        self._action = action or fn
        self.target = target
        self.flags |= METHOD_LOADED

    def load_from_dict(self, dictionary):
        """ 
        辞書からメソッド定義をロードする。
        Params:
            dictionary(Dict[str, Any]): 定義辞書
        """
        if self.flags & METHOD_LOADED:
            return 
        
        action = None
        doc = ""
        decls = []
        for key, value in dictionary.items():
            if key == "Document" or key == "Doc":
                doc = value.strip()

            elif key == "Params" or key == "Args":
                for i, pdef in enumerate(value, start=1):
                    name = "param{}".format(i)
                    typename = "Any"
                    default = None
                    doc = ""
                    for k, v in pdef.items():
                        if key == "Name":
                            name = v
                        elif key == "Document" or key == "Doc":
                            doc = v
                        elif k == "Typename":
                            typename = v
                        elif k == "Default":
                            default = v
                    # TODO: 可変長引数など
                    self.add_parameter(name, typename, doc, default)

            elif key == "Results" or key == "Returns":
                typename = None
                doc = ""
                for k, v in value.items():
                    if key == "Document" or key == "Doc":
                        doc = v
                    elif k == "Typename":
                        typename = v
                self.add_result(typename, doc)

            elif key == "Action":
                action = value

            elif key == "Decl" or key == "Declaration":
                decls = value.split()

            else:
                raise BadMethodDeclaration("無効な要素が定義辞書にあります: {}".format(key))

        if action is None:
            raise BadMethodDeclaration()

        self.doc = doc
        self.load_declaration_properties(decls)
        self._action = action
        self.target = "<loaded from dict>"
        self.flags |= METHOD_LOADED

    def make_invocation(self, mods=0, type=None):
        """ 適した呼び出しオブジェクトを作成する """
        if self.flags & METHOD_INVOKEAS_BOUND_METHOD or self.flags & METHOD_INVOKEAS_PROPERTY:
            if not isinstance(self._action, InstanceBoundAction):
                raise ValueError("InstanceBoundAction must be specified when METHOD_INVOKEAS_BOUND_METHOD is set")
            ami = self.get_required_argument_min()
            amx = self.get_acceptable_argument_max()
            from machaon.core.invocation import InstanceMethodInvocation
            return InstanceMethodInvocation(self._action.target, mods, ami, amx)

        elif self.flags & METHOD_INVOKEAS_FUNCTION:
            ami = self.get_required_argument_min()
            amx = self.get_acceptable_argument_max()
            from machaon.core.invocation import FunctionInvocation
            return FunctionInvocation(self._action, mods, ami, amx)

        else:
            if type is None:
                raise ValueError("type argument must be specified")
            from machaon.core.invocation import TypeMethodInvocation
            return TypeMethodInvocation(type, self, mods)

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
            else:
                if fully:
                    ps = "{}={}".format(p.name, repr(p.default))
                else:
                    ps = "{}?".format(p.name)
            if p.is_variable():
                ps = "*" + p.name
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
#
#
class MethodParameter():
    def __init__(self, name, typedecl, doc, default=None, flags=0):
        self.name = name
        self.doc = doc
        self.default = default
        self.flags = flags
        self.typedecl = typedecl or TypeDecl()
    
    def __str__(self):
        name = self.name
        if self.is_variable():
            name = "*" + name
        line = "param '{}' [{}]".format(name, self.typename)
        if self.default:
            line = line + " = {}".format(self.default)
        return "<{}>".format(line)
    
    @property
    def typename(self):
        if self.typedecl:
            return self.typedecl.to_string()
        return None

    def get_name(self):
        return self.name

    def get_typename(self):
        return self.typename
    
    def get_doc(self):
        return self.doc
    
    def is_type_unspecified(self):
        return self.typename is None or self.typename == "Any" or self.typename == "Object"
        
    def is_type_uninstantiable(self):
        return self.typename is None or self.typename == "Object"

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
    
    def get_typedecl(self):
        return self.typedecl

#
#
#
class MethodResult:
    def __init__(self, typedecl=None, doc="", special=None):
        self.typedecl = typedecl or TypeDecl()
        self.doc = doc
        self.special = special

    def __str__(self):
        line = "Return [{}]".format(self.typename)
        return line
    
    @property
    def typename(self):
        return self.typedecl.to_string()

    def get_typename(self):
        return self.typename
    
    def get_doc(self):
        return self.doc
    
    def is_type_to_be_deduced(self):
        return self.typename == "Any"
    
    def is_return_self(self):
        return self.special is RETURN_SELF

    def get_typedecl(self):
        return self.typedecl


def parse_parameter_line(line):
    """
    Params:
        line(str):
    Returns:
        Tuple[str, str, int]: 型名、変数名、フラグ
    """
    head, _sep, doc = [x.strip() for x in line.partition(":")]
    # sepが無くても続行する    

    flags = 0
    if head.startswith("*"):
        # 可変長引数
        name, _, right = head[1:].partition("(")
        if right:
            typename, _, _ = right.rpartition(")")
            typename = typename.strip()
        else:
            typename = "Any"
        flags |= PARAMETER_VARIABLE
    else:
        name, _, paren = head.partition("(")
        name = name.strip()
        if name.endswith("?"):
            name = name[:-1]
        else:
            flags |= PARAMETER_REQUIRED
        typename, _, _ = paren.rpartition(")")
        typename = typename.strip()
    
    if not name or not typename:
        raise BadMethodDeclaration("引数'{}'の型指定が間違っています。「引数名(型名): 説明文」と指定してください".format(name))

    return typename, name, doc, flags

    
def pick_parameter_default_value(p):
    """
    Params:
        p(inspect.Parameter):
    Returns:
        Tuple[Any, int]:
    """
    flags = 0
    default = p.default
    if default is inspect.Signature.empty:
        default = None
        flags |= PARAMETER_REQUIRED
    
    if p.kind == p.VAR_KEYWORD or p.kind == p.KEYWORD_ONLY:
        flags |= PARAMETER_KEYWORD
        
    return default, flags


def parse_result_line(line):
    """
    Params:
        line(str):
    Returns:
        Tuple[str, str, int]:
    """
    typename, sep, doc = [x.strip() for x in line.partition(":")]
    if not sep:
        return typename, "", 0
    return typename, doc, 0


#
#
#
class MetaMethod():
    def __init__(self, target, flags=0):
        self.target = target
        self.flags = flags
        self._ctorparam = None
    
    def get_action_target(self):
        return self.target
    
    def new(self, decl):
        """ 特殊メソッドを構築 
        Params:
            decl(DocStringDeclaration)
        """
        flags = self.flags
        if "context" in decl.props:
            flags |= METHOD_CONTEXT_BOUND
        if "spirit" in decl.props:
            flags |= METHOD_SPIRIT_BOUND
        if "noarg" in decl.props or "noparam" in decl.props:
            flags |= METHOD_META_NOEXTRAPARAMS
        
        meth = MetaMethod(self.target, flags)
        meth.load_from_docstring(decl)
        return meth

    def is_type_bound(self):
        return (self.flags & METHOD_TYPE_BOUND) > 0
    
    def is_context_bound(self):
        return (self.flags & METHOD_CONTEXT_BOUND) > 0

    def is_spirit_bound(self):
        return (self.flags & METHOD_SPIRIT_BOUND) > 0
    
    def has_no_extra_params(self):
        return (self.flags & METHOD_META_NOEXTRAPARAMS) > 0
    
    def load_from_docstring(self, decl):
        """
        Params: ですべて指定
        第1引数は変数名を省略可能（value）
        追加引数においては、型がTypeなら型引数、そうでないなら追加コンストラクタ引数とみなす
        """
        sections = decl.create_parser((
            "Params Parameters",
        ))

        # 説明文
        desc = sections.get_string("Document")
        if desc:
            self.doc = desc.strip()

        # コンストラクタ引数
        params = sections.get_lines("Params")
        if params:
            if self.target != "constructor":
                raise ValueError("メタメソッド'{}'で引数を定義することはできません".format(self.target))

            firstline = params[0]
            findend = (lambda x: None if x == -1 else x)(firstline.find(":"))
            if -1 == firstline.find("(", 0, findend):
                name = "value"
                typename, doc, flags = parse_result_line(firstline.strip())
            else:
                typename, name, doc, flags = parse_parameter_line(firstline.strip())

            typedecl = parse_type_declaration(typename)
            p = MethodParameter(name, typedecl, doc, flags=flags)
            self._ctorparam = p

    def prepare_invoke_args(self, context, typeparams, value, typeinst, *moreargs):
        """ メソッド実行時に渡す引数を準備する """        
        # コンストラクタ引数の型をチェックする
        if self._ctorparam and context is not None:
            t0 = self._ctorparam.get_typedecl().instance(context)
            if not t0.check_value_type(type(value)):
                raise TypeConversionError(type(value), t0)
        
        args = []
        if context is not None and self.is_context_bound(): 
            args.append(context)
        
        args.append(value)

        args.extend(moreargs)

        if self.has_no_extra_params():
            return args

        # 引数を集める
        if typeinst:
            thead = 0
            nthead = 0
            for tp in typeparams:
                if tp.is_type():
                    # 型引数
                    if thead < len(typeinst.type_args):
                        ta = typeinst.type_args[thead]
                    else:
                        ta = None
                    thead += 1
                    args.append(ta)
                else:
                    # 非型引数
                    if tp.is_variable():
                        ntas = typeinst.constructor_args[nthead:]
                        args.extend(ntas)
                        nthead = -1
                    else:
                        if nthead < len(typeinst.constructor_args):
                            nta = typeinst.constructor_args[nthead]
                        else:
                            if tp.is_required():
                                break
                            else:
                                nta = None
                        nthead += 1
                        args.append(nta)
        else:
            # デフォルト型引数をセット
            for tp in typeparams:
                if not tp.is_type():
                    break
                args.append(None)
        
        return args


meta_method_prototypes = (
    MetaMethod("constructor", METHOD_TYPE_BOUND),
    MetaMethod("stringify"),
    MetaMethod("summarize"),
    MetaMethod("pprint"),
    MetaMethod("reflux"),
)


def make_method_prototype(attr, attrname, mixinkey=None) -> Tuple[Optional[Method], List[str]]:
    """ 
    ドキュメントを解析して空のメソッドオブジェクトを構築 
    Params:
        attr(Any): ドキュメントの付された関数オブジェクト
        attrname(str): 属性名
        *mixinkey(str): mixinクラスへの参照名
    """ 
    decl = parse_doc_declaration(attr, ("method", "task"))
    if decl is None:
        return None, []

    mname = decl.name or attrname
    method = Method(name=normalize_method_name(mname), target=attrname, mixin=mixinkey, flags=METHOD_FROM_USER_DEFINITION)
    method.load_declaration_properties(decl.props)
    return method, decl.aliases

def make_method_from_dict(di):
    """
    辞書による定義からメソッドを作成する
    
    """
    name = di.pop("Name", None)
    if name is None:
        raise BadMethodDeclaration("Name でメソッド名を指定してください")
    mth = Method(name, flags=METHOD_FROM_USER_DEFINITION)
    mth.load_from_dict(di)
    return mth


#
#
# インスタンスメソッド
#
#
class InstanceBoundAction():
    def __init__(self, target):
        self.target = target

    def __call__(self, *args):
        raise ValueError("未解決のアクションのため呼び出せません")
        
#
def classdict_invokeas(value):
    """ ディスクリプタが適用される前の値から判定する """
    if isinstance(value, classmethod):
        return METHOD_INVOKEAS_FUNCTION
    elif isinstance(value, staticmethod):
        return METHOD_INVOKEAS_FUNCTION
    elif isinstance(value, property):
        return METHOD_INVOKEAS_PROPERTY
    elif isinstance(value, (types.FunctionType, types.MethodType)):
        return METHOD_INVOKEAS_BOUND_METHOD
    elif callable(value):
        if getattr(value, "__objclass__", None) is not None:
            return METHOD_INVOKEAS_BOUND_METHOD
        else:
            return METHOD_INVOKEAS_FUNCTION
    else:
        return METHOD_INVOKEAS_PROPERTY

def classdir_invokeas(value):
    """ value_typeのdirの結果から推定する """
    if isinstance(value, types.FunctionType):
        # メソッドあるいはstaticmethodだが、
        # 二つを区別する方法がわからないので、メソッドに決め打ちする。
        return METHOD_INVOKEAS_BOUND_METHOD
    elif isinstance(value, types.MethodType):
        # classmethod
        return METHOD_INVOKEAS_FUNCTION
    else:
        # その他すべて
        return METHOD_INVOKEAS_PROPERTY

def instance_invokeas(value, this):
    """ インスタンスの値から判定する """
    if isinstance(value, (types.FunctionType, types.BuiltinFunctionType)):
        # staticmethod
        return METHOD_INVOKEAS_FUNCTION
    elif isinstance(value, (types.MethodType, types.BuiltinMethodType)):
        if getattr(value, "__self__", None) is this:
            # メソッド
            return METHOD_INVOKEAS_BOUND_METHOD
        else:
            # classmethod
            return METHOD_INVOKEAS_FUNCTION
    else:
        # その他すべて
        return METHOD_INVOKEAS_PROPERTY


class _InvokeasTypeDict():
    """
    メソッドや属性の呼び出し方法を推定する
    """
    def __init__(self, value_type):
        self._classdict = None
        self._dirdict = None

        classdict = getattr(value_type, "__dict__", None)
        if classdict is not None:
            self._dict = classdict
            self._lookup = classdict_invokeas
        else:
            self._dict = dir(value_type)
            self._lookup = classdir_invokeas

    def get(self, name):
        """ 値の型から呼び出し方法を判別する """
        if name not in self._dict:
            return None
        return self._lookup(self._dict[name])


def make_method_from_value(value, name, invokeas, source):
    """ 値からメソッドオブジェクトを作成する """
    m = Method(name, flags=invokeas|source)
    if invokeas == METHOD_INVOKEAS_FUNCTION:
        m.load_from_function(value)
    elif invokeas == METHOD_INVOKEAS_BOUND_METHOD:
        if getattr(value, "__self__", None) is not None:
            m.load_from_function(value, action=InstanceBoundAction(name))
        else:
            m.load_from_function(value, action=InstanceBoundAction(name), self_to_be_bound=True)
    elif invokeas == METHOD_INVOKEAS_PROPERTY:
        if inspect.ismethoddescriptor(value) or inspect.isdatadescriptor(value):
            tn = "Any"
        else:
            tn = make_conversion_from_value_type(type(value))
        m.load_from_dict({
            "Params" : [],
            "Returns": { "Typename": tn },
            "Action" : InstanceBoundAction(name)
        })
    return m


def select_method_from_type_and_instance(value_type, value, name):
    """
    インスタンスでセレクタとして利用可能なメソッドを指定して得る
    Returns:
        Optional[Method]:
    """   
    invasdict = _InvokeasTypeDict(value_type)
    invtype = invasdict.get(name)
    if invtype is None:
        return None

    if not hasattr(value, name):
        return None
    attr = getattr(value, name)
    
    if value_type is value:
        sourcebit = METHOD_FROM_CLASS_MEMBER
    else:
        sourcebit = METHOD_FROM_INSTANCE_MEMBER
    
    return make_method_from_value(attr, name, invtype, sourcebit)  

def is_method_selectable_from_type_and_instance(value_type, value, name):
    """ 呼び出せるかどうかだけチェックする """
    invasdict = _InvokeasTypeDict(value_type)
    invtype = invasdict.get(name)
    if invtype is None:
        return False

    if not hasattr(value, name):
        return False
    return True

def enum_methods_from_type_and_instance(value_type, value):
    """
    インスタンスでセレクタとして利用可能なすべてのメソッドを列挙する
    Yields:
        Tuple[str, Method | Exception]:
    """
    invasdict = _InvokeasTypeDict(value_type)

    from machaon.core.importer import enum_attributes
    for name, attr in enum_attributes(value_type, value):
        if isinstance(attr, Exception):
            yield name, attr
        
        invtype = invasdict.get(name)
        if invtype is None:
            if callable(attr):
                invtype = METHOD_INVOKEAS_BOUND_METHOD
            else:
                invtype = METHOD_INVOKEAS_PROPERTY
                
        if value_type is value:
            sourcebit = METHOD_FROM_CLASS_MEMBER
        else:
            sourcebit = METHOD_FROM_INSTANCE_MEMBER
        
        try:
            m = make_method_from_value(attr, name, invtype, sourcebit)   
        except Exception as e:
            m = e
        yield name, m


from typing import (
    Any, Sequence, List, Dict, Union, Callable, 
    Optional, Tuple, Generator
)

from machaon.core.type.basic import METHODS_BOUND_TYPE_TRAIT_INSTANCE, TypeProxy
from machaon.core.type.decl import TypeInstanceDecl

import types
import inspect

from machaon.core.object import Object
from machaon.core.symbol import normalize_method_target, normalize_method_name, SIGIL_OPERATOR_MEMBER_AT, normalize_typename
from machaon.core.docstring import parse_doc_declaration, DocStringDefinition, DocStringDeclaration
from machaon.core.type.decl import (
    TypeDecl, parse_type_declaration, split_typename_and_value
)
from machaon.core.type.declresolver import BasicTypenameResolver
from machaon.core.type.basic import TypeConversionError, TypeProxy
from machaon.core.type.extend import get_type_extension_loader

# imported from...
# type
# operator
#
#

#
METHOD_CONTEXT_BOUND            = 0x0001
METHOD_SPIRIT_BOUND             = 0x0002
METHOD_TASK                     = 0x0004 | METHOD_SPIRIT_BOUND
METHOD_TYPE_BOUND               = 0x0008 # デスクライバのクラスがselfとして渡される
METHOD_TYPEVAL_BOUND            = 0x0010 # デスクライバのインスタンスがselfとして渡される
METHOD_EXTERNAL                 = 0x0020 # レシーバオブジェクトもパラメータとして扱う
METHOD_BOUND_TRAILING           = 0x0040 # ?
METHOD_LOADED                   = 0x0100
METHOD_DECL_LOADED              = 0x0200
METHOD_LOADBIT_MASK             = 0x0F00 

METHOD_PARAMETER_UNSPECIFIED        = 0x1000
METHOD_RESULT_UNSPECIFIED           = 0x2000
METHOD_UNSPECIFIED_MASK             = 0x3000
METHOD_KEYWORD_PARAMETER            = 0x4000
METHOD_CONSUME_TRAILING_PARAMETERS  = 0x8000 # ?

METHOD_INVOKEAS_FUNCTION            = 0x10000  # レシーバを受け取らない関数
METHOD_INVOKEAS_BOUND_METHOD        = 0x20000  # インスタンスメソッド、レシーバを受け取る
METHOD_INVOKEAS_PROPERTY            = 0x30000  # インスタンスのプロパティ、レシーバのみを受け取る
METHOD_INVOKEAS_BOUND_FUNCTION      = 0x40000  # レシーバを第1引数に受け取る関数
METHOD_INVOKEAS_IMMEDIATE_VALUE     = 0x50000  # 値、レシーバを受け取らない
METHOD_INVOKEAS_MASK                = 0xF0000

METHOD_FROM_CLASS_MEMBER            = 0x100000  # クラスメンバから得た定義
METHOD_FROM_INSTANCE_MEMBER         = 0x200000  # インスタンスメンバから得た定義
METHOD_FROM_USER_DEFINITION         = 0x400000  # コメントや辞書による定義 
METHOD_DEFINITION_FROM_MASK         = 0xF00000  


#
PARAMETER_REQUIRED = 0x0100
PARAMETER_VARIABLE = 0x0200
PARAMETER_KEYWORD  = 0x0400
PARAMETER_VARIABLE_ONEORMORE = 0x0800

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

class MethodCallingError(Exception):
    pass

# メタメソッド呼び出し時のエラー
class BadMetaMethod(Exception):
    def __init__(self, error, type, method):
        super().__init__(error, type, method)
    
    def __str__(self):
        errtype = type(self.args[0]).__name__
        typename = self.args[1].get_typename()
        methname = self.args[2].get_action_target()
        return " {}の{}で{}が発生：{}".format(typename, methname, errtype, self.args[0])

#
class MethodParameterNoDefault:
    pass

class MethodParameterDefault:
    pass

#
#
#
class Method:
    """ @type
    メソッド定義。
    """
    def __init__(self, name = None, target = None, doc = "", flags = 0, mixin = None, *, params = None, result = None):
        self.name: str = name
        self.doc: str = doc

        self.target: str = target
        self.mixin: int = mixin
        self.flags = flags

        self._action = None
        self.params: List[MethodParameter] = params or []    # List[MethodParameter]
        self.result: Optional[MethodResult] = result          # Optional[MethodResult]

    def check_valid(self):
        if self.name is None:
            raise ValueError("name")
    
    def get_name(self):
        """ @method alias-name [name]
        メソッド名。
        Returns:
            Str:
        """
        #if self.flags & METHOD_LOADED == 0:
        #    raise UnloadedMethod(self.name)
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

    def is_type_class_bound(self):
        """ @method
        メソッドにデスクライバクラスが渡されるか
        Returns:
            Bool:
        """
        return (self.flags & METHOD_TYPE_BOUND) > 0

    def is_type_value_bound(self):
        """ @method
        メソッドにデスクライバインスタンスが渡されるか
        Returns:
            Bool:
        """
        return (self.flags & METHOD_TYPEVAL_BOUND) > 0

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
        return (self.flags & METHOD_CONSUME_TRAILING_PARAMETERS) > 0
    
    def is_external(self):
        """ @method
        外部メソッドか
        Returns:
            Bool:
        """
        return (self.flags & METHOD_EXTERNAL) > 0
    
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
        return d.get_value()

    def get_describer_qualname(self, this_type):
        """ @method
        定義クラスを得る。
        Params:
            this_type(Type):
        Returns:
            Str:
        """
        return this_type.get_describer(self.mixin).get_full_qualname()
    
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
            Sheet[MethodParameter]:
        Decorates:
            @ view: name typename doc
        """
        if self.flags & METHOD_PARAMETER_UNSPECIFIED:
            raise UnloadedMethod(self.name)
        return self.params
    
    def get_param(self, index):
        """ 引数の定義を得る。 """
        if self.is_external():
            if index == -1: # レシーバオブジェクトの型を返す
                return self.params[0]
            index = index + 1
        if 0 <= index:
            if len(self.params) <= index:
                if self.params and self.params[-1].is_variable():
                    return self.params[-1]
                else:
                    return None
            return self.params[index]
        return None

    def get_param_count(self):
        """ 可変長引数はカウントしない仮引数の数 """
        if self.flags & METHOD_PARAMETER_UNSPECIFIED:
            raise UnloadedMethod(self.name)
        return len(self.params)
    
    def check_param_count(self, count):
        """ 引数の数が仮引数の数を超えていないかチェックする """
        if self.flags & METHOD_PARAMETER_UNSPECIFIED:
            raise UnloadedMethod(self.name)
        if count <= len(self.params):
            return True
        elif self.params and self.params[-1].is_variable():
            return True
        return False

    def make_argument_row(self, context, args, *, construct=False, construct_offset=None):
        """ 
        実引数の列を生成する。
        reciever-paramは含まれない
        Returns:
            List[Object]:
        """
        argpairs: List[Tuple[MethodParameter, Any]] = []
        ihead = 0
        for i, tp in enumerate(self.params):
            if tp.is_variable():
                argpairs.extend((tp, x) for x in args[ihead:])
                ihead = 0xFFFF
                break
            else:
                if ihead < len(args):
                    argpairs.append((tp, args[ihead]))
                else:
                    argpairs.append((tp, MethodParameterDefault))
                ihead += 1        
        
        if ihead < len(args) and not self.is_external_nullary():
            if self.params:
                pasig = "({})".format(", ".join(x.get_name() for x in self.params))
            else:
                pasig = "無し"
            raise TypeError("引数{}に対し、余計に多くの引数が与えられました: {}".format(pasig, args))

        argvalues = []
        for i, (tp, valueo) in enumerate(argpairs):
            if construct_offset is not None:
                constr = i < construct_offset
            else:
                constr = construct
            avalue = tp.make_argument_value(context, valueo, construct=constr)
            argvalues.append(avalue)
        
        return argvalues

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
        if not isinstance(typedecl, TypeDecl):
            typedecl = parse_type_declaration(typedecl)
        r = MethodResult(typedecl, doc)
        self.result = r
    
    def add_result_self(self, typedecl):
        """ メソッドのselfオブジェクトを返す """
        if not isinstance(typedecl, TypeDecl):
            typedecl = parse_type_declaration(typedecl)
        r = MethodResult(typedecl, "selfオブジェクト", RETURN_SELF)
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
    
    def set_result_decorator(self, expr):
        """ 返り値デコレータをセットする """
        if self.result is None:
            raise UnloadedMethod("返り値がロードされていません")
        self.result.set_decorator(expr)
    
    def get_acceptable_argument_max(self) -> Union[int, None]:
        """
        受け入れ可能な最大の引数の数を得る。
        Returns:
            int: 個数。Noneで無限を示す。引数なし外部メソッドであれば-1を返す
        """
        if self.flags & METHOD_LOADED == 0:
            raise UnloadedMethod(self.name)
        if self.flags & METHOD_PARAMETER_UNSPECIFIED:
            return None 
        cnt = 0
        for p in self.params:
            if p.is_variable():
                return None
            cnt += 1
        if self.is_external():
            cnt -= 1
        return cnt

    # 必要な最小の引数の数を得る
    def get_required_argument_min(self) -> int:
        """
        実行に必要な最小の引数の数を得る。
        Returns:
            int: 個数
        """
        if self.flags & METHOD_LOADED == 0:
            raise UnloadedMethod(self.name)
        if self.flags & METHOD_PARAMETER_UNSPECIFIED:
            return 0
        cnt = 0
        for p in self.params:
            if p.is_variable_oneormore():
                cnt += 1
                break
            if not p.is_required() or p.is_variable():
                break
            cnt += 1
        if self.is_external():
            cnt -= 1
        return cnt
    
    def is_nullary(self):
        """ 引数が無い """
        return len(self.params) == 0
    
    def load_from_type(self, this_type: TypeProxy, *, meta=False):
        """
        実装をロードする。
        """
        if self.flags & METHOD_LOADED:
            return

        if self.target is None:
            self.target = normalize_method_target(self.name)

        # クラスに定義されたメソッドが実装となる
        if meta:
            callobj = this_type.get_describer(self.mixin).get_metamethod_attribute(self.target)
        else:
            callobj = this_type.get_describer(self.mixin).get_method_attribute(self.target)
        if callobj is None:
            raise BadMethodDeclaration("'{}'は型'{}'の属性として存在しません".format(self.target, this_type.get_conversion()))
        
        target_method = "{}{}{}".format(this_type.get_conversion(), SIGIL_OPERATOR_MEMBER_AT, self.name)

        if this_type.get_methods_bound_type() == METHODS_BOUND_TYPE_TRAIT_INSTANCE or self.is_mixin():
            self.flags &= ~METHOD_TYPE_BOUND
            self.flags |= METHOD_TYPEVAL_BOUND

        # ドキュメント文字列を取り出す
        calldoc = getattr(callobj, "__doc__", None)

        # プロパティオブジェクトから関数を取り出す
        if isinstance(callobj, property):
            callobj = callobj.fget

        # アクションオブジェクトの初期化処理
        if hasattr(callobj, "describe_method"):
            # アクションに定義されたメソッド定義処理があれば実行
            callobj.describe_method(self)
        elif calldoc is not None:
            # callobjのdocstringsを解析する
            self.parse_syntax_from_docstring(calldoc, callobj, this_type)
        else:
            raise BadMethodDeclaration("メソッド定義がありません。メソッド 'describe_method' かドキュメント文字列で記述してください")
    
        if isinstance(callobj, type):
            callobj = callobj()

        if callobj is None or not callable(callobj):
            raise BadMethodDeclaration("アクションは呼び出し可能な値ではありません：{} = {}".format(self.target, callobj))

        action = callobj
        
        # 返り値が無い場合はレシーバ自身を返す
        if not self.result and this_type is not None:
            if self.is_external():
                self.add_result(TypeInstanceDecl(this_type))
            else:
                self.add_result_self(TypeInstanceDecl(this_type))
        
        if self.flags & METHOD_UNSPECIFIED_MASK:
            self._action = None
        else:
            self._action = action
        self.target = target_method
        self.flags |= METHOD_LOADED
    
    def is_loaded(self):
        """ ロードされているか。 """
        return self._action is not None
    
    def is_mixin(self):
        return self.mixin is not None and self.mixin > 0

    def parse_syntax_from_docstring(self, doc: str, function: Callable = None, this_type = None):
        """ 
        docstringの解析で引数を追加する。
        Params:
            doc(str): docstring
            function(Callable): *関数の実体。引数デフォルト値を得るのに使用する
        """
        if this_type is not None:
            tnresolver = this_type.get_describer(self.mixin).get_typename_resolver()
        else:
            tnresolver = BasicTypenameResolver()

        if isinstance(doc, DocStringDeclaration):
            # パース済みの宣言
            decl = doc
        else:
            # 1行目はメソッド宣言
            decl = parse_doc_declaration(doc, ("method", "task", "meta"))
            if decl is None:
                raise BadMethodDeclaration("宣言のタイプがメソッドではないか、ドキュメント文字列が取得できません")
        
        if self.flags & METHOD_DECL_LOADED == 0:         
            self.load_declaration_properties(decl.props)
        
        # 定義部
        sections = DocStringDefinition.parse(decl, (
            "Params Parameters Arguments Args",
            "Returns", 
            "Decorates Deco",
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
        for i, line in enumerate(sections.get_lines("Params")):
            typename, name, doc, flags = parse_parameter_line(line.strip(), i)
            
            if typename.endswith("..."):
                self.flags |= METHOD_CONSUME_TRAILING_PARAMETERS
                typename = typename.rstrip(".")
            
            default = None
            if funcsig:
                p = funcsig.parameters.get(name)
                if p is None:
                    if decl.decltype == "meta":
                        # メタメソッドでのみ、名前が食い違っても許す
                        flags |= PARAMETER_REQUIRED
                    else:
                        raise BadMethodDeclaration("引数'{}'は宣言されていますが、関数に存在しません".format(name))

                if p is not None:
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

            typedecl = tnresolver.parse_type_declaration(typename)
            self.add_parameter(name, typedecl, doc, default, flags=flags)

        # 戻り値
        for line in sections.get_lines("Returns"):
            typename, doc, flags = parse_result_line(line.strip())
            typedecl = tnresolver.parse_type_declaration(typename)
            self.add_result(typedecl, doc)

        # 戻り値デコレータ
        decoexpr = sections.get_string("Decorates")
        if decoexpr:
            self.set_result_decorator(decoexpr.strip())
        
    def load_declaration_properties(self, props: Sequence[str]):
        """
        宣言の値を読み込んでフラグを設定する
        """
        if "spirit" in props:
            self.flags |= METHOD_SPIRIT_BOUND
        if "context" in props:
            self.flags |= METHOD_CONTEXT_BOUND
        if "external" in props:
            self.flags |= METHOD_EXTERNAL
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
        else:
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
            target = repr(fn)

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

    def load_default_meta(self, selftype):
        """ デフォルトのメタメソッドの実装を型から読み込む """
        target = "default_"+self.name
        self._action = getattr(selftype, target)
        self.target = target
        self.flags |= METHOD_LOADED

    def make_invocation(self, mods=None, type=None):
        """ 適した呼び出しオブジェクトを作成する """
        def argminmax(i,x):
            return i, (0xFFFF if x is None else x)
        
        bit = self.flags & METHOD_INVOKEAS_MASK
        if bit == METHOD_INVOKEAS_BOUND_METHOD or bit == METHOD_INVOKEAS_PROPERTY:
            if not isinstance(self._action, InstanceBoundAction):
                raise ValueError("InstanceBoundAction must be specified when METHOD_INVOKEAS_BOUND_METHOD or METHOD_INVOKEAS_PROPERTY is set")
            ami, amx = argminmax(self.get_required_argument_min(), self.get_acceptable_argument_max())
            from machaon.core.invocation import InstanceMethodInvocation
            return InstanceMethodInvocation(self._action.target, mods, ami, amx)

        elif bit == METHOD_INVOKEAS_FUNCTION or bit == METHOD_INVOKEAS_BOUND_FUNCTION:
            ami, amx = argminmax(self.get_required_argument_min(), self.get_acceptable_argument_max())
            from machaon.core.invocation import FunctionInvocation
            return FunctionInvocation(self._action, mods, ami, amx)

        elif bit == METHOD_INVOKEAS_IMMEDIATE_VALUE:
            from machaon.core.invocation import FunctionInvocation
            return FunctionInvocation(self._action, mods, 0, 0)

        else:
            if type is None:
                raise ValueError("type argument must be specified")
            from machaon.core.invocation import TypeMethodInvocation
            return TypeMethodInvocation(type, self, mods)
        
    def prepare_invoke_args(self, args, *, selftype=None, context=None, typeargs=None):
        """ 
        メソッド実行時に渡す引数を準備する 
        引数の順番：
            <describer> traitメソッドである場合
            <self> 外部メソッドでない場合
            <context> context宣言がある場合
            <spirit> spirit宣言がある場合
            <typeargs...> 型引数
            <args...> 引数
        Params:
            args(Object[]): 引数
            selftype(Type):
            context(InvocationContext):
            typeargs(Any[]):
        """
        if self.flags & METHOD_LOADED == 0:
            raise UnloadedMethod(self.name)
        
        ivargs = []
        
        external = self.is_external()

        if self.is_type_value_bound(): # or (selftype and selftype.get_methods_bound_type() == METHODS_BOUND_TYPE_TRAIT_INSTANCE):
            if selftype is not None:
                desc = self.get_describer(selftype)
                if isinstance(desc, type):
                    desc = desc()    
                ivargs.append(desc)
            else:
                raise MethodCallingError("trait実装のメソッドですが、selftypeが引数に渡されていません")
        elif self.is_type_class_bound():
            # 値の方がクラスよりも優先される
            if selftype is not None:
                desc = self.get_describer(selftype)
                ivargs.append(desc)
            else:
                raise MethodCallingError("trait実装のメソッドですが、selftypeが引数に渡されていません")

        if not external:
            selfspec = MethodParameter("self") # デフォルトのパラメータスペック
            selfarg, *args = args
            ivargs.append(selfspec.make_argument_value(context, selfarg))

        if self.is_context_bound(): 
            if context is not None:
                ivargs.append(context)
            else:
                raise MethodCallingError("contextを要求していますが、引数に渡されていません")
        if self.is_spirit_bound():
            if context is not None:
                ivargs.append(context.spirit)
            else:
                raise MethodCallingError("spiritを要求していますが、引数にcontextが渡されていません")

        # 型引数を集める
        if typeargs is not None:
            ivargs.extend(typeargs)

        # 引数を生成する
        if not external or not self.is_nullary():
            if context is not None:
                argvalues = self.make_argument_row(context, args)
                ivargs.extend(argvalues)
            else:
                ivargs.extend([x.value if isinstance(x,Object) else x for x in args])
            
        return ivargs

    def get_signature(self, *, fully=False):
        """ @method alias-name [signature]
        メソッドの構文を返す。
        Returns:
            Str: 構文
        """
        # パラメータ
        params = []
        for p in self.params:
            ps = ""
            ptype = p.get_typename()
            if p.is_required():
                ps = ptype
            else:
                if fully:
                    ps = "{}={}".format(ptype, repr(p.default))
                else:
                    ps = "{}?".format(ptype)
            if p.is_variable():
                ps = "*" + ptype
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
        if not self.is_external():
            params.insert(0, "@") # レシーバを引数として表現
        if params:
            parts.append(" ".join(params))
        parts.append("->")
        parts.append(", ".join(results))
        return " ".join(parts)

    def constructor(self, cxt, value=None):
        """ @meta context
        Params:
            str|None: 外部メソッド指定
        """
        if value is None:
            return Method()
        from machaon.core.message import select_method
        inv = select_method(value, context=cxt)
        if inv.display()[0] != "TypeMethod":
            raise ValueError("{}: 無効なメソッド名です".format(value))
        return inv.get_method()
    
    def pprint(self, app):
        """ @meta """
        app.post("message", self.name)
        app.post("message", self.doc)
        sig = self.get_signature(fully=True)
        app.post("message", sig)

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
class MethodParameter:
    def __init__(self, name, typedecl=None, doc="", default=None, flags=0):
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
        
    def is_variable_oneormore(self):
        return (self.flags & PARAMETER_VARIABLE_ONEORMORE) > 0

    def set_required(self):
        self.flags |= PARAMETER_REQUIRED
    
    def set_variable(self):
        self.flags |= PARAMETER_VARIABLE
    
    def get_default(self):
        return self.default
    
    def get_typedecl(self):
        return self.typedecl
        
    def make_argument_value(self, context, val, typeinst=None, *, construct=False):
        """ 型を検査しつつオブジェクトから引数となる値を得る """
        if isinstance(val, Object):
            construct = False
            obj_value = True
        else:
            obj_value = False
        
        # デフォルト引数を返す
        if obj_value and not construct:
            usedefault = val.value is MethodParameterDefault
        else:
            usedefault = val is MethodParameterDefault
        if usedefault and not self.is_required():
            if self.is_object():
                return None # 常にNoneを使う
            else:
                return self.default

        if self.is_object():
            if construct:
                return context.new_object(val)
            elif obj_value:
                return val
            else:
                raise ValueError("Object is required, but not passed")
        elif self.is_type_uninstantiable():
            if construct:
                raise ValueError("cannot be constructed")
            elif obj_value:
                return val.value
            else:
                return val
        else:
            t = typeinst or self.get_typedecl().instance(context)
            if construct:
                if isinstance(val, TypeDecl) and not self.is_type():
                    val = val.to_string() # 非型引数を値に変換する
                try:
                    value = t.construct(context, val)
                except Exception as e:
                    raise ArgumentTypeError(self, val, str(e)) from e
            elif obj_value:
                value = val.value
            else:
                value = val
            
            if not t.check_value_type(type(value)):
                raise ArgumentTypeError(self, value)

            return value
    
    def check_argument_value(self, context, value):
        """ 型を検査する """
        if self.is_object():
            return isinstance(value, Object)
        else:
            t0 = self.get_typedecl().instance(context)
            return t0.check_value_type(type(value))


class ArgumentTypeError(Exception):
    def __init__(self, spec, value, cause=None):
        super().__init__()
        self.spec = spec
        self.value = value
        self.cause = cause
    
    def __str__(self):
        if hasattr(self.spec, "name"):
            spec = "引数'{}'の型'{}'".format(self.spec.name, self.spec.typename)
        else:
            spec = "型'{}'".format(self.spec.typename)
        value = repr(self.value)
        s = "{}は{}に適合しません".format(value, spec)
        if self.cause:
            s += "\n型変換エラー: {}".format(self.cause)
        return s


#
#
#
class MethodResult:
    def __init__(self, typedecl=None, doc="", special=None):
        self.typedecl = typedecl or TypeDecl()
        self.doc = doc
        self.special = special
        self.decorator = None
        if not isinstance(self.typedecl, TypeDecl):
            raise TypeError("MethodResult.typedecl")

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

    def is_already_instantiated(self):
        return isinstance(self.typedecl, TypeInstanceDecl)

    def get_typedecl(self):
        return self.typedecl
    
    def set_decorator(self, expr):
        self.decorator = expr

    def make_result_value(self, context, value, *, message=None, negate=False):
        """ 型を検査しつつオブジェクトから返り値となる値を得る 
        Returns:
            Tuple[TypeProxy, Any]:
        """
        # Object
        if isinstance(value, Object):
            return (value.type, value.value)

        # return-self
        if self.is_return_self():
            if message is None:
                raise ValueError("No message is specified to get return-self value")
            # レシーバオブジェクトを返す
            reciever = message.get_reciever_value()
            if not isinstance(reciever, Object):
                raise ValueError("reciever must be Object")
            if value is not None and value is not reciever.value:
                raise ValueError("Value returned in return-self context will be discarded: {}".format(value))
            return (reciever.type, reciever.value)
        
        # Noneはそのまま返す
        if value is None:
            return (context.get_type("None"), None)

        # 型拡張の定義かどうか
        extension = get_type_extension_loader(value)
        if extension is not None:
            value = extension.get_basic()
        
        # 型を決める
        rettype = None
        if self.is_already_instantiated():
            rettype = self.typedecl.instance(context)
        elif self.is_type_to_be_deduced():
            rettype = context.deduce_type(value) # 型を値から推定する
        else:
            rettype = self.typedecl.instance(context)

        # 型拡張がある場合は、適用する
        if extension is not None:
            rettype = extension.load(rettype)

        # NEGATEモディファイアを適用            
        if negate:
            value = not value

        # 返り値型に値が適合しない場合は、型変換を行う
        if not rettype.check_value_type(type(value)):
            value = rettype.construct(context, value)

        # デコレータを適用する
        if self.decorator is not None:
            if isinstance(self.decorator, str): # コンパイルする
                from machaon.core.function import parse_sequential_function
                self.decorator = parse_sequential_function(self.decorator, context, argspec=rettype)
            
            value = self.decorator(value)
            if not rettype.check_value_type(type(value)): # 必要なら、さらに型変換を行う
                value = rettype.construct(context, value)

        return (rettype, value)


def parse_parameter_line(line, index=None):
    """
    Params:
        line(str):
    Returns:
        Tuple[str, str, int]: 型名、変数名、フラグ
    """
    head, _sep, doc = [x.strip() for x in line.partition(":")]
    # sepが無くても続行する    

    flags = 0
    if head.startswith(("*","+")):
        # 可変長引数
        name, _, right = head[1:].partition("(")
        if right:
            typename, _, _ = right.rpartition(")")
            typename = typename.strip()
        else:
            typename = "Any"
        flags |= PARAMETER_VARIABLE
        if head[0] == "+":
            flags |= PARAMETER_VARIABLE_ONEORMORE
    else:
        name, _, paren = head.partition("(")
        name = name.strip()
        if name.endswith("?"):
            name = name[:-1]
        else:
            flags |= PARAMETER_REQUIRED
        typename, _, _ = paren.rpartition(")")
        typename = typename.strip()

    if index is not None and name and not typename: # 名前を補完する
        typename = name
        if index == 0:
            name = "value"
        else:
            name = "value{}".format(index+1)
    
    if not name and not typename:
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


def make_method_prototype_from_doc(decl, attrname, mixinkey=None) -> Tuple[Optional[Method], List[str]]:
    """ 
    ドキュメントを解析して空のメソッドオブジェクトを構築 
    Params:
        decl(DocStringDeclaration): ドキュメント宣言
        attrname(str): 属性名
        *mixinkey(str): mixinクラスへの参照名
    """ 
    mname = decl.name or attrname
    method = Method(name=normalize_method_name(mname), target=attrname, mixin=mixinkey, flags=METHOD_FROM_USER_DEFINITION)
    method.load_declaration_properties(decl.props)
    return method, decl.aliases

def make_method_from_dict(name, di, mixinkey=None):
    """
    辞書による定義からメソッドを作成する
    """
    if name is None:
        raise BadMethodDeclaration("メソッド名を指定してください")
    mth = Method(name, flags=METHOD_FROM_USER_DEFINITION, mixin=mixinkey)
    mth.load_from_dict(di)
    return mth


class MetaMethods:
    def __init__(self):
        prototypes = [
            Method("constructor", flags=METHOD_TYPE_BOUND|METHOD_EXTERNAL),
            Method("stringify"),
            Method("summarize"),
            Method("pprint"),
        ]
        self.prototypes = {x.get_name():x for x in prototypes}
        self.prototypes["constructor"].add_parameter("value", "Any")

    def get_prototype(self, name):
        """ 
        空の新しいメタメソッドを返す 
        Params:
            decl(DocStringDeclaration): ドキュメント宣言
            attrname(str): 属性名
        """ 
        protometh = self.prototypes.get(name)
        if protometh is None:
            return None
        flags = protometh.flags & ~METHOD_LOADBIT_MASK # ロードフラグは引き継がないように
        meta = Method(name, target=name, flags=flags)
        return meta
    
    def load_default(self, name, selftype):
        """ 
        デフォルトのメタメソッドを取得する
        """
        protometh = self.prototypes.get(name)
        if protometh is None:
            raise MethodLoadError("meta method '{}' does not exist".format(name))
        protometh.load_default_meta(selftype)
        return protometh


meta_methods = MetaMethods()

#
#
# インスタンスメソッド
#
#
class InstanceBoundAction:
    def __init__(self, target):
        self.target = target

    def __call__(self, *args):
        raise ValueError("未解決のアクションのため呼び出せません")

class ImmediateValue:
    def __init__(self, value, name):
        self.value = value
        self.name = name

    def __repr__(self):
        name = self.name or repr(self.value)
        return "<ImmediateValue '{}'>".format(name)
    
    def get_action_name(self):
        name = self.name or repr(self.value)
        return "ImmediateValue<{}>".format(name)

    def __call__(self, *args):
        return self.value

        
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
            return METHOD_INVOKEAS_IMMEDIATE_VALUE
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


class _InvokeasTypeDict:
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


def make_method_from_value(value, name, invokeas, source=METHOD_FROM_USER_DEFINITION):
    """ 値からメソッドオブジェクトを作成する """
    m = Method(name, flags=invokeas|source)
    if invokeas == METHOD_INVOKEAS_FUNCTION:
        m.load_from_function(value)  
    elif invokeas == METHOD_INVOKEAS_BOUND_FUNCTION:
        m.load_from_function(value, self_to_be_bound=True)
    elif invokeas == METHOD_INVOKEAS_BOUND_METHOD:
        if getattr(value, "__self__", None) is not None:
            m.load_from_function(value, action=InstanceBoundAction(name))
        else:
            m.load_from_function(value, action=InstanceBoundAction(name), self_to_be_bound=True)
    elif invokeas == METHOD_INVOKEAS_PROPERTY:
        if inspect.ismethoddescriptor(value) or inspect.isdatadescriptor(value):
            tn = "Any"
        else:
            tn, _val = split_typename_and_value(value)
        m.load_from_dict({
            "Params" : [],
            "Returns": { "Typename": tn },
            "Action" : InstanceBoundAction(name)
        })
    elif invokeas == METHOD_INVOKEAS_IMMEDIATE_VALUE:
        tn, val = split_typename_and_value(value)
        m.load_from_dict({
            "Params" : [],
            "Returns": { "Typename": tn },
            "Action" : ImmediateValue(val, name)
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


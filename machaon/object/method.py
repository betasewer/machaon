from typing import Any, Sequence, List, Dict, Union, Callable, ItemsView, Optional, DefaultDict

import inspect
from collections import defaultdict

from machaon.object.typename import normalize_typename
from machaon.object.docstring import DocStringParser

# imported from...
# type
# operator
#
#

#
METHOD_TASK = 0x0001
METHOD_CONSUME_TRAILING_PARAMS = 0x0002
METHOD_TYPE_BOUND = 0x0010

#
PARAMETER_REQUIRED = 0x0100
PARAMETER_VARIABLE = 0x0200

#
class BadMethodName(Exception):
    pass
class BadMethodDeclaration(Exception):
    pass
class UnloadedMethod(Exception):
    pass

#
def normalize_method_target(name):
    return name.replace("-","_") # ハイフンはアンダースコア扱いにする

#
class MethodParameterNoDefault:
    pass

#
#
#
class Method():
    def __init__(self, name = None, target = None, doc = "", is_task = False):
        self.name: str = name
        self.doc: str = doc

        self.target: str = target
        self._action = None
        
        self.flags = 0
        if is_task:
            self.flags |= METHOD_TASK

        self.params: List[MethodParameter] = []
        self.results: List[MethodResult] = []

    def check_valid(self):
        if self.name is None:
            raise ValueError("name")
    
    def get_name(self):
        return self.name
        
    def get_first_result_typename(self):
        if self.results:
            return self.results[0].get_typename()
        else:
            return None
    
    def get_doc(self):
        return self.doc
    
    def get_action_target(self):
        if self._action is None:
            raise ValueError("Action is not loaded")
        return self.target
    
    def get_action(self):
        return self._action

    def is_task(self):
        return (self.flags & METHOD_TASK) > 0
        
    def is_trailing_params_consumer(self):
        return (self.flags & METHOD_CONSUME_TRAILING_PARAMS) > 0
    
    def is_type_bound(self):
        return (self.flags & METHOD_TYPE_BOUND) > 0

    # 仮引数を追加
    def add_parameter(self,
        name,
        typename,
        doc = "",
        default = MethodParameterNoDefault,
        variable = False,
        *,
        flags = 0
    ):
        f = 0
        if flags:
            f |= flags
        if variable:
            f |= PARAMETER_VARIABLE
        if default is MethodParameterNoDefault:
            default = None
            f |= PARAMETER_REQUIRED
        p = MethodParameter(name, typename, doc, default, f)
        self.params.append(p)
    
    def get_param_count(self):
        return len(self.params)

    # 返り値宣言を追加
    def add_result(self, 
        typename, 
        doc = ""
    ):
        r = MethodResult(typename, doc)
        self.results.append(r)
        
    def get_result_count(self):
        return len(self.results)
    
    # 受け入れ可能なスペース区切りの引数の数、Noneで無限を示す
    def get_acceptable_argument_max(self) -> Union[int, None]:
        cnt = 0
        for p in self.params:
            if p.is_variable():
                return None
            cnt += 1
        return cnt
        
    # 必要な最小の引数の数を得る
    def get_required_argument_min(self) -> int:
        cnt = 0
        for p in self.params:
            if not p.is_required():
                break
            cnt += 1
        return cnt

    #
    # 構文で引数を追加する
    # 
    def __getitem__(self, declaration: str):
        declaration = declaration.rstrip()
        if declaration.startswith("->"):
            return method_result_declaration_chain(self, declaration)
        else:
            return method_parameter_declaration_chain(self, declaration)

    #
    # 実装のロード
    #
    def load(self, this_type):
        if self._action is not None:
            return

        if self.target is None:
            self.target = normalize_method_target(self.name)     

        # 実装コードを読み込む
        from machaon.object.importer import attribute_loader
        action = None
        source = None
        while True:
            loader = attribute_loader(self.target)
            callobj = None

            if loader is None:
                # 1. 型定義のメソッドを取り出す
                typefn = this_type.method_delegation(self.target)
                if typefn is not None:
                    callobj = typefn
                    source = "TypeMethod:{}".format(self.target)
                    if this_type.is_method_bound("TYPE"):
                        self.flags |= METHOD_TYPE_BOUND # 第一引数は型オブジェクトを渡す
            else:
                # 2. 外部モジュールから定義をロードする
                callobj = loader() # モジュールやメンバが見つからなければ例外が投げられる
                source = "ImportedMethod:{}".format(self.target)
            
            # アクションオブジェクトの初期化処理
            if hasattr(callobj, "describe_method"):
                # アクションに定義されたメソッド定義処理があれば実行
                callobj.describe_method(self)
            elif hasattr(callobj, "__doc__") and callobj.__doc__ is not None:
                # callobjのdocstringsを解析する。
                self.load_syntax_from_docstring(callobj.__doc__, callobj)
            else:
                raise BadMethodDeclaration("メソッド定義がありません。メソッド 'describe_method' かドキュメント文字列で記述してください")
        
            if isinstance(callobj, type):
                callobj = callobj()
        
            if callobj is not None and callable(callobj):
                action = callobj
                break
            
            raise ValueError("無効なアクションです：{}".format(self.target))

        self._action = action
        self.target = source
    
    def is_loaded(self):
        return self._action is not None

    # docstringの解析で引数を追加する
    def load_syntax_from_docstring(self, doc: str, function: Callable):
        """ @method [alias-names]
        メソッドの説明
        Params:
            caption (str): 見出し 
            count (int): 回数
        Returns:
            str: 結果の文字列
        """
        sections = DocStringParser(doc, (
            "Returns", 
            "Params",
            "Parameters",
            "Arguments",
            "Args",
        ))
        method_type, _, desc = sections.get_string("Summary").partition(" ")
        if "[" in desc and "]" in desc:
            _, _, desc = desc.partition("]") # エイリアス宣言を読み飛ばす

        desc += sections.get_string("Description")
        if desc:
            self.doc = desc.strip()

        if method_type == "@task":
            self.flags |= METHOD_TASK
        else:
            self.flags = self.flags & (~METHOD_TASK)

        #
        funcsig = inspect.signature(function)
        
        # 引数
        lines = sections.get_lines("Params", "Parameters", "Arguments", "Args")
        for line in lines:
            flags = 0

            head, _, doc = [x.strip() for x in line.partition(":")]
            if head.startswith("*"):
                name = head[1:]
                typename = "Any"
                flags |= PARAMETER_VARIABLE
            else:
                name, _, paren = head.partition("(")
                name = name.strip()
                typename, _, _ = paren.partition(")")
                typename = typename.strip()
            
            if typename.endswith("..."):
                self.flags |= METHOD_CONSUME_TRAILING_PARAMS
                typename = typename.rstrip(".")

            p = funcsig.parameters.get(name)
            if p is None:
                raise BadMethodDeclaration()
            
            default = p.default
            if default is inspect.Signature.empty:
                default = None
                flags |= PARAMETER_REQUIRED
            
            if p.kind == p.VAR_KEYWORD or p.kind == p.KEYWORD_ONLY:
                raise BadMethodDeclaration("キーワード引数には未対応です")
            
            typename = normalize_typename(typename)
            self.add_parameter(name, typename, doc, default, flags=flags)

        # 戻り値
        lines = sections.get_lines("Returns")
        for line in lines:
            typename, _, doc = [x.strip() for x in line.partition(":")]
            typename = normalize_typename(typename)
            self.add_result(typename, doc)
    
    # 直に設定
    def set_action(self, action):
        self._action = action

        
#
#
#
class MethodParameter():
    def __init__(self, name, typename, doc, default=None, flags=0):
        self.name = name
        self.typename = typename
        self.doc = doc
        self.default = default
        self.flags = flags
    
    def get_name(self):
        return self.name

    def get_typename(self):
        return self.typename
    
    def get_doc(self):
        return self.doc
    
    def is_any(self):
        return self.typename == "Any"

    def is_raw_string(self):
        return self.typename == "RawString"

    def is_required(self):
        return (self.flags & PARAMETER_REQUIRED) > 0

    def is_variable(self):
        return (self.flags & PARAMETER_VARIABLE) > 0
    
    def get_default(self):
        return self.default

#
#
#
class MethodResult:
    def __init__(self, typename, doc=""):
        self.typename = typename
        self.doc = doc

    def get_typename(self):
        return self.typename    

    def get_doc(self):
        return self.doc

#
#
#
def method_parameter_declaration_chain(method, declaration):
    # param1: int
    # param2: any
    if declaration and isinstance(declaration, str):
        if ":" in declaration:   
            varpart, typepart = declaration.split(":")
        else:
            varpart, typepart = declaration, "Any"
        typename = typepart.strip()
        
        paramname = varpart.strip()
    else:
        raise TypeError()

    def trailing_call(
        **kwargs
    ):
        method.add_parameter(paramname, typename, **kwargs)
        return method

    return trailing_call
    
#
def method_result_declaration_chain(method, declaration):
    if declaration and isinstance(declaration, str):
        typepart = declaration[declaration.find("->"):].strip()
        if not typepart:
            raise ValueError("型指定がありません")
        typename = typepart    
    else:
        raise TypeError()

    def trailing_call(
        **kwargs
    ):
        method.add_result(typename, **kwargs)
        return method

    return trailing_call

#
#
#
def create_method_prototype(traits, method_type, target, name, othernames, resulttype, params, **kwargs):
    if not resulttype:
        resulttype = "Any"
    
    if method_type == "task":
        kwargs["is_task"] = True
    elif method_type == "member":
        pass

    if method is None:
        method = Method(name=name, target=target, **kwargs)
        for n, t, d in params:
            method.add_parameter(n, t, doc=d)
        method.add_result(resulttype)
    
    method.check_valid()

    traits.add_method(method)
    for alias in othernames:
        traits.add_method_alias(alias, name)
    
    return method

#
# prorotype + describe_method
# )[method <method-name> -> ReturnType](
#   parameter and result decl... (traits.describe_method)
# )
#
def methoddecl_setter_chain(traits, method_type, declaration):
    namerow, _, typename = [x.strip() for x in declaration.partition("->")]
    names = namerow.split()
    if len(names) == 0:
        raise BadMethodDeclaration("Bad declaration syntax: [method|task <method-name> (-> <return-type>)]")

    name, *othernames = names
    
    def trailing_call(method=None, *, target=None, **kwargs):
        create_method_prototype(traits, method_type, target, name, othernames, typename, [], **kwargs)
        return traits
    return trailing_call

# 
# 特定のドキュメント文字列を持った属性を列挙する
#
def methoddecl_collect_attribute(traits, describer):
    for attrname in dir(describer):
        attr = getattr(describer, attrname)
        if attrname.startswith("__"):
            continue

        doc = getattr(attr, "__doc__", "")
        if not doc:
            continue

        firstline, br, _ = doc.partition("\n")
        if not br:
            firstline = doc
        
        # メソッド宣言
        firstline = firstline.strip()
        method = None
        if firstline.startswith("@method"):
            method = Method(name=attrname, target=attrname)
        elif firstline.startswith("@task"):
            method = Method(name=attrname, target=attrname, is_task=True)
        else:
            continue
        traits.add_method(method)

        # エイリアス宣言
        aliasnames = []
        if "[" in firstline and "]" in firstline:
            _, _, aliasrow = firstline.partition("[")
            aliasrow, _, _ = aliasrow.partition("]")
            aliasnames.extend(aliasrow.strip().split())

        for aliasname in aliasnames:
            traits.add_member_alias(aliasname, attrname)

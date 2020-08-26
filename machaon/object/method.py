from typing import Any, Sequence, List, Dict, Union, Callable, ItemsView, Optional, DefaultDict

import inspect
from collections import defaultdict

# imported from...
# type
# operator
#
#

#
METHOD_TASK = 0x1

#
PARAMETER_REQUIRED = 0x01
PARAMETER_VARIABLE = 0x10

#
class MethodParameterNoDefault:
    pass


#
def normalize_method_target(name):
    return name.replace("-","_") # ハイフンはアンダースコア扱いにする

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

    def is_task(self):
        return (self.flags & METHOD_TASK) > 0

    # 仮引数を追加
    def add_parameter(self,
        name,
        typename,
        doc = "",
        default = MethodParameterNoDefault,
        variable = False
    ):
        f = 0
        if variable:
            f |= PARAMETER_VARIABLE
        if default is MethodParameterNoDefault:
            f |= PARAMETER_REQUIRED
        p = MethodParameter(name, typename, doc, default, f)
        self.params.append(p)

    # 返り値宣言を追加
    def add_result(self, 
        typename, 
        doc = ""
    ):
        r = MethodResult(typename, doc)
        self.results.append(r)
    
    # 受け入れ可能なスペース区切りの引数の数、Noneで無限を示す
    def get_acceptable_argument_max(self) -> Union[int, None]:
        cnt = 0
        for p in self.params:
            if p.is_raw_string() or p.is_variable():
                return None
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
    def load_action(self, this_type):
        if self._action is not None:
            return self._action

        if self.target is None:
            self.target = normalize_method_target(self.name)     

        # 実装コードを読み込む
        from machaon.object.importer import get_importer
        action = None
        source = None
        while True:
            importer = get_importer(self.target)

            # 1. 型定義のメソッドを取り出す
            if importer is None:
                typefn = this_type.get_method_delegation(self.target)
                if typefn is not None:
                    action = typefn
                    source = "TypeMethod:{}".format(self.target)
                    break
        
            # 2. 外部モジュールから定義をロードする
            callobj = None
            if importer is not None:
                callobj = importer() # モジュールやメンバが見つからなければ例外が投げられる
                source = "ImportedMethod:{}".format(self.target)
            
            # アクションオブジェクトの初期化処理
            if hasattr(callobj, "describe_method"):
                # アクションに定義されたメソッド定義処理があれば実行
                callobj.describe_method(self)
            else:
                # TODO: callobjのdocstringsを解析する。
                pass
        
            if isinstance(callobj, type):
                callobj = callobj()
        
            if callobj is not None and callable(callobj):
                action = callobj
                break
            
            raise ValueError("無効なアクションです：{}".format(self.target))

        self._action = action
        self.target = source
        return action
        
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
# member <method-name> -> ReturnType
# operator <method-name> -> ReturnType
# task <method-name> -> ReturnType
#
def method_declaration_chain(traits, declaration):
    decl, _, typename = [x.strip() for x in declaration.partition("->")]
    method_type, _, names = [x.strip() for x in decl.partition(" ")]
    name, *othernames = names.split()
    
    if not typename:
        typename = "Any"
    
    if not names:
        names = method_type
        method_type = "member"    
    
    defparams = None
    istask = False
    if method_type == "task":
        istask = True
    elif method_type == "member":
        defparams = []
    elif method_type == "operator":
        defparams = [("right", "Any", "第2引数")]

    #
    def trailing_call(
        method=None,
        *, 
        target=None, 
        **kwargs
    ):
        kwargs.setdefault("is_task", istask)

        if method is None:
            method = Method(name=name, target=target, **kwargs)
            for n, t, d in defparams:
                method.add_parameter(n, t, doc=d)
            method.add_result(typename)
        
        method.check_valid()

        traits.add_method(method)
        for alias in othernames:
            traits.add_method_alias(alias, name)
        
        return traits

    return trailing_call


"""
declare_method("member position p -> Coord")(
    doc='''座標'''
)
declare_method("operator less-than -> bool")(
    doc='''比較する''',
    param1_name = "target right: This",
    param1_doc = ,
    param1_default = ,
)
declare_method("operator less-than -> bool")(
    Method(
        target=""
    )["target right: This"](
        doc="右パラメータ"
    )

    doc='''比較する''',
    param1_name = "target right: This",
    param1_doc = ,
    param1_default = ,
)

"""



#
class TypeMethodAlias:
    def __init__(self, name, dest):
        self.name = name
        self.dest = dest
    
    def get_name(self):
        return self.name
    
    def get_destination(self):
        return self.dest



"""
class SomeObject:
    def time(self):
        ....
    
    def name(self):
        ...
    
    def is_equal(self, right):
        return True
    
    def make_index(self, root):
        return make_index()
    
    @classmethod
    def describe_object(cls, traits):
        traits.describe(

        )["member time"](

        )["member name"](

        )["operator is-equal"](
            
        )["task make-index: Index"](
            traits.describe_method(
                target=""
            )["target page: int"](
                doc='''対象頁番号'''
            )["target bleed: int"](
                doc='''裁ち落とし（mm）''',
            )["target turtle: bool"](
                doc='''タートルグラフィックス'''
            )["-> int"](
            )["-> "]
        )








"""
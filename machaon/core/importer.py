from collections import defaultdict
import importlib
import importlib.util
import builtins
import os
import ast

from machaon.core.docstring import parse_doc_declaration
from machaon.core.symbol import full_qualified_name


def module_loader(expr=None, *, location=None):
    if location:
        if expr is None:
            expr = location
        return PyModuleFileLoader(expr, location)
    else:
        if expr is None:
            raise TypeError("expr")
        return PyModuleLoader(expr)

def attribute_loader(expr, *, attr=None, location=None):
    modloader = None
    member = None
    if attr is None:
        mod, _, member = expr.rpartition(".")
        if not member:
            member = expr
            mod = None
    else:
        member = attr
        mod = expr
    if mod:
        modloader = module_loader(mod, location=location)
    return AttributeLoader(modloader, member)

def module_loader_from_file(path, namebasepath):
    name = module_name_from_path(path, namebasepath)
    return PyModuleFileLoader(name, path)

class PyBasicModuleLoader:
    """
    ローダーの基礎クラス
    """
    def __init__(self, m=None): # モジュールのインスタンスを受ける
        self._m = m
        self._requires = []
        self._pkg_submods = []
        self._usingtypes = []
    
    @property
    def module(self):
        if self._m is None:
            self._m = self.load_module()
        return self._m

    def get_name(self):
        raise NotImplementedError()
        
    def load_module(self):
        raise NotImplementedError()

    def load_filepath(self):
        raise NotImplementedError()
    
    def load_source(self):
        p = self.load_filepath()
        if p is None:
            return None
        with open(p, "r", encoding="utf-8") as fi:
            return fi.read()
    
    def load_attr(self, name=None, *, fallback=False):
        mod = self.module
        loaded = getattr(mod, name, None)
        if loaded is None and not fallback:
            raise ValueError("ターゲット'{}'はモジュール'{}'に存在しません".format(name, mod.__name__))
        return loaded
    
    def load_package_directories(self):
        mod = self.module
        if getattr(mod, "__path__", None) is not None:
            for path in mod.__path__:
                yield path
        elif getattr(mod, "__file__", None) is not None:
            yield os.path.dirname(mod.__file__)
        else:
            raise ValueError("__path__, __file__属性が無く、ディレクトリを特定できません")
    
    def load_module_declaration(self, doc=None):
        """ ソースコードの構文木からモジュールのドキュメント文字列を取り出し、解析する 
        """
        if doc is None:
            source = self.load_source()
            if source is None:
                return
            disp = str(self)
            tree = compile(source, disp, 'exec', ast.PyCF_ONLY_AST)
            doc = ast.get_docstring(tree)
        
        if not doc:
            return

        decl = parse_doc_declaration(doc, ("module",))
        if decl is None:
            return
        
        pser = decl.create_parser((
            "Extra-Requirements Extra-Req",
            "Submodules",
            "Using",
        ))
        # 追加の依存するmachaonパッケージ名
        requires = [x.strip() for x in pser.get_string("Extra-Requirements").split(",")]
        self._requires = requires
        
        # パッケージで、型定義が含まれるモジュールを明示する
        self._pkg_submods = []
        for line in pser.get_lines("Submodules"):
            m = module_loader(line)
            self._pkg_submods.append(m)

        # 参照する外部のmachaon型
        self._usingtypes = []
        for line in pser.get_lines("Using"):
            typename, sep, modname = line.partition(":")
            if not sep:
                raise ValueError("Invalid module declaration: Using: [typename]:[modulename]")
            from machaon.core.type import TypeDefinition, BadTypeDeclaration
            d = TypeDefinition(value_type=modname.strip(), typename=typename.strip())
            if not d.load_declaration_docstring():
                raise BadTypeDeclaration()
            self._usingtypes.append(d)
    
    def get_extra_requirements(self):
        return self._requires

    def get_package_submodules(self):
        return self._pkg_submods
    
    def scan_type_definitions(self):
        """ ソースコードの構文木を解析し、型を定義するクラスの名前を取り出す
        Yields:
            TypeDefinition: ドキュメント文字列解析済みの定義オブジェクト
        """
        source = self.load_source()
        disp = str(self)
        tree = compile(source, disp, 'exec', ast.PyCF_ONLY_AST)

        # モジュールのドキュメント文字列に書かれた宣言をロードする
        moduledoc = ast.get_docstring(tree)
        self.load_module_declaration(moduledoc)

        # モジュールに定義されたクラスのドキュメント文字列を全て読んでいく
        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            doc = ast.get_docstring(node)
            if not doc:
                continue
            doc = doc.lstrip()
            
            classname = None
            for name, field in ast.iter_fields(node):
                if name == "name":
                    classname = field
                    break
            if classname is None:
                raise ValueError("no classname")
            
            describer = ClassDescriber(AttributeLoader(self, classname))

            from machaon.core.type import TypeDefinition
            d = TypeDefinition(describer, classname)
            if not d.load_declaration_docstring(doc):
                continue

            yield d

        # 外部型
        for d in self._usingtypes:
            yield d
    
    def scan_print_type_definitions(self, app):
        """ 型を定義するクラスの詳細を取り出す。調査用
        Yields:
            ObjectCollection(typename, qualname, error):
        """
        count = 0

        modqualname = str(self)
        app.post("message", "{}".format(modqualname))

        err = None
        try:
            for typedef in self.scan_type_definitions():
                typename = typedef.get_scoped_typename()
                qualname = typedef.get_describer_qualname()
                yield {
                    "typename" : typename,
                    "qualname" : qualname
                }
                app.post("message", "  {}".format(typename))
                count += 1
        except Exception as e:
            err = e
        
        if count > 0:
            app.post("message", "  型定義を{}個発見".format(count))
        if err:
            app.post("error", "  ロードエラー:{}".format(err))
            yield {
                "qualname" : modqualname,
                "error" : err
            }


class PyModuleLoader(PyBasicModuleLoader):
    """
    配置されたモジュールからロードする
    """
    def __init__(self, module):
        super().__init__()
        self.module_name = module
    
    def get_name(self):
        return self.module_name

    def load_module(self):
        import sys
        if self.module_name in sys.modules:
            mod = sys.modules[self.module_name]
        else:
            # sys.modulesの扱いを任せる
            mod = importlib.import_module(self.module_name)
        return mod
    
    def load_filepath(self):
        spec = importlib.util.find_spec(self.module_name)
        if spec is None:
            raise ValueError("モジュールが見つかりません")
        return get_first_package_path(self._m, spec)
    
    def __str__(self) -> str:
        return self.module_name


class PyModuleFileLoader(PyBasicModuleLoader):
    """
    ファイルパスを指定してロードする
    """
    def __init__(self, module, path):
        super().__init__()
        self.module_name = module
        self._path = path
    
    def get_name(self):
        return self.module_name
    
    def load_module(self):
        spec = importlib.util.spec_from_file_location(self.module_name, self._path)
        if spec is None:
            raise FileNotFoundError(self._path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def load_filepath(self):
        return self._path

    def __str__(self) -> str:
        return "{} ({})".format(self.module_name, self._path)


class PyModuleInstance(PyBasicModuleLoader):
    """
    ロードずみのインスタンスを操作する
    """
    def get_name(self):
        return self._m.__name__
    
    def load_module(self):
        return self._m

    def load_filepath(self):
        return get_first_package_path(self._m, self._m.__spec__)

    def __str__(self) -> str:
        return "{} ({})".format(self._m.__name__, self.load_filepath())


class AttributeLoader():
    """
    モジュールの要素をロードする
    """
    def __init__(self, module, attr):
        self.attr_name = attr
        self.module = module

    def __call__(self, *, fallback=False):
        if self.module:
            return self.module.load_attr(self.attr_name, fallback=fallback)
        else:
            if not hasattr(builtins, self.attr_name):
                if not fallback:
                    raise ValueError("ビルトインモジュールに'{}'というメンバは存在しません".format(self.attr_name))
                else:
                    return None
            return getattr(builtins, self.attr_name)


def walk_modules(path, package_name=None):
    """
    このパス以下にあるインポート可能なすべてのモジュールを列挙する。
    二重アンダースコア、ドットで始まる名前のファイルは除外する。
    """
    for dirpath, dirnames, filenames in os.walk(path, topdown=True):
        # キャッシュディレクトリを走査しない
        dirnames[:] = [x for x in dirnames if not x.startswith((".", "__"))]
        
        filenames = [x for x in filenames if x.endswith(".py")]
        for filename in filenames:
            if filename.startswith((".", "__")):
                continue
            filepath = os.path.join(dirpath, filename)
            qual_name = module_name_from_path(filepath, path, package_name)
            yield PyModuleLoader(qual_name)


def module_name_from_path(path, basepath, basename=None):
    """
    パスからモジュール名を作る
    """
    if not os.path.isabs(path):
        raise ValueError("Pass an absolute path")
    relpath, _ = os.path.splitext(os.path.relpath(path, basepath))
    if "\\" in relpath:
        relparts = relpath.split("\\")
    else:
        relparts = relpath.split("/")
    name = ".".join(relparts)
    if basename:
        name = basename + "." + name
    return name


def get_first_package_path(module, spec):
    if spec.has_location:
        return spec.origin
    if module and module.__path__:
        # 名前空間パッケージの場合、最初のパスのみを得る
        return next(iter(module.__path__), None)
    return None

#
#
#
class ClassDescriber():
    def __init__(self, resolver):
        self._resolver = resolver
        self._resolved = None

    def get_classname(self):
        return getattr(self.klass, "__name__", None)

    def get_docstring(self):
        return getattr(self.klass, "__doc__", None)
    
    def get_qualname(self):
        return full_qualified_name(self.klass)
    
    def do_describe_object(self, type):
        if hasattr(self.klass, "describe_object"):
            self.klass.describe_object(type) # type: ignore

    @property
    def klass(self):
        if self._resolved is None:
            if isinstance(self._resolver, type):
                self._resolved = self._resolver
            else:
                self._resolved = self._resolver()
        return self._resolved

    def get_attribute(self, name):
        return getattr(self.klass, name, None)

    def enum_attributes(self):
        # 定義順でメソッドを列挙する
        members = []
        
        ranks = {}
        top = 1
        bases = [self.klass]
        while bases:
            kls = bases.pop()
            ranks[full_qualified_name(kls)] = top 
            for base in kls.__bases__:
                if base is not object:
                    bases.append(base)
            top += 1

        for attrname in dir(self.klass):
            if attrname.startswith("__"):
                continue

            attr = getattr(self.klass, attrname, None)
            if attr is None:
                continue
            
            code = getattr(attr, "__code__", None)
            if code is None:
                continue
            
            # クラス名を取り出す
            qual = full_qualified_name(attr)
            if "." in qual:
                klass = qual.rpartition(".")[0]
            else:
                klass = None
            qualkey = ranks.get(klass, 0xFF) # クラスの優先度に変換する
            key = (qualkey, code.co_firstlineno) # 行番号を付加する
            members.append((key, attrname, attr))

        members.sort(key=lambda x:x[0])

        for _key, attrname, attr in members:
            yield attrname, attr



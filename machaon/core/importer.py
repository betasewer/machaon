import importlib
import builtins
import os
import ast

from machaon.core.docstring import parse_doc_declaration

def module_loader(expr, *, location=None):
    if location:
        return PyModuleFileLoader(expr, location)
    else:
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


class PyBasicModuleLoader:
    """
    ローダーの基礎クラス
    """
    def __init__(self):
        self._m = None
    
    @property
    def module(self):
        if self._m is None:
            self._m = self.load_module()
        return self._m
        
    def load_module(self):
        raise NotImplementedError()

    def load_filepath(self):
        raise NotImplementedError()
    
    def load_source(self):
        p = self.load_filepath()
        if not os.path.isfile(p):
            raise ValueError("ファイルではないのでソースコードを取得できません")
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
            yield [os.path.dirname(mod.__file__)]
        else:
            raise ValueError("__path__, __file__属性が無く、ディレクトリを特定できません")
    
    def scan_type_definitions(self):
        """ ソースコードの構文木を解析し、型を定義するクラスの名前を取り出す """
        source = self.load_source()
        disp = str(self)
        tree = compile(source, disp, 'exec', ast.PyCF_ONLY_AST)
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
            
            loader = AttributeLoader(self, classname)

            from machaon.core.type import TypeDefinition
            d = TypeDefinition(loader, classname)
            if not d.load_declaration_docstring(doc):
                continue

            yield d



class PyModuleLoader(PyBasicModuleLoader):
    """
    配置されたモジュールからロードする
    """
    def __init__(self, module):
        super().__init__()
        self.module_name = module
    
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
        if not spec.has_location:
            raise ValueError("モジュールの場所が参照不能です")
        return spec.origin
    
    def load_source(self):
        p = self.load_filepath()
        with open(p, "r", encoding="utf-8") as fi:
            return fi.read()
    
    def __str__(self) -> str:
        return self.module_name


class PyModuleFileLoader(PyBasicModuleLoader):
    """
    ファイルパスを指定してロードする
    """
    def __init__(self, module, path):
        self.module_name = module
        self._path = path
    
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
        return "{}[{}]".format(self.module_name, self._path)


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
            return getattr(builtins, self.attr_name, None)


def walk_modules(path, package_name=None):
    """
    このパス以下にあるすべてのモジュールを列挙する。
    """
    for dirpath, dirnames, filenames in os.walk(path, topdown=True):
        # キャッシュディレクトリを走査しない
        dirnames[:] = [x for x in dirnames if not x.startswith((".", "__"))]
        
        filenames = [x for x in filenames if x.endswith(".py")]
        for filename in filenames:
            if filename in ("__init__.py", "__main__.py"):
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

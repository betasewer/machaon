import importlib
import builtins
import inspect
import pkgutil
import os

#
#
#
def attribute_loader(expr, *, attr=None, location=None):
    if attr is None:
        mod, _, member = expr.rpartition(".")
        if not member:
            member = expr
            mod = None
    else:
        member = attr
        mod = expr
    if location:
        return PyModuleFileAttributeLoader(mod, location, member)
    else:
        return PyModuleAttributeLoader(mod, member)

def module_loader(expr, *, location=None):
    if location:
        return PyModuleFileAttributeLoader(expr, location)
    else:
        return PyModuleAttributeLoader(expr)


class PyAttributeLoader:
    """
    ローダーの基礎クラス
    """
    def __init__(self, member = None):
        self.member_name = member
        self._m = None
    
    @property
    def module(self):
        if self._m is None:
            self._m = self.load_module()
        return self._m
        
    def load_module(self):
        raise NotImplementedError()
    
    def __call__(self, *, fallback=False):
        return self.load_attr(fallback=fallback)
    
    def load_attr(self, name=None, *, fallback=False):
        name = name or self.member_name
        mod = self.module
        loaded = getattr(mod, name, None)
        if loaded is None and not fallback:
            raise ValueError("ターゲット'{}'はモジュール'{}'に存在しません".format(name, mod.__name__))
        return loaded
    
    def load_filepath(self):
        mod = self.module
        basefile = getattr(mod, "__file__", None)
        if basefile is None:
            raise ValueError("モジュールのファイルパスを特定できません")
        return basefile
    
    def enum_type_describers(self):
        """ 型を定義しているクラスをモジュールから列挙する """
        mod = self.module
        for _name, value in inspect.getmembers(mod, inspect.isclass):
            if value.__module__ != mod.__name__: # インポートされた要素を無視する
                continue
            doc = getattr(value, "__doc__", None)
            if doc is None:
                continue
            doc = doc.lstrip()
            if doc.startswith("@type"):
                yield value

class PyModuleAttributeLoader(PyAttributeLoader):
    """
    配置されたモジュールからロードする
    """
    def __init__(self, module, member = None, *, finder = None):
        super().__init__(member)
        self.module_name = module
        self._finder = finder
    
    def load_module(self):
        if self.module_name:
            import sys
            if self.module_name in sys.modules:
                mod = sys.modules[self.module_name]
            else:
                # sys.modulesの扱いを任せたいのでfinderは（今のところ）使わない
                mod = importlib.import_module(self.module_name)
        else:
            mod = builtins
        return mod
    
    def __str__(self) -> str:
        parts= []
        if self.module_name:
            parts.append(self.module_name)
        if self.member_name:
            parts.append(self.member_name)
        return ".".join(parts)

class PyModuleFileAttributeLoader(PyAttributeLoader):
    """
    ファイルパスを指定してロードする
    """
    def __init__(self, module, path, member = None):
        super().__init__(member)
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
        parts= []
        parts.append("{}[{}]".format(self.module_name, self._path))
        if self.member_name:
            parts.append(self.member_name)
        return ".".join(parts)


def walk_modules(path, package_name=None):
    """
    このパス以下にあるすべてのモジュールを列挙する。
    """
    for finder, name, ispkg in pkgutil.iter_modules(path=[path]):
        qual_name = name if not package_name else package_name + "." + name
        if ispkg:
            cp = os.path.join(path, name)
            yield from walk_modules(cp, qual_name)
        else:
            yield PyModuleAttributeLoader(qual_name, finder=finder)

def module_name_from_path(path, basepath, basename=None):
    """
    パスからモジュール名を作る
    """
    relpath, _ = os.path.splitext(os.path.relpath(path, basepath))
    if "\\" in relpath:
        relparts = relpath.split("\\")
    else:
        relparts = relpath.split("/")
    name = ".".join(relparts)
    if basename:
        name = basename + "." + name
    return name

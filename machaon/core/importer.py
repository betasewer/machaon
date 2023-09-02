from typing import List, Tuple

import importlib
import importlib.util
import builtins
import os
import ast
import traceback

from machaon.core.docstring import parse_doc_declaration, get_doc_declaration_type, DocStringDefinition
from machaon.core.symbol import full_qualified_name
from machaon.core.error import ErrorSet

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

def load_attribute_value(expr, **kwargs):
    loader = attribute_loader(expr, **kwargs)
    entrypoint = loader()
    if callable(entrypoint):
        return entrypoint()
    else:
        return entrypoint

def module_loader_from_file(path, namebasepath):
    name = module_name_from_path(path, namebasepath)
    return PyModuleFileLoader(name, path)


class PyBasicModuleLoader:
    """
    ローダーの基礎クラス
    """
    def __init__(self, m=None): # モジュールのインスタンスを受ける
        self._m = m
        self._moduledoc = None
    
    @property
    def module(self):
        if self._m is None:
            self._m = self.load_module()
        return self._m

    def exists(self):
        raise NotImplementedError()

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
        raise NotImplementedError()
    
    #
    #
    #
    def is_module_document_loaded(self):
        """ 構文木がロード済み """
        return self._moduledoc is not None
    
    def load_module_declaration(self):
        """ 
        ソースコードの構文木からモジュールのドキュメント文字列を取り出し、解析する 
        """
        if self.is_module_document_loaded():
            return
        self._moduledoc = ModuleDocDefinition(self)
        self._moduledoc.load_declaration()
        
    def get_package_extra_requirements(self):
        """ 追加の依存するmachaonパッケージ名 """
        return self._moduledoc.required_packages

    def get_package_defmodule_loaders(self):
        """ このパッケージ中にて型定義が含まれるモジュールを明示する """
        return self._moduledoc.defined_modules

    def get_using_extra_packages(self) -> List[Tuple[str, str]]:
        """ このモジュールが依存する外部パッケージ """
        return self._moduledoc.using_packages

    def scan_type_describers(self):
        """ ソースコードの構文木を解析し、型を定義するクラスを取り出す
        Yields:
            TypeDescriber: 定義オブジェクト
        """
        # モジュールのドキュメント文字を読み込む
        self.load_module_declaration()

        # モジュールに定義されたクラスのドキュメント文字列を全て読んでいく
        for describer in self._moduledoc.scan_describers():
            yield describer

        # 外部型
        for d in self._moduledoc.using_types:
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
            for typedesc in self.scan_type_describers():
                typename = typedesc.get_typename()
                qualname = typedesc.get_full_qualname()
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

    def get_all_submodule_loaders(self):
        """ 全てのサブモジュールのローダーを作成する
        Returns:
            List[PyBasicModuleLoader]:
        """
        modules = []
        basepkg = self.get_name()
        for pkgpath in self.load_package_directories(): # 開始モジュールのディレクトリから下降する
            # 再帰を避けるためにスタック上にあるソースファイルパスを調べる
            skip_names = []
            for fr in traceback.extract_stack():
                fname = os.path.normpath(fr.filename)
                if fname.startswith(pkgpath):
                    relname = module_name_from_path(fname, pkgpath, basepkg)
                    skip_names.append(relname)
            
            # サブモジュールを取得する
            for loader in walk_modules(pkgpath, basepkg):
                if loader.module_name in skip_names:
                    continue 
                modules.append(loader)

        return modules

    def load_all_module_loaders(self):
        """ このモジュールとサブモジュール全てのローダーを返す """
        modules = [self]
        self.load_module_declaration()

        defmods = self.get_package_defmodule_loaders()
        if defmods:
            modules.extend(defmods)
        elif self.is_package():
            modules.extend(self.get_all_submodule_loaders())
        
        with ErrorSet("サブモジュールの宣言を解析中") as errs:
            for mod in modules:
                errs.try_(mod.load_module_declaration)

        return modules
    
    def load_all_describers(self):
        """ このモジュールにある全ての型定義を抽出する """
        # 依存パッケージをチェックする
        notfound_depends = []
        for name in self.get_using_extra_packages():
            if not module_loader(name).exists():
                notfound_depends.append(name)
        if notfound_depends:
            raise ValueError("依存パッケージ{}が見つかりません".format(",".join(notfound_depends)))
    
        # 型定義を抽出するだけ
        for typedesc in self.scan_type_describers():
            yield typedesc
    
    def show_latest_files(self, app, full=False):
        """ @task
        パッケージ内のファイルをタイムスタンプ順に表示する。
        """
        filepaths = []
        try:
            thispath = self.load_filepath()
        except Exception as e:
            app.post("message", e)
            return
        if thispath:
            filepaths.append(thispath)
        
        try:
            pkgdirs = self.load_package_directories()
        except Exception as e:
            app.post("message", e)
            return
        for pkgdir in pkgdirs:
            for dirpath, dirnames, filenames in os.walk(pkgdir, topdown=True):
                # キャッシュディレクトリを走査しない
                dirnames[:] = [x for x in dirnames if not x.startswith((".", "__"))]
                for filename in filenames:
                    if filename.startswith((".","__")):
                        continue
                    fp = os.path.join(dirpath, filename)
                    filepaths.append(fp)

        import datetime
        import bisect
        buckets = []
        for fp in filepaths:
            if not os.path.isfile(fp):
                continue
            ts = datetime.datetime.fromtimestamp(os.stat(fp).st_mtime)
            for bucket in buckets:
                if bucket[0][0] <= ts and ts <= bucket[-1][0]:
                    bisect.insort(bucket, (ts, fp))
                    break
                elif (bucket[0][0] - ts).seconds < 60:
                    bucket.insert(0, (ts, fp))
                    break
                elif (ts - bucket[-1][0]).seconds < 60:
                    bucket.append((ts, fp))
                    break
            else:
                buckets.append([(ts, fp)])
                
        li = sorted(buckets, reverse=True, key=lambda x:x[0][0])
        for i, bucket in enumerate(li):
            t1 = bucket[0][0].strftime("%Y-%m-%d %H:%M:%S")
            t2 = bucket[-1][0].strftime("%Y-%m-%d %H:%M:%S")
            if t1 == t2:
                tx = t1
            else:
                tx = t1 + "~" + t2
            app.post("message", "[{}更新]".format(tx))
            if not full and i == len(li)-1:
                app.post("message", "  {}個のファイル".format(len(bucket)))
            else:
                for ts, fp in bucket:
                    app.post("message", "  {}".format(fp))
                
    def is_package(self):
        """ パッケージかどうか判定する """
        return self.module.__spec__.submodule_search_locations is not None


class ModuleDocDefinition:
    """ モジュールのドキュメントを解析する """
    def __init__(self, module: PyBasicModuleLoader):
        source = module.load_source()
        if source is None:
            return
        disp = str(self)
        tree = compile(source, disp, 'exec', ast.PyCF_ONLY_AST)
        #
        self._module = module
        self._ast = tree
        self.required_packages = []
        self.defined_modules = []
        self.using_types = []
        self.using_packages = []
        
    def load_declaration(self):
        """ 宣言部を解析する """
        doc = ast.get_docstring(self._ast)
        if not doc:
            return

        decl = parse_doc_declaration(doc, ("module",))
        if decl is None:
            return
        
        defs = DocStringDefinition.parse(decl, (
            "Extra-Requirements Extra-Req",
            "TypedefModules DefModules",
            "UsingType",
            "UsingPackage",
        ))
        # 追加の依存するmachaonパッケージ名
        for name in defs.get_string("Extra-Requirements").split(","):
            package_name = name.strip()
            if package_name:
                self.required_packages.append(package_name)
        
        # パッケージで、型定義が含まれるモジュールを明示する
        for line in defs.get_lines("TypedefModules"):
            module_name = line.strip()
            if module_name:
                m = module_loader(module_name)
                self.defined_modules.append(m)

        # 参照する外部のmachaon型
        for line in defs.get_lines("UsingType"):
            fulltypename = line.strip()
            from machaon.core.type.describer import create_type_describer
            d = create_type_describer(fulltypename)
            if d.is_typedef():
                self.using_types.append(d)
            
        # 参照する外部のパッケージ
        for line in defs.get_lines("UsingPackage"):
            packagename, sep, libname = line.partition(":")
            if sep:
                entry = (packagename.strip(), libname.strip())
            else:
                libname = line.strip()
                entry = (libname, libname)
            self.using_packages.append(entry)

    def scan_describers(self):
        """
        モジュールに定義されたクラスのドキュメント文字列を全て読み、machaon型のデスクライバを抽出する
        """
        from machaon.core.type.describer import TypeDescriberClass, create_type_describer
        for node in ast.iter_child_nodes(self._ast):
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

            atloader = AttributeLoader(self._module, classname)
            desc = create_type_describer(TypeDescriberClass(atloader, doc))
            if not desc.is_valid():
                continue
            yield desc

#
#
#
class PyModuleLoader(PyBasicModuleLoader):
    """
    配置されたモジュールからロードする
    """
    def __init__(self, module, filepath=None):
        super().__init__()
        self.module_name = module
        self.filepath = filepath
    
    def get_name(self):
        return self.module_name

    def exists(self):
        try:
            spec = importlib.util.find_spec(self.module_name)
            return spec is not None
        except:
            return False

    def load_module(self):
        import sys
        if self.module_name in sys.modules:
            mod = sys.modules[self.module_name]
        else:
            # sys.modulesの扱いを任せる
            mod = importlib.import_module(self.module_name)
        return mod
    
    def load_filepath(self):
        if self.filepath is not None:
            return self.filepath
        spec = importlib.util.find_spec(self.module_name)
        if spec is None:
            raise ValueError("モジュールが見つかりません")
        return get_first_package_path(self._m, spec)

    def load_package_directories(self):
        spec = importlib.util.find_spec(self.module_name)
        if spec is None:
            raise ValueError("モジュールが見つかりません")
        if spec.submodule_search_locations is not None:
            for path in spec.submodule_search_locations:
                yield path
        elif spec.has_location:
            yield os.path.dirname(spec.origin)
        else:
            raise ValueError("ModuleSpecにsubmodule_search_locations, origin属性が無く、ディレクトリを特定できません")
    
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
    
    def exists(self):
        return os.path.isfile(self._path)

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

    def exists(self):
        return True
    
    def load_module(self):
        return self._m

    def load_filepath(self):
        return get_first_package_path(self._m, self._m.__spec__)

    def load_package_directories(self):
        if getattr(self._m, "__path__", None) is not None:
            for path in self._m.__path__:
                yield path
        elif getattr(self._m, "__file__", None) is not None:
            yield os.path.dirname(self._m.__file__)
        else:
            raise ValueError("__path__, __file__属性が無く、ディレクトリを特定できません")
    
    def __str__(self) -> str:
        return "{} ({})".format(self._m.__name__, self.load_filepath())


class AttributeLoader:
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

    def get_name(self):
        return self.attr_name

    def get_qualname(self):
        return "{}.{}".format(self.module.get_name(), self.attr_name)


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
            yield PyModuleLoader(qual_name, filepath) # FileModuleLoaderを使うと、import文で読み込んだ同一モジュールとは別のインスタンスになってしまう


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
    if module and getattr(module, "__path__", None) is not None:
        # 名前空間パッケージの場合、最初のパスのみを得る
        return next(iter(module.__path__), None)
    return None

#
#
#
def enum_attributes(value_type, value):
    """
    定義順でメソッドを列挙する
    Yields:
        Tuple[str, Any | Exception]:
    """
    ranks = {}
    top = 1
    bases = [value_type]
    while bases:
        kls = bases.pop()
        ranks[full_qualified_name(kls)] = top 
        for base in kls.__bases__:
            if base is not object:
                bases.append(base)
        top += 1

    members = []
    nocodemembers = []
    for attrname in dir(value):
        if attrname.startswith("__"):
            continue
        
        try:
            attr = getattr(value, attrname, None)
        except Exception as e:
            attr = e
        if attr is None:
            continue

        fn = attr
        
        code = getattr(fn, "__code__", None)
        if code is None:
            nocodemembers.append((attrname, attr))
            continue
        
        # クラス名を取り出す
        qual = full_qualified_name(fn, fallback=True)
        if qual and "." in qual:
            klass = qual.rpartition(".")[0]
        else:
            klass = None
        qualkey = ranks.get(klass, 0xFF) # クラスの優先度に変換する
        key = (qualkey, code.co_firstlineno) # 行番号を付加する
        members.append((key, attrname, attr))

    members.sort(key=lambda x:x[0])
    for _key, attrname, attr in members:
        yield attrname, attr

    for attrname, attr in nocodemembers:
        yield attrname, attr


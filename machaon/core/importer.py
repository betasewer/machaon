import importlib
import importlib.util
import builtins
import os

from machaon.core.symbol import full_qualified_name

def module_loader(expr=None, *, location=None):
    if location:
        if expr is None:
            expr = location
        return PyModuleFile(expr, location)
    else:
        if expr is None:
            raise TypeError("'expr' must not be None")
        return PyModule(expr)

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
    return PyModuleFile(name, path)

class BasicModule:
    """
    モジュールのベースクラス
    """
    def __init__(self, m=None): # モジュールのインスタンスを受ける
        self._m = m

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
        if p is None or not os.path.isfile(p):
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

    def show_latest_files(self, full=False, *, printer=None):
        """ @task
        パッケージ内のファイルをタイムスタンプ順に表示する。
        """
        printer = printer or print

        filepaths = []
        try:
            thispath = self.load_filepath()
        except Exception as e:
            printer("message", e)
            return
        if thispath:
            filepaths.append(thispath)
        
        try:
            pkgdirs = self.load_package_directories()
        except Exception as e:
            printer("message", e)
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
            printer("message", "[{}更新]".format(tx))
            if not full and i == len(li)-1:
                printer("message", "  {}個のファイル".format(len(bucket)))
            else:
                for ts, fp in bucket:
                    printer("message", "  {}".format(fp))

    def is_package(self):
        """ パッケージかどうか判定する """
        return self.module.__spec__.submodule_search_locations is not None

#
#
#
class PyModule(BasicModule):
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


class PyModuleFile(BasicModule):
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


class PyModuleInstance(BasicModule):
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
            yield PyModule(qual_name, filepath) # FileModuleLoaderを使うと、import文で読み込んだ同一モジュールとは別のインスタンスになってしまう


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
def enum_attributes(value_type, value=None):
    """
    定義順でメソッドを列挙する
    Yields:
        Tuple[str, Any | Exception]:
    """
    if value is None:
        value = value_type
        value_type = type(value)

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


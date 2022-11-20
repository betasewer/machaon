import os
import shutil
import stat
import datetime
from collections import defaultdict

from machaon.shellpopen import popen_capture
from machaon.platforms import shellpath


def _normext(extension):
    if not extension.startswith("."):
        return "." + extension
    return extension

# Path new known-location-names
#
#
class Path:
    """ @type
    ファイル・フォルダのパス。
    コンストラクタ＝
    パス、または場所の名前を受ける。
    使用できる場所の名前の一覧は、known-names。
    """
    def __init__(self, path=None):
        self._path = os.fspath(path) if path else ""
        self._stat = None
    
    def __str__(self):
        return self._path
        
    def __repr__(self):
        return "<maca.Path {}>".format(self._path)
    
    def __fspath__(self):
        return self._path
    
    def get(self):
        return self._path
    
    def set(self, p):
        self._path = p
        return self
    
    @property
    def normpath(self):
        return os.path.normpath(self._path)
    
    @property
    def stat(self):
        if self._stat is None:
            self._stat = os.stat(self._path)
        return self._stat
        
    #
    #
    #
    def known_names(self, spirit):
        """ @method spirit
        場所の名前のリスト。
        Returns:
            Sheet[ObjectCollection](name, path):
        """
        res = []
        for k, v in shellpath().known_paths(spirit.get_root()):
            if v is not None:
                res.append({"name":k, "path":Path(v)})
        return res

    #
    # 要素を調査する
    #
    def path(self):
        """ @method
        パスの文字列
        Returns:
            Str:
        """
        return self._path

    def name(self):
        """ @method
        ファイル・フォルダ名
        Returns:
            Str:
        """
        return os.path.basename(self._path)
    
    def basename(self):
        """ @method [stem]
        拡張子なしのファイル名
        Returns:
            Str:
        """
        n, _ext = os.path.splitext(os.path.basename(self._path))
        return n
    
    def extension(self):
        """ @method
        ドットを含む拡張子。
        Returns:
            Str:
        """
        _n, ext = os.path.splitext(self._path)
        return ext
    
    def filetype(self):
        """ @method
        ファイルタイプ名（フォルダまたは拡張子）
        Returns:
            Str:
        """
        if self.isdir():
            return "<DIR>"
        else:
            return self.extension().lstrip(".")
    
    def hasext(self, names):
        """ @method
        いずれかの拡張子を持っているか
        Params:
            names(Tuple):
        Returns:
            Bool:
        """
        if self.isdir():
            return False
        if isinstance(names, str):
            names = [names]
        ext = self.extension().lstrip(".")
        for name in names:
            if ext == name.lstrip("."):
                return True
        return False
    
    def isdir(self):
        """ @method
        フォルダのパスかどうか
        Returns:
            Bool:
        """
        return os.path.isdir(self._path)
    
    def isfile(self):
        """ @method
        ファイルのパスかどうか
        Returns:
            Bool:
        """
        return os.path.isfile(self._path)
    
    def ishidden(self):
        """ @method
        隠しファイルかどうか
        ファイル名がピリオドで始まるか、隠し属性がついているか
        Returns:
            Bool:
        """
        if self.name().startswith("."):
            return True
        if shellpath().has_hidden_attribute(self._path):
            return True
        return False
    
    def exists(self):
        """ @method
        ファイル・フォルダとして存在するか
        Returns:
            Bool:
        """
        return os.path.exists(self._path)
    
    def track(self):
        """
        全ての構成要素を下から順に返す。
        Yields:
            Str:
        """
        names = []
        p = self._path
        while len(names) < 256:
            up, basename = os.path.split(p)
            if basename:
                yield basename
            if not up:
                return
            elif p == up:
                yield up
                return
            p = up
        raise ValueError("パス深度の限界値に到達しました")

    def split(self):
        """ @method
        全ての構成要素を分割して返す。
        Returns:
            Tuple[Str]:
        """
        names = list(self.track())
        names.reverse()
        return names

    #
    # ファイル属性
    #
    def device(self):
        """ @method
        ファイルが存在するデバイス名
        Returns:
            Str:
        """
        return self.stat.st_dev

    def link_count(self):
        """ @method
        ハードリンクの数
        Returns:
            Int:
        """
        return self.stat.st_nlink

    def modtime(self):
        """ @method [mtime]
        変更日時。
        Returns:
            Datetime:
        """
        return datetime.datetime.fromtimestamp(self.stat.st_mtime)
    
    def accesstime(self):
        """ @method [atime]
        アクセス日時。
        Returns:
            Datetime:
        """
        return datetime.datetime.fromtimestamp(self.stat.st_atime)
    
    def creationtime(self):
        """ @method [ctime]
        作成日時／メタデータ変更日時
        Returns:
            Datetime:
        """
        return datetime.datetime.fromtimestamp(self.stat.st_ctime)
    
    def size(self):
        """ @method
        ファイルサイズ
        Returns:
            Int:
        """
        if self.isdir():
            return None
        return os.path.getsize(self._path)
        #if size_bytes == 0:
        #    return "0B"
        #i = int(math.floor(math.log(size_bytes, 1024)))
        #p = math.pow(1024, i)
        #s = round(size_bytes / p, 2)
        #size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        #return "{:.0F} {}".format(s, size_name[i])
    
    def mode(self):
        """ @method
        ファイルモードを示す文字列
        Returns:
            Str:
        """
        return stat.filemode(self.stat.st_mode)

    def inode(self):
        """ @method
        ファイルのinodeまたはインデックス
        Returns:
            Int:
        """
        return self.stat.st_ino
        
    #
    # パス操作
    #
    def dir(self):
        """ @method
        ファイルならそのディレクトリを返す。ディレクトリはそのまま。
        Returns:
            Path:
        """
        if self.isfile():
            return self.up()
        return self

    def up(self):
        """ @method
        一つ上のディレクトリを返す。
        Returns:
            Path:
        """
        up, _basename = os.path.split(self._path)
        return Path(up)

    def shift(self):
        """ @method
        トップ要素をパスから取り除く。 
        Returns:
            Path:
        """
        elements = self.split()
        elements.pop(0)
        return Path(os.path.join(*elements))

    def append(self, path):
        """ @method
        パスを付け足す。
        Params:
            path(Path):
        Returns:
            Path:
        """
        p = os.path.join(self._path, path._path)
        return Path(p)
    
    def with_name(self, name):
        """ @method
        ファイル・ディレクトリ名だけ変更する。
        Params:
            name(str):
        Returns:
            Path:
        """
        up, _basename = os.path.split(self._path)
        return Path(os.path.join(up, name))
    
    def with_ext(self, extension):
        """ @method
        拡張子だけ変更する。
        Params:
            extension(str):
        Returns:
            Path:
        """
        up, _ext = os.path.splitext(self._path)
        extension = _normext(extension)
        return Path(up + extension)
    
    def without_ext(self):
        """ @method
        拡張子を取り除いたフルパス。
        Returns:
            Path:
        """
        up, _ext = os.path.splitext(self._path)
        return Path(up)
    
    def with_name_format(self, format, *args):
        """ 
        書式に基づいて名前を変更する。（内部利用）
        {0}に元のnameが入る。
        """
        head, name = os.path.split(self._path)
        newpath = os.path.join(head, format.format(name, *args))
        return Path(newpath)
    
    def with_basename_format(self, format, *args, ext=None):
        """ 
        書式に基づいて拡張子を除く名前を変更する。（内部利用）
        {0}に元のbasenameが入る。
        """
        head, name = os.path.split(self._path)
        basename, fext = os.path.splitext(name)
        if ext is not None:
            fext = _normext(ext)
        newpath = os.path.join(head, format.format(basename, *args) + fext)
        return Path(newpath)

    def join(self, *paths):
        """ パスを結合する """
        ps = [self._path] + [os.fspath(x) for x in paths]
        ps = [x for x in ps if x]
        if ps:
            return Path(os.path.join(*ps))
        else:
            return Path()

    def relative_to(self, base):
        """ @method
        引数のパスに対する相対パスを返す。
        Params:
            base(Path):
        Returns:
            Path:
        """
        return Path(os.path.relpath(self._path, start=base))

    def is_relative_to(self, base):
        """ @method
        引数のパスに対して相対かどうかを返す。
        Params:
            base(Path):
        Returns:
            bool:
        """
        try:
            p = os.path.relpath(self._path, start=base)
            return not Path(p).is_redundant()
        except ValueError:
            return False # Windowsでドライブが異なる場合

    def is_redundant(self):
        """ @method
        '.'または'..'が含まれているか。
        Returns:
            bool:
        """
        for elem in self.split():
            if elem == "." or elem == "..":
                return True
        return False

    def new_increment(self, suffixformat=None, start=1):
        """ @method
        存在しないパスになるまで、元のパスにサフィックスを付して新たに生成する。
        Params:
            suffixformat?(str): サフィックスの書式文字列
            start?(int): 開始の数字
        Returns:
            Path:
        """
        if not self.exists():
            return self
        
        suffixformat = suffixformat or "_{}"
        up, name = os.path.split(self._path)
        basename, ext = os.path.splitext(name)
        for alt in range(start, 10000):
            altname = basename + suffixformat.format(alt) + ext
            newpath = os.path.join(up, altname)
            if not os.path.exists(newpath): # 既に存在する
                return Path(newpath)
        else:
            raise ValueError("Too many same name dir: {}".format(self._path)) 

    def new_random_name(self, width=8):
        """ @method
        存在しないパスになるまで、元のパスにランダムな英数字の連続を付して生成する。
        Params:
            width?(int): 新たな名前の文字数
        Returns:
            Path:
        """
        import random
        import string
        wd = len(string.digits)
        wl = len(string.ascii_lowercase)
        puncts = "_-=[]"
        wp = len(puncts)

        def pickchar():
            index = random.randrange(0,wd+wl+wp)
            if index < wd:
                return string.digits[index]
            index -= wd
            if index < wl:
                return string.ascii_lowercase[index]
            index -= wl
            return puncts[index]

        #
        for alt in range(0, 100):
            suffix = "".join(pickchar() for _ in range(width))
            newpath = self.with_basename_format("{}{}", suffix)
            if not newpath.exists(): # 存在しない新しい名
                return newpath
        else:
            raise ValueError("Too many same name dir: {}".format(self._path)) 
            
    def is_same(self, right):
        """ @method
        同じファイルまたはディレクトリを指しているか。
        Params:
            right(Path):
        Returns:
            bool:
        """
        return os.path.samefile(self.get(), right.get())


    #
    # パス調査
    #
    def listdir(self):
        """ @method [ls]
        ディレクトリに含まれるファイルとサブディレクトリの一覧を返す。
        Returns:
            Sheet[Path](name, filetype, modtime, size):
        """
        return [x for x in self.listdirall() if x.exists() and not x.ishidden()]
    
    def listdirdir(self):
        """ @method [lsd]
        ディレクトリに含まれるサブディレクトリの一覧を返す。
        Returns:
            Sheet[Path](name, filetype, modtime, size):
        """
        if not self.isdir():
            return []
        return [x for x in self.listdir() if x.isdir()]
    
    def listdirfile(self):
        """ @method [lsf]
        ディレクトリに含まれるファイルの一覧を返す。
        Returns:
            Sheet[Path](name, filetype, modtime, size):
        """
        if not self.isdir():
            return []
        return [x for x in self.listdir() if x.isfile()]
    
    def listdirall(self):
        """ @method [lsa]
        隠しファイルも含めた全てのファイルとサブディレクトリの一覧を返す。
        Returns:
            Sheet[Path](name, filetype, modtime, size):
        """
        if not self.isdir():
            return []
        items = [Path(os.path.join(self._path,x)) for x in os.listdir(self._path)]
        return items

    def walkfile(self):
        """ @method
        サブディレクトリのファイルを再帰的に辿る。
        Returns:
            Sheet[Path](name, filetype, modtime, size):
        """
        for dirpath, dirnames, filenames in os.walk(self._path):
            for filename in filenames:
                yield Path(os.path.join(dirpath, filename))
    
    def walkdir(self):
        """ @method
        サブディレクトリを再帰的に辿る。
        Returns:
            Sheet[Path](name, filetype, modtime, size):
        """
        for dirpath, dirnames, filenames in os.walk(self._path):
            for dirname in dirnames:
                yield Path(os.path.join(dirpath, dirname))
    
    def dialog(self):
        """ @method [dlg]
        ファイル・フォルダダイアログを開く。
        Returns:
            PathDialog:
        """
        return self
    
    def search(self, context, app, predicate, depth=3):
        """ @task context
        ファイルを再帰的に検索する。
        Params:
            predicate(Function[](seq)): 述語関数
            depth?(int): 探索する階層の限界
        Returns:
            Sheet[Path](name, extension, modtime, size):
        """
        predicate.set_subject_type("Path")
        basedir = self.dir().path()
        for dirpath, dirname, filenames in os.walk(basedir):
            for filename in filenames:
                filepath = os.path.join(basedir, dirpath, filename)
                if predicate(filepath):
                    yield filepath
    
    def makedirs(self):
        """ @method
        パスが存在しない場合、ディレクトリとして作成する。途中のパスも作成する。
        """
        if self.isfile():
            raise ValueError("パスは既にファイルとして存在しています")
        os.makedirs(self.normpath, exist_ok=True)
        return self
    
    def isemptydir(self):
        """ @task nospirit
        空のフォルダか調べる（隠しフォルダ含む）
        Returns:
            bool:
        """
        return len(self.listdirall()) == 0
    
    #
    # コピー・移動・削除
    #
    def move(self, dest, *, overwrite=False):
        """ @method
        このパスにファイルを移動する。
        Params:
            dest(Path): 移動先のパス
        Returns:
            Path: 移動されたファイルパス
        """
        if not overwrite and dest.exists():
            raise ValueError("すでに同名ファイルが宛先に存在しています")
        p = shutil.move(self.get(), dest.get())
        return Path(p)
    
    def move_to(self, d, *, overwrite=False):
        """ @method
        別のディレクトリにこのファイルを移動する。
        Params:
            d(Path): 宛先ディレクトリ
        Returns:
            Path: コピーされたファイルパス
        """
        dest = d.dir() / self.name()
        if not overwrite and dest.exists():
            raise ValueError("すでに同名ファイルが宛先に存在しています")
        p = shutil.move(self.get(), dest.get())
        return Path(p)
    
    def move_from(self, p, *, overwrite=False):
        """ @method
        このディレクトリにファイルを移動する。
        Params:
            p(Path): 移動するファイル
        Returns:
            Path: コピーされたファイルパス
        """
        dest = self.dir() / p.name()
        if not overwrite and dest.exists():
            raise ValueError("すでに同名ファイルが宛先に存在しています")
        p = shutil.move(p.get(), dest.get())
        return Path(p)

    def copy(self, dest, *, overwrite=False):
        """ @method
        このパスにファイルをコピーする。
        Params:
            dest(Path): コピー先のパス
        Returns:
            Path: コピーされたファイルパス
        """
        if not overwrite and dest.exists():
            raise ValueError("すでに同名ファイルが宛先に存在しています")
        p = shutil.copy(self.get(), dest.get())
        return Path(p)
    
    def copy_to(self, d, name=None, *, overwrite=False):
        """ @method
        このディレクトリにファイルをコピーする。
        Params:
            d(Path): コピー先のディレクトリ
        Returns:
            Path: コピーされたファイルパス
        """ 
        dest = d.dir() / (name or self.name())
        if not overwrite and dest.exists():
            raise ValueError("すでに同名ファイルが宛先に存在しています")
        p = shutil.copy(self.get(), dest.get())
        return Path(p)
    
    def copy_from(self, p, *, overwrite=False):
        """ @method
        このディレクトリにファイルをコピーする。
        Params:
            p(Path): コピーするファイル
        Returns:
            Path: コピーされたファイルパス
        """ 
        dest = self.dir() / p.name()
        if not overwrite and dest.exists():
            raise ValueError("すでに同名ファイルが宛先に存在しています")
        p = shutil.copy(p.get(), dest.get())
        return Path(p)
    
    def remove(self):
        """ @method
        このパスを削除する。
        """
        if self.isfile():
            os.remove(self._path)
        elif self.isdir():
            os.rmdir(self._path) # 空のディレクトリのみ

    def rmtree(self):
        """
        ディレクトリを削除する。
        コマンドの際は確認を行う
        """
        if self.isdir():
            shutil.rmtree(self._path)

    #
    # 実行・シェル機能
    #
    def run_command(self, app, *params):
        """ @task
        ファイルを実行し、終わるまで待つ。入出力をキャプチャする。
        Params:
            *params(Any): コマンド引数
        """
        if self.isdir():
            raise ValueError("ディレクトリは実行できません")
        pa = [self.normpath, *params]
        run_command_capturing(app, pa)

    def do_external(self, context, app):
        """ @task context [doex do-ex]
        メッセージを記述したファイルのパスとして評価し、実行して返す。
        Returns:
            Object: 返り値
        """
        o = context.new_object(self, type="Stored")
        ret = o.value.do(context, app)  
        return ret

    def start(self, operation=None):
        """ @method [open]
        ファイル・フォルダをデフォルトの方法で開く。
        Params:
            operation(str): *動作のカテゴリ。[open|print|edit|explore|find|...]
        """
        shellpath().start_file(self._path, operation)
    
    def explore(self):
        """ @method
        ファイル・フォルダをエクスプローラで開く。
        """
        p = self.dir()
        shellpath().start_file(p._path, "explore")

    def print(self):
        """ @method
        ファイル・フォルダを印刷する。
        """
        if self.isdir():
            raise ValueError("Unsupported")
        shellpath().start_file(self._path, "print")

    def touch(self):
        """ @method
        空ファイルを作成する。
        """
        if self.exists():
            raise ValueError("ファイルは既に存在します")
        with open(self._path, "wb") as fo:
            fo.write(bytes())
    
    #
    # 型の振る舞い
    #
    def __truediv__(self, right):
        """ パスの結合 """
        return self.join(right)
    
    @classmethod
    def known(self, value, approot=None, context=None):
        """ 場所の名前からパスを得る """
        if value == "here" and context:
            p = context.get_herepath()
        elif value == "machaon" and approot:
            p = approot.get_basic_dir()
        elif value == "store" and approot:
            p = os.path.join(approot.get_basic_dir(), "store")
        else:
            name, _, param  = value.partition(":")
            p = shellpath().get_known_path(name, param, approot)
        if p is not None:
            return Path(p)
        return None

    def constructor(self, context, value):
        """ @meta context
        Params:
            Any:
        """
        if isinstance(value, str) and value:
            head, tail = os.path.split(value)
            if not head: # no slash in path
                # 場所の識別名として解釈
                p = Path.known(value, context.spirit.get_root(), context)
                if p is not None:
                    return p
            # 識別名が存在しなければパスとする
        else:
            pass
        return Path(value)
    
    def stringify(self):
        """ @meta """
        return self._path   

class PathDialog:
    """ @type
    パスを選択するダイアログ。
    """
    def __init__(self, p):
        self.p = p
        self._filter = None
    
    def file(self, app):
        """ @method spirit
        一つのファイルを選択する。
        Returns:
            Path:
        """
        p = app.open_pathdialog("f", self.p.dir(), filters=self._filter)
        return p

    def files(self, app):
        """ @method spirit
        複数のファイルを選択する。
        Returns:
            Tuple:
        """
        p = app.open_pathdialog("f", self.p.dir(), filters=self._filter, multiple=True)
        return p

    def dir(self, app):
        """ @method spirit
        一つのディレクトリを選択する。
        Returns:
            Path:
        """
        p = app.open_pathdialog("d", self.p.dir())
        return p

    def dirs(self, app):
        """ @method spirit
        複数のディレクトリを選択する。
        Returns:
            Tuple:
        """
        p = app.open_pathdialog("d", self.p.dir(), multiple=True)
        return p
    
    def save(self, app):
        """ @method spirit
        保存するファイルの場所を選択する。
        Returns:
            Path:
        """
        p = app.open_pathdialog("s", self.p.dir())
        return p

class TextPath:
    """ @type
    テキストファイル内のある場所を示す位置情報。
    パス、行番号、カラム番号。
    """
    def __init__(self, filepath, line=None, column=None) -> None:
        """
        Params:
            filepath(Path):
            line(int):
            column(int):
        """
        self._path = filepath
        self._line = line
        self._column = column
    
    def get_path(self):
        """ @method alias-name [path]
        ファイルパス。
        Returns:
            Path:
        """
        return self._path
    
    def get_line(self):
        """ @method alias-name [line]
        行番号。
        Returns:
            Int:
        """
        return self._line
    
    def get_column(self):
        """ @method alias-name [column]
        カラム番号。
        Returns:
            Int:
        """
        return self._column
    
    def open(self, context):
        """ @method context
        設定されたテキストエディタで開く。
        """
        context.root.open_by_text_editor(self._path.get(), self._line, self._column)

    def constructor(self, value):
        """ @meta 
        Params:
            Path|Tuple[Path, Str]
        """
        path = None
        line = None
        column = None
        if isinstance(value, tuple):
            path, line, column, *_ = (value + (None, None))
        else:
            path = value
        
        return TextPath(path, line, column)
    
    def stringify(self):
        """ @meta """
        parts = []
        parts.append('"{}"'.format(self._path))
        if self._line is not None:
            parts.append("line {}".format(self._line))
        if self._column is not None:
            parts.append("column {}".format(self._column))
        return ", ".join(parts)


class PlatformPath(shellpath().PlatformPath):
    """ @type mixin
    プラットフォーム独自のパス機能を提供するミキシン
    MixinType:
        Path:
    """

#
#
#
class TemporaryDirectory():
    """  
    exit時に削除される一時ディレクトリ
    """
    def __init__(self, *, ignore_cleanup_errors=False):
        self.dir = None
        self._ignerror = ignore_cleanup_errors

    def make(self):
        import tempfile
        return Path(tempfile.mkdtemp())

    def deletes(self, d):
        shutil.rmtree(d)

    def prepare(self):
        if self.dir is None:
            self.dir = self.make()
    
    def cleanup(self):
        if self.dir is not None:
            self.deletes(self.dir)
            self.dir = None
    
    def get(self):
        if self.dir is None:
            raise ValueError("not prepared")
        return self.dir.get()
    
    def path(self):
        return self.dir

    def __fspath__(self):
        return os.fspath(self.dir)

    def __enter__(self):
        self.prepare()
        return self

    def __exit__(self, et, ev, tb):
        try:
            self.cleanup()
        except:
            if self._ignerror:
                pass
            else:
                raise

    #
    #
    #
    def writefile(self, bits, ext=None, prefix="tmp"):
        """ パスを参照可能な一時ファイルを作成 """
        p = (self.dir / prefix).new_random_name()
        if ext:
            p = p.with_ext(ext)
        with open(p, "wb") as fo:
            fo.write(bits)
        return p


class UserTemporaryDirectory(TemporaryDirectory):
    def __init__(self, root, **kwargs):
        self.root = root
        super().__init__(**kwargs)
    
    def make(self):
        return (self.root / "temp").new_random_name().makedirs()
    
    def deletes(self, d):
        shutil.rmtree(d)
        


# 
#
#
def run_command_capturing(app, params):
    """ 
    プロセスを実行しつつ出力をキャプチャする 
    Params:
        app(Spirit):
        params(Sequence[str]): 引数リスト
    TODO:
        入力に未対応
    """
    proc = popen_capture(params)
    for msg in proc:
        if msg.is_waiting_input():
            if not app.interruption_point(noexception=True):
                msg.send_kill(proc)
                app.post("warn", "実行中のプロセスを強制終了しました")
                app.raise_interruption()
            continue
            #inp = spi.get_input()
            #if inp == 'q':
            #    msg.end_input(proc)
            #elif inp:
            #    msg.send_input(proc, inp)
            #else:
            #    msg.skip_input(proc)
        
        if msg.is_output():
            app.post("message", msg.text)
        
        if msg.is_finished():
            app.post("message-em", "プロセスはコード={}で終了しました".format(msg.returncode))


def unzip(app, path, out=None, win=False):
    path = app.abspath(path)

    from zipfile import ZipFile
    if out is None:
        out, _ = os.path.splitext(path)
    if not os.path.isdir(out):
        os.mkdir(out)

    memberdict = defaultdict(dict)
    with ZipFile(path) as zf:
        for membername in zf.namelist():
            zf.extract(membername, out)
            node = memberdict
            # リネーム用にパスをツリー構造で記録する
            if win:
                for part in membername.split("/"):
                    if not part:
                        continue
                    if part not in node:
                        node[part] = {}
                    node = node[part]
    
    # 文字化けしたファイル名をすべてリネーム
    if win:
        stack = [(out, memberdict, x) for x in memberdict.keys()]
        while stack:
            cd, d, memberpath = stack.pop()
            oldpath = os.path.join(cd, memberpath)
            newpath = os.path.join(cd, memberpath.encode("cp437").decode("utf-8"))
            os.rename(oldpath, newpath)
            stack.extend([(newpath, d[memberpath], x) for x in d[memberpath]])




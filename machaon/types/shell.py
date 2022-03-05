import os
import shutil
import stat
import datetime
from collections import defaultdict

from machaon.shellpopen import popen_capture
from machaon.types.fundamental import NotFound
from machaon.platforms import shellpath


def _normext(extension):
    if not extension.startswith("."):
        return "." + extension
    return extension

# Path new known-location-names
#
#
class Path():
    """ @type
    ファイル・フォルダのパス。
    コンストラクタ＝
    パス、または場所の名前を受ける。
    使用できる場所の名前の一覧は、known-names。
    """
    def __init__(self, path=None):
        self._path = os.fspath(path) if path else ""
        self._isdir = None
        self._stat = None
    
    def __str__(self):
        return self._path
    
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
        if self._isdir is None:
            self._isdir = os.path.isdir(self._path)
        return self._isdir
    
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
    
    def modtime(self):
        """ @method
        変更日時
        Returns:
            Datetime:
        """
        return datetime.datetime.fromtimestamp(os.path.getmtime(self._path))
    
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
        return Path(os.path.join(self._path, *paths))

    #
    # シェル機能
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
            return [Path(self._path)]
        return [x for x in self.listdir() if x.isfile()]
    
    def listdirall(self):
        """ @method [lsa]
        隠しファイルも含めた全てのファイルとサブディレクトリの一覧を返す。
        Returns:
            Sheet[Path](name, filetype, modtime, size):
        """
        if not self.isdir():
            return [Path(self._path)]
        items = [Path(os.path.join(self._path,x)) for x in os.listdir(self._path)]
        return items
    
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
            predicate(Function): 述語関数
            depth(int): 探索する階層の限界
        Returns:
            Sheet[Path](name, extension, modtime, size):
        """
        basedir = self.dir().path()
        for dirpath, dirname, filenames in os.walk(basedir):
            for filename in filenames:
                filepath = os.path.join(basedir, dirpath, filename)
                path = context.new_object(filepath, type="Path")
                if predicate.run_function(path, context).test_truth():
                    return path
        raise NotFound()
    
    def makedirs(self):
        """ @method
        パスが存在しない場合、ディレクトリとして作成する。途中のパスも作成する。
        """
        if self.isfile():
            raise ValueError("パスは既にファイルとして存在しています")
        os.makedirs(self.normpath, exist_ok=True)
    
    def move_to(self, d):
        """ @method
        別のディレクトリにこのファイルを移動する。
        Params:
            d(Path): 宛先ディレクトリ
        Returns:
            Path: コピーされたファイルパス
        """
        dest = d.dir() / self.name()
        if dest.exists():
            raise ValueError("すでに同名ファイルが宛先に存在しています")
        p = shutil.move(self.get(), dest.get())
        return Path(p)
    
    def move_from(self, p):
        """ @method
        このディレクトリにファイルを移動する。
        Params:
            p(Path): 移動するファイル
        Returns:
            Path: コピーされたファイルパス
        """
        dest = self.dir() / p.name()
        if dest.exists():
            raise ValueError("すでに同名ファイルが宛先に存在しています")
        p = shutil.move(p.get(), dest.get())
        return Path(p)
    
    def copy_to(self, d):
        """ @method
        このディレクトリにファイルをコピーする。
        Params:
            d(Path): コピー先のディレクトリ
        Returns:
            Path: コピーされたファイルパス
        """ 
        dest = d.dir() / self.name()
        if dest.exists():
            raise ValueError("すでに同名ファイルが宛先に存在しています")
        p = shutil.copy(self.get(), dest.get())
        return Path(p)
    
    def copy_from(self, p):
        """ @method
        このディレクトリにファイルをコピーする。
        Params:
            p(Path): コピーするファイル
        Returns:
            Path: コピーされたファイルパス
        """ 
        dest = self.dir() / p.name()
        if dest.exists():
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

    #
    #
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
    
    #
    # 型の振る舞い
    #
    def __truediv__(self, right):
        """ パスの結合 """
        if isinstance(right, Path):
            r = right._path
        elif isinstance(right, str):
            r = right
        else:
            raise TypeError("right")

        return Path(os.path.join(self._path, r))
    
    @classmethod
    def known(self, value, approot=None):
        """ 場所の名前からパスを得る """
        if value == "machaon" and approot:
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
        if isinstance(value, str):
            head, tail = os.path.split(value)
            if not head: # no slash in path
                # 場所の識別名として解釈
                p = Path.known(value, context.spirit.get_root())
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

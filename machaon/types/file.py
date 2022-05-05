import os

from machaon.types.shell import Path


class BasicLoadFile():
    """
    開いた時に中身を取得できるファイル
    load / save
    """
    def __init__(self, path=None, *, file=None):
        self._path = path or Path()
        self._file = file
    
    def resetfile(self, file=None):
        self._file = file

    def load(self):
        if self._file is None:
            self._file = self.loadfile()
        return self._file
    
    def loadfile(self):
        raise NotImplementedError()
    
    def path(self):
        """ @method
        ファイルパス。
        Returns:
            Path:
        """
        return self._path
    
    @property
    def pathstr(self):
        return self._path.get()
    
    @property
    def file(self):
        return self.load()

    def with_path(self, path):
        """ @method
        ファイルパスのみ変更したオブジェクトを生成。
        Params:
            path(Path):
        Returns:
            Any:
        """
        if type(self).__init__ is not BasicLoadFile.__init__:
            return self._with_path(path)
        return type(self)(path, file=self._file)
    
    def _with_path(self, *args, **kwargs):
        raise NotImplementedError()

    def save(self, *, nooverwrite=False):
        """ @task nospirit
        ファイルをセーブする。
        """
        # パスを変えて何度か試行する
        savepath = self.pathstr
        for retry_level in range(1, 4):
            if nooverwrite and os.path.exists(savepath):
                pass # 名前を変えて再トライ
            else:
                try:
                    self.savefile(savepath)
                except PermissionError:
                    pass # 名前を変えて再トライ
                else: 
                    break # 正常終了
            savepath = self._path.with_basename_format("{}_{}", retry_level).get()
        else:
            if nooverwrite:
                raise ValueError('"{}"に保存できません。同名のファイルが既に存在します。'.format(savepath))
            else:
                raise ValueError('"{}"に保存できません。別のアプリで開かれています。'.format(savepath))
        self._path = Path(savepath)
    
    def savefile(self, path):
        raise NotImplementedError()
    
    #
    def constructor(self, v):
        """ @meta 
        Params:
            Path:
        """
        return self.get_value_type()(v)

    def stringify(self):
        """ @meta """
        return self.pathstr


class BasicContextFile(BasicLoadFile):
    """
    開いている間のみ中身にアクセスできるファイル
    open / close
    """
    def __init__(self, path=None):
        super().__init__(path)
        self._stream = None
    
    def open(self, mode):
        if mode not in ("r", "w"):
            raise ValueError("mode must be 'r' or 'w'")
        if self._stream is not None:
            raise ValueError("File has already been opened")
        self._stream = self.openfile(mode)
        return self
    
    def openfile(self, mode):
        raise NotImplementedError()

    def close(self):
        if self._stream is None:
            raise ValueError("File has not been opened")
        self._stream.close()
        self._stream = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, et, ev, tb):
        self.close()
    
    #
    # LoadFileとして
    #
    def savefile(self, path):
        if self._file is None:
            return
        self._path.set(path)
        with self.open("w"):
            return self._stream.write(self._file)
    
    def loadfile(self, size=None):
        with self.open("r"):
            return self._stream.read(size)
    
    @property
    def stream(self):
        if self._stream is None:
            raise ValueError("File has not been opened")
        return self._stream
    
    def read_stream(self):
        """ ファイルを開いて読み込みストリームを返す。 """
        return self.open("r")

    def write_stream(self):
        """ ファイルを開いて書き込みストリームを返す。 """
        return self.open("w")

    def open_do(self, app, context, mode, block):
        """ @task context
        ファイルを開いて操作を行い、閉じる。
        Params:
            mode(Str): r/w
            block(Function):
        """
        with self.open(mode):
            subject = context.new_object(self, type=type(self))
            block.run_as_function(subject, context)


class BasicStream():
    """ ストリームの基底クラス """
    def __init__(self, source):
        self._source = source
        self._stream = None
    
    def get_path(self):
        if isinstance(self._source, str):
            return self._source
        elif hasattr(self._source, "__fspath__"):
            return self._source.__fspath__()
        import io
        if isinstance(self._source, io.FileIO):
            return self._source.name
        if hasattr(self._source, "path"): # Pathオブジェクトが返される
            return self._source.path().get()
        
        return None

    def __enter__(self):
        return self
    
    def __exit__(self, et, ev, tb):
        self.close()

    def _open_stream(self, rw, binary, encoding):
        source = self._source

        # ファイルパスから開く
        fpath = None
        if isinstance(source, str):
            fpath = source
        elif hasattr(source, "__fspath__"):
            fpath = source.__fspath__()
        if fpath:
            mode = rw[0] + ("b" if binary else "")
            return open(fpath, mode, encoding=encoding)
        
        # オブジェクトから開く
        if hasattr(source, "{}_stream".format(rw)):
            opener = getattr(source, "{}_stream".format(rw))
            return opener()
        
        # 開かれたストリームである
        import io
        if isinstance(source, io.IOBase):
            if source.closed:
                raise ValueError("Stream has already been closed")
            return source
        
        raise TypeError("'{}'からストリームを取り出せません".format(repr(source)))

    def _must_be_opened(self):
        if self._stream is None:
            raise ValueError("Stream is not opened")
    
    def close(self):
        self._must_be_opened()
        self._stream.close()
    

class InputStream(BasicStream):
    def open(self, binary=False, encoding=None):
        self._stream = self._open_stream("read", binary=binary, encoding=encoding)
        return self
    
    def lines(self):
        self._must_be_opened()
        for l in self._stream:
            yield l
    
    def constructor(self, value):
        """ @meta """
        return InputStream(value)
    
    def stringify(self, _v):
        """ @meta """
        return "<InputStream>"


class OutputStream(BasicStream):
    def open(self, binary=False, encoding=None):
        self._stream = self._open_stream("write", binary=binary, encoding=encoding)
        return self
    
    def write(self, v):
        self._must_be_opened()
        return self._stream.write(v)

    def constructor(self, value):
        """ @meta """
        return OutputStream(value)

    def stringify(self, _v):
        """ @meta """
        return "<OutputStream>"
        
#
#
#
#
#
class TextFile(BasicContextFile):
    """ @type
    テキストファイル。
    """
    def __init__(self, path, *, encoding=None, **params):
        super().__init__(path)
        self._enc = encoding
        self._openparams = params
    
    def openfile(self, mode):
        self.detect_encoding()
        return open(self.pathstr, mode, encoding=self._enc, **self._openparams)

    def detect_encoding(self):
        """ @method
        文字エンコーディング形式を推定する。
        Returns:
            Str: 文字エンコーディングの名前
        """
        if self._enc is not None:
            return self._enc
        if not os.path.isfile(self.pathstr):
            raise ValueError("パスが存在しないため、ファイルを開くには文字列エンコーディングの指定が必要です")
        encoding = detect_text_encoding(self.pathstr)
        self._enc = encoding
        return encoding
    
    def encoding(self):
        """ @method
        設定された文字エンコーディング形式を取得する。
        Returns:
            Str:
        """
        return self._enc
    
    def set_encoding(self, encoding):
        """ @method
        文字エンコーディング形式を設定する。
        Params:
            encoding(Str):
        """
        self._enc = encoding
    
    def text(self, size=None):
        """ @task nospirit
        テキストを丸ごと返す。
        Params:
            size?(int): 取得する文字数
        Returns:
            Str:
        """
        return self.loadfile(size)

    def write_text(self, text):
        """ @task nospirit
        テキストを書き込んで閉じる。
        Params:
            text(str): 書き込むテキスト
        Returns:
            Str:
        """
        with self.write_stream():
            self.stream.write(text)

    def lines(self):
        """ @task nospirit
        行を返す。
        Returns:
            Tuple[Str]:
        """
        return list(self.read_stream())

    def write_lines(self, lines):
        """ @task nospirit
        行を書き込んで閉じる。
        Params:
            lines(Tuple[str]): 書き込む各行
        Returns:
            Str:
        """
        with self.write_stream():
            for line in lines:
                self.stream.write(line+"\n")


#
def detect_text_encoding(fpath):
    from machaon.platforms import console
    
    encset = []
    # Unicode
    encset.extend(["utf-8", "utf_8_sig", "utf-16"])
    # ascii extended encodings
    if console().default_encoding not in encset:
        encset.append(console().default_encoding)
    # ascii
    encset.append("ascii")

    cands = set(encset)
    size = 256
    badterminated = False
    with open(fpath, "rb") as fi:
        heads = fi.read(size)

        for i in range(4):
            if i>0:
                bit = fi.read(1)
                if bit is None:
                    break
                heads += bit

            for encoding in encset:
                if encoding not in cands:
                    continue
                try:
                    heads.decode(encoding)
                except UnicodeDecodeError as e:
                    if (size+i - e.end) < 4:
                        badterminated = True
                        continue
                    cands.remove(encoding)
                        
            if not cands:
                return None
            
            if not badterminated:
                break

    return next(x for x in encset if x in cands)

#
#
#
def get_binary_content(app, target, size=128, width=16):
    app.message-em("ファイル名：[%1%]", embed=[
        app.hyperlink.msg(target)
    ])
    app.message-em("--------------------")
    with open(app.abspath(target), "rb") as fi:
        bits = fi.read(size)
    j = 0
    app.message-em("        |" + " ".join(["{:0>2X}".format(x) for x in range(width)]))
    for i, bit in enumerate(bits):
        if i % width == 0:
            app.message-em("00000{:02X}0|".format(j), nobreak=True)
        app.message("{:02X} ".format(bit), nobreak=True)
        if i % width == width-1:
            app.message("")
            j += 1
    app.message-em("\n--------------------")
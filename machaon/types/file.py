import os

from machaon.types.shell import Path


class BasicLoadFile():
    """
    開いた時に中身を取得できるファイル
    load / save
    """
    def __init__(self, path=None, *, file=None):
        if not isinstance(path, Path):
            path = Path(path)
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
    
    def openfile(self, mode):
        raise NotImplementedError()

    def open(self, mode):
        if mode not in ("r", "w"):
            raise ValueError("mode must be 'r' or 'w'")
        if self._stream is not None:
            raise ValueError("ファイル'{}'は既に開かれています".format(self.path()))
        self._stream = self.openfile(mode)
        return self
    
    def close(self):
        if self._stream is None:
            raise ValueError("ファイル'{}'はまだ開かれていません".format(self.path()))
        self._stream.close()
        self._stream = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, et, ev, tb):
        self.close()
    
    #
    # LoadFileとしてオーバーライド
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
            raise ValueError("ファイル'{}'はまだ開かれていません".format(self.path()))
        return self._stream
    
    def read_stream(self):
        """ ファイルを開いて読み込みストリームを返す。 """
        return self.open("r")

    def write_stream(self):
        """ ファイルを開いて書き込みストリームを返す。 """
        return self.open("w")

    def open_do(self, app, context, mode, selector):
        """ @task context
        ファイルを開いて操作を行い、閉じる。
        Params:
            mode(Str): r/w
            selector(Function[seq]):
        """
        with self.open(mode):
            selector(self)


class BasicFileStream(BasicContextFile):
    """ Pythonストリームの基底クラス """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)    

    #
    #
    #
    def seek(self, offset):
        """ @task nospirit
        先頭からのオフセット位置に移動する
        Params:
            offset(int):
        Returns:
            int:
        """
        if offset > 0:
            self.stream.seek(offset, 0)
        elif offset < 0:
            self.stream.seek(offset, 2)
        
    def seekdelta(self, offset):
        """ @task nospirit
        現在地からのオフセット位置に移動する
        Params:
            offset(int):
        Returns:
            int:
        """
        return self.stream.seek(offset, 1)
    
    def tell(self):
        """ @task nospirit
        現在のオフセットを返す
        Returns:
            int:
        """
        return self.stream.tell()
        
    def read(self, length=None):
        """ @task nospirit
        開いているストリームから読み取る
        Params:
            length(int):
        """
        return self.stream.read(length or -1)

    def write(self, data):
        """ @task nospirit
        開いているストリームに書き込む
        Params:
            data(Any):
        """
        return self.stream.write(data)

    def flush(self):
        """ @task nospirit 
        バッファを書き込む
        """
        self.stream.flush()
        
    def seek_and_read(self, offset, length):
        """ @task nospirit
        あるオフセットからある長さのデータを読み取る
        Params:
            offset(int):
            length(int):
        """
        if offset is not None:
            self.seek(offset)
        return self.read(length)
        
    def seek_and_write(self, offset, data):
        """ @task nospirit
        あるオフセットからある長さのデータを書き込む
        Params:
            offset(int):
            data(Any):
        """
        if offset is not None:
            self.seek(offset)
        return self.write(data)

#
#
#
#
#
class TextFile(BasicFileStream):
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
    
    def text(self, size=None, offset=None):
        """ @task nospirit
        テキストを丸ごと返す。
        Params:
            size?(int): 取得する文字数
            offset?(int):
        Returns:
            Str:
        """
        with self.read_stream():
            return self.seek_and_read(offset, size)

    def write_text(self, text, offset=None):
        """ @task nospirit
        テキストを書き込んで閉じる。
        Params:
            text(str): 書き込むテキスト
            offset?(int):
        Returns:
            Str:
        """
        with self.write_stream():
            self.seek_and_write(offset, text)

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
    from machaon.platforms import ui
    
    encset = []
    # Unicode
    encset.extend(["utf-8", "utf_8_sig", "utf-16"])
    # ascii extended encodings
    if ui().default_encoding not in encset:
        encset.append(ui().default_encoding)
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
class BinaryFile(BasicFileStream):
    """ @type
    バイナリデータファイル。
    """
    def __init__(self, path, **params):
        super().__init__(path)
        self._openparams = params

    def openfile(self, mode):
        return open(self.pathstr, mode+"b", **self._openparams)

    def bytes(self, size=None, offset=None):
        """ @task nospirit
        データを読み取る。
        Params:
            size?(int): 取得する文字数
            offset?(int): 先頭からのオフセット
        Returns:
            Any:
        """
        with self.read_stream():
            return self.seek_and_read(offset, size)
    
    def write_bytes(self, bits, offset=None):
        """ @task nospirit
        データを書き込む。
        Params:
            bits(Any): 書き込むデータ
            offset?(int):
        """
        with self.write_stream():
            self.seek_and_write(offset, bits)

    def view(self, app, size=None, offset=None):
        """ @task
        先頭の数バイトを表示する。
        Params:
            size?(int): 取得するバイト数
            offset?(int): 先頭からのオフセット（負値も可）
        """
        bits = self.bytes(size or 64, offset)

        width = 16
        indent = " " * 8
        app.post("message-em", indent + "|" + " ".join(["{:0>2X}".format(x) for x in range(width)]))

        j = 0
        linebuf = []
        for i, bit in enumerate(bits):
            app.interruption_point()
            if i % width == 0:
                app.post("message-em", "00000{:02X}0|".format(j), nobreak=True)
            linebuf.append(bit)
            if i % width == width-1:
                app.post("message", " ".join(["{:02X}".format(x) for x in linebuf]))
                linebuf.clear()
                j += 1
    

        

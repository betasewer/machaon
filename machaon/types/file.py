import os
from machaon.types.shell import Path

class BasicLoadFile():
    """
    開いた時に中身を取得できるファイル
    """
    def __init__(self, path, file=None):
        self._path = path
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
            raise ValueError("Need overwrite")
        return type(self)(path, file=self._file)

    def save(self, app):
        """ @task
        ファイルをセーブする。
        """
        savepath = self._pathstr
        for retry_level in range(1, 4):
            try:
                self.savefile(savepath)
            except PermissionError:
                savepath = self._path.with_basename_format("{}_{}", retry_level).get()
            else:
                break
        else:
            app.post("error", '"{}"に保存できません。別のアプリで開かれています。'.format(self._pathstr))
        self._path.set(savepath)
    
    def savefile(self, path):
        raise NotImplementedError()
    
    #
    def conversion_construct(self, context, v):
        return self.get_value_type()(context.new_object(v, type=Path).value)

    def stringify(self):
        return self.pathstr


class BasicContextFile():
    """
    開いている間のみ中身にアクセスできるファイル
    """
    def __init__(self, path):
        self._path = path
        self._file = None
    
    def open(self, mode):
        if mode not in ("r", "w"):
            raise ValueError("mode must be 'r' or 'w'")
        if self._file is not None:
            raise ValueError("File has already been opened")
        self._file = self.openfile(mode)
        return self._file
    
    def openfile(self, mode):
        raise NotImplementedError()

    def close(self):
        if self._file is None:
            raise ValueError("File has not been opened")
        self._file.close()
        self._file = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, et, ev, tb):
        self.close()
    
    def path(self):
        """ @method
        パスを得る。
        Returns:
            Path:
        """
        return self._path
    
    @property
    def pathstr(self):
        return self._path.get()
    
    @property
    def file(self):
        if self._file is None:
            raise ValueError("File has not been opened")
        return self._file
    
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
    
    #
    def conversion_construct(self, context, v):
        return self.get_value_type()(context.new_object(v, type=Path).value)

    def stringify(self):
        return self.pathstr


class TextFile(BasicContextFile):
    """ @type
    テキストファイル。
    Typename: TextFile    
    """
    def __init__(self, path):
        super().__init__(path)
        self._enc = None
    
    def openfile(self, mode):
        self.detect_encoding()
        return open(self.pathstr, mode, encoding=self._enc)

    def detect_encoding(self):
        """ @method
        文字エンコーディング形式を推定する。
        Returns:
            Str: 文字エンコーディングの名前
        """
        if self._enc is not None:
            return self._enc
        encoding = detect_text_encoding(self.pathstr)
        self._enc = encoding
        return encoding
    
    def encoding(self):
        """ @method
        文字エンコーディング形式を取得する。
        Returns:
            encoding(Str):
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
        """ @method
        テキストを丸ごと返す。
        Params:
            size(int): 取得する文字数
        Returns:
            Str:
        """
        with self.openfile("r") as fi:
            return fi.read(size)

    def read_stream(self):
        """ ファイルを開いて読み込みストリームを返す。 """
        return self.open("r").file()

    def write_stream(self):
        """ ファイルを開いて書き込みストリームを返す。 """
        return self.open("w").file()


#
def detect_text_encoding(fpath):
    from machaon.platforms import current
    
    encset = ["utf-8", "utf_8_sig", "utf-16", "shift-jis"]
    if current.default_encoding not in encset:
        encset.insert(0, current.default_encoding)

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
import os
from machaon.types.shell import Path
from machaon.types.file import TextFile
from machaon.core.object import Object
from machaon.core.message import run_function_print_step, run_function

def get_persistent_path(root, name):
    """ オブジェクト名からファイルパスを得る
    Params:
        root(AppRoot):
        name(str): /区切りの相対パス
    """
    d = root.get_store_dir()
    path = os.path.join(d, *name.split("/"))
    if not os.path.isfile(path):
        path = path + ".txt"
    return path

def enum_persistent_names(root):
    """ machaon標準ディレクトリからファイルを読み込む """
    n = []
    d = root.get_store_dir()
    for dirpath, _dirnames, filenames in os.walk(d):
        parts = []
        if not os.path.samefile(dirpath, d):
            p = os.path.relpath(dirpath, d)
            while p:
                p, tail = os.path.split(p)
                parts.append(tail)
            parts.reverse()

        for filename in filenames:
            name, _ = os.path.splitext(filename)
            fullname = "/".join(parts + [name])
            n.append(fullname)
    return n


class StoredMessage():
    """ 記述されたメッセージ """
    def __init__(self, path, name=None):
        self.path = path
        self.name = name
        self._buf = []
    
    def get_path(self):
        """ @method alias-name [path]
        ファイルパス
        Returns:
            Str:
        """
        return self.path
    
    def get_name(self):
        """ @method alias-name [name]
        ファイルパス
        Returns:
            Str:
        """
        return self.name or "<no-name>"
    
    def exists(self):
        """ @method
        ファイルパスが存在するか。
        Returns:
            bool:
        """
        return os.path.isfile(self.path)
        
    def message(self):
        """ @method
        メッセージの内容を返す。
        Returns:
            Str:
        """
        if not self.exists():
            raise ValueError("ファイルが存在しません")
        f = TextFile(Path(self.path))
        return f.text()

    def recall(self, context, context_index):
        """ @method context
        コンテキストに紐づけられたメッセージを書き留める。
        Params:
            context_index(str):
        """
        from machaon.core.invocation import InvocationContext
        cxt = InvocationContext.constructor(InvocationContext, context, context_index)
        self._buf.append(cxt.get_message())

    def record(self, message):
        """ @method
        メッセージを書き留める。
        Params:
            message(str):
        """
        self._buf.append(message)
    
    def save(self):
        """ @method
        書き留められたメッセージを保存する。
        """
        if not self._buf:
            raise ValueError("record, recallで保存するメッセージを追加してください")
        if self.exists():
            raise ValueError("すでにファイルが存在します")
        f = TextFile(Path(self.path), encoding="utf-8")
        with f.write_stream():
            for line in self._buf[:-1]:
                f.stream.write(line + ' . \n')
            f.stream.write(self._buf[-1])
        self._buf.clear()

    def do(self, context, app=None, *, subject=None):
        """ @task context
        メッセージを実行し、返り値を返す。
        Returns:
            Object:
        """
        content = self.message()
        return run_function_print_step(content, subject, context, raiseerror=True)

    def do_silent(self, context, app=None, *, subject=None):
        """ @task context 
        メッセージを表示せずに実行する。
        Returns:
            Object:
        """
        content = self.message()
        return run_function(content, subject, context, raiseerror=True)

    def bind(self, context):
        """ @method context
        オブジェクトを名前に束縛する。
        Returns:
            Object:
        """
        o = self.do(context, None)
        context.push_object(self.name, o)
        context.spirit.post("message", "'{}'からロード => @{}".format(self.path, self.name))
        return o

    def edit(self):
        """ @method
        エディタで開く。
        """
        if not self.exists():
            raise ValueError("ファイルが存在しません")
        from machaon.types.shellplatform import shellpath
        return shellpath().start_file(self.path)

    def constructor(self, context, value):
        """ @meta """
        # 外部ファイルのパスを得る
        from machaon.types.shell import Path
        if isinstance(value, str):
            path = get_persistent_path(context.root, value)
            name, _ = os.path.splitext(os.path.split(path)[1])
        elif isinstance(value, Path):
            path = value
            name = None
        else:
            raise TypeError("")
        
        return StoredMessage(path, name)
    
    def stringify(self):
        """ @meta """
        name = self.get_name()
        return "<StoredMessage {} from '{}'>".format(name, self.path)



import os
from machaon.types.shell import Path
from machaon.types.file import TextFile
from machaon.core.message import run_function

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
        if not os.path.isfile(path):
            raise ValueError("ファイルが見つかりません")
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
    def __init__(self, path, name):
        self.path = path
        self.name = name
    
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
            
    def message(self):
        """ @method
        メッセージを表示する。
        Returns:
            Str:
        """
        f = TextFile(Path(self.path))
        return f.text()

    def do(self, context, _app):
        """ @task context
        メッセージを実行し、返り値を返す。
        Returns:
            Object:
        """
        content = self.message()
        return run_function(content, None, context, raiseerror=True)
    
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



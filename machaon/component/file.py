import shutil
import os

from machaon.types.shell import Path, TemporaryDirectory
from machaon.types.file import TextFile


class FSTransaction:
    def __init__(self):
        self._transactions = []

    def filewrite_to(self, dest):
        tr = FileWriteTransaction(dest)
        self._transactions.append(tr)
        return tr
    
    def treecopy_to(self, dest):
        tr = TreeCopyTransaction(dest)
        self._transactions.append(tr)
        return tr
    
    def pathensure(self, dest):
        tr = PathEnsureTransaction(dest)
        self._transactions.append(tr)
        return tr
    
    def apply(self, app):
        for tr in self._transactions:
            tr.apply(app)

    def __iadd__(self, right: 'FSTransaction'):
        self._transactions.extend(right._transactions)
        return self


class PathEnsureTransaction:
    def __init__(self, dest: Path):
        if not isinstance(dest, Path):
            raise TypeError("dest")
        self.dest = dest
        self._clean = False
        
    def clean(self, b):
        self._clean = b
        return self
    
    def apply(self, app):
        if self._clean and self.dest.exists():
            app.post("message", "ファイルツリーを削除: {}".format(self.dest))
            self.dest.rmtree()  # 元ディレクトリを削除する      
        app.post("message", "パスを確認: {}".format(self.dest))
        self.dest.makedirs()


class FileWriteTransaction(PathEnsureTransaction):
    def __init__(self, dest: Path):
        super().__init__(dest)
        self.temp = TemporaryDirectory(ignore_cleanup_errors=True)
        self.temp.prepare()

    def fileexists(self, p: Path):
        return (self.dest / p).isfile()
    
    def write(self, p: Path, value: str):
        target = self.temp.path() / p
        target.up().makedirs()
        TextFile(target, encoding="utf-8").write_text(value.lstrip())
        return self
    
    def apply(self, app):
        super().apply(app) # 書き込み先パスを確保する
        def copier(src: str, dest: str):
            app.post("message", "ファイルを書き込み: {}".format(dest))
            shutil.copy2(src, dest)
        shutil.copytree(self.temp.path(), self.dest, dirs_exist_ok=True, copy_function=copier) # 上書きする
        self.temp.cleanup()


class TreeCopyTransaction:
    def __init__(self, dest: Path):
        if not isinstance(dest, Path):
            raise TypeError("dest")
        self.dest = dest
        self.src = None

    def copy(self, src: Path):
        self.src = src
        return self

    def apply(self, app):
        if self.src is None:
            return
        if self.dest.exists():
            app.post("message", "ファイルツリーを削除: {}".format(self.dest))
            self.dest.rmtree()  # 元ディレクトリを削除する
        app.post("message", "ファイルツリーをコピー: {} -> {}".format(self.src, self.dest))
        shutil.copytree(self.src, self.dest)




#
#
#
def readfile(p: Path) -> str:
    return TextFile(p, encoding="utf-8").text()

def readtemplate(p: Path) -> str:
    p = Path(__file__).up() / "template" / p
    return readfile(p)




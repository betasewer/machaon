import shutil
import os
from typing import TypeVar

from machaon.types.shell import Path, TemporaryDirectory
from machaon.types.file import TextFile

class Transaction:
    def apply(self, app):
        raise NotImplementedError()

T = TypeVar('T')

class FSTransaction:
    def __init__(self):
        self._transactions: list[Transaction] = []

    def append(self, tr: T):
        self._transactions.append(tr)
        return tr

    def filewrite_to(self, dest):
        return self.append(FileWriteTransaction(dest))
    
    def treecopy_to(self, dest):
        return self.append(TreeCopyTransaction(dest))
    
    def pathensure(self, dest):
        return self.append(PathEnsureTransaction(dest))
    
    def apply(self, app):
        for tr in self._transactions:
            tr.apply(app)

    def __iadd__(self, right: 'FSTransaction'):
        self._transactions.extend(right._transactions)
        return self


class PathEnsureTransaction(Transaction):
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
        if not self.dest.exists():
            os.mkdir(self.dest, mode=0o777)
#            self.dest.makedirs()


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


class TreeCopyTransaction(Transaction):
    def __init__(self, dest: Path):
        if not isinstance(dest, Path):
            raise TypeError("dest")
        self.dest = dest
        self.src:Path = None
        self.dest_req:Path = None

    def dest_required(self, d: Path):
        self.dest_req = d
        return self

    def copy(self, src: Path):
        self.src = src
        return self

    def apply(self, app):
        if self.src is None:
            return
        if self.dest.exists():
            if self.dest_req is not None:
                app.post("message", "ファイルツリーをクリア: {}".format(self.dest))
                self.dest_req.remove_children()
            else:
                app.post("message", "ファイルツリーを削除: {}".format(self.dest))
                self.dest.rmtree()  # 元ディレクトリを削除する
        app.post("message", "ファイルツリーをコピー: {} -> {}".format(self.src, self.dest))
        shutil.copytree(self.src, self.dest, dirs_exist_ok=True)




#
#
#
def readfile(p: Path) -> str:
    return TextFile(p, encoding="utf-8").text()

def readtemplate(p: Path) -> str:
    p = Path(__file__).up() / "template" / p
    return readfile(p)




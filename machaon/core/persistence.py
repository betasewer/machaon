import os
from machaon.types.shell import Path
from machaon.types.file import TextFile
from machaon.core.message import run_function

def get_persistent_path(root, name):
    """ machaon標準ディレクトリからファイルを読み込む """
    d = root.get_basic_dir()
    path = os.path.join(d, name)
    if not os.path.isfile(path):
        path = path + ".txt"
        if not os.path.isfile(path):
            raise ValueError("ファイルが見つかりません")
    return path

def enum_persistent_names(root):
    """ machaon標準ディレクトリからファイルを読み込む """
    n = []
    d = root.get_basic_dir()
    for name in os.listdir(d):
        path = os.path.join(d, name)
        if os.path.isfile(path):
            name, _ = os.path.splitext(name)
            n.append(name)
    return n

def load_persistent_file(context, path):
    """ ファイルにメッセージとして記述されたオブジェクトをロードする """
    f = TextFile(Path(path))    
    content = f.text()
    # メッセージとして実行する
    obj = run_function(content, None, context)
    return obj



# bookinfosample Object
# machaon Path / bookinfosample Object => macha


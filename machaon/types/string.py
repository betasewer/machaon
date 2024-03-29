import re
import string
from machaon.core.function import parse_sequential_function


class StrType():
    """ @type trait [Str]
    Pythonの文字列型。
    ValueType:
        str
    """
    def constructor(self, o):
        """ @meta 
        Params:
            Any:
        """
        return str(o)
    
    def stringify(self, v):
        """ @meta """
        return v
    
    #
    # 文字列を検索・置換する
    #
    def find(self, s, sub, start=None, end=None):
        """ @method
        文字を検索する
        Params:
            sub(str): 
            start?(int): 開始位置  
            end?(int): 終了位置
        Returns:
            Int: 文字の開始位置。見つからなければ-1
        """
        return s.find(sub, start, end)

    def rfind(self, s, sub, start=None, end=None):
        """ @method
        文字を右から検索する
        Params:
            sub(str): 
            start?(int): 開始位置  
            end?(int): 終了位置
        Returns:
            Int: 文字の開始位置。見つからなければ-1
        """
        return s.rfind(sub, start, end)
        
    def index(self, s, sub, start=None, end=None):
        """ @method
        文字を検索する
        Params:
            sub(str): 
            start?(int): 開始位置  
            end?(int): 終了位置
        Returns:
            Int: 文字の開始位置
        """
        return s.index(sub, start, end)
    
    def rindex(self, s, sub, start=None, end=None):
        """ @method
        文字を右から検索する
        Params:
            sub(str): 
            start?(int): 開始位置  
            end?(int): 終了位置
        Returns:
            Int: 文字の開始位置
        """
        return s.rindex(sub, start, end)
    
    def count(self, s, sub, start=None, end=None):
        """ @method
        出現数を数える。
        Params:
            sub(str): 数える文字列
            start?(int): 開始位置  
            end?(int): 終了位置
        Returns:
            Int:
        """
        return s.count(sub, start, end)
    
    def startswith(self, s, suffix, start=None, end=None):
        """ @method
        この文字列で始まるか
        Params:
            suffix(str): 
            start?(int): 開始位置  
            end?(int): 終了位置
        Returns:
            Bool:
        """
        return s.startswith(suffix, start, end)

    def endswith(self, s, suffix, start=None, end=None):
        """ @method
        この文字列で終わっているか
        Params:
            suffix(str): 
            start?(int): 開始位置  
            end?(int): 終了位置
        Returns:
            Bool:
        """
        return s.endswith(suffix, start, end)

    def replace(self, s, old, new, count=None):
        """ @method
        文字列を置き換える。
        Params:
            old(str): 元の文字列
            new(str): 新しい文字列
            count?(int): 置換回数
        Returns:
            str:
        """
        return s.replace(old, new, count or -1)

    def translate(self, s, table):
        """ @method
        一文字ごとの変換表を作成し、文字列を置き換える。
        Params:
            table(ObjectCollection): 文字 -> 文字列/None のマップ
        Returns:
            Str:
        """
        return s.translate(str.maketrans(table))
    
    def reg_match(self, s, pattern):
        '''@method
        正規表現に先頭から一致するかを調べる。
        Params:
            pattern (str): 正規表現
        Returns:
            bool: 一致するか
        '''
        m = re.match(pattern, s)
        if m:
            return True
        return False
    
    def reg_search(self, s, pattern):
        '''@method
        正規表現にいずれかの部分が一致するかを調べる。
        Params:
            pattern (str): 正規表現
        Returns:
            bool: 一致するか
        '''
        m = re.search(pattern, s)
        if m:
            return True
        return False
    
    def reg_replace(self, s, pattern, new, count=0):
        '''@method
        正規表現を利用して文字列を置き換える。
        Params:
            pattern (str): 正規表現
            new (str): 置き換え文字列
            count? (int): 置き換え回数
        Returns:
            Str:
        '''
        return re.sub(pattern, new, s, count)
    
    #
    # 大文字と小文字
    #
    def lower(self, s):
        """ @method
        小文字化する。
        Returns:
            Str:
        """
        return s.lower()

    def upper(self, s):
        """ @method
        大文字化する。
        Returns:
            Str:
        """
        return s.upper()

    def capitalize(self, s):
        """ @method
        先頭を大文字化する。
        Returns:
            Str:
        """
        return s.capitalize()
    
    def swapcase(self, s):
        """ @method
        大文字と小文字を入れ替える。
        Returns:
            Str:
        """
        return s.swapcase()

    def casefold(self, s):
        """ @method
        casefold化する。
        Returns:
            Str:
        """
        return s.casefold()

    def title(self, s):
        """ @method
        各単語の先頭を大文字にする。
        Returns:
            Str:
        """
        return s.title()

    def islower(self, s):
        """ @method 
        すべてが小文字か
        Returns:
            Bool:
        """
        return s.islower()
    
    def isupper(self, s):
        """ @method 
        すべてが大文字か
        Returns:
            Bool:
        """
        return s.isupper()
    
    def istitle(self, s):
        """ @method 
        すべてがタイトルのようか
        Returns:
            Bool:
        """
        return s.istitle()
    
    #
    # 文字列を分解・合成する
    #
    def slice(self, s, start=None, end=None):
        """ @method
        文字列の一部を切り出す。
        Params:
            start? (int): 
            end? (int):
        Returns:
            Str:
        """
        return s[start:end]
    
    def add(self, s, text):
        """ @method
        文字列の後ろに付け足す。
        Params:
            text(str):
        Returns:
            Str:
        """
        return s + text

    def enclose(self, s, before, after):
        """ @method
        文字列の両側に付け足す。
        Params:
            before(str):
            after(str):
        Returns:
            Str:
        """
        return before + s + after

    def format(self, s, *args):
        """@method
        引数から書式にしたがって文字列を作成する。
        Params:
            *args: 任意の引数
        Returns:
            str: 文字列
        """
        return s.format(*args)
    
    def format_map(self, s, mapping):
        """@method
        辞書の引数から書式にしたがって文字列を作成する。
        Params:
            mapping(ObjectCollection):
        Returns:
            str: 文字列
        """
        return s.format_map(mapping)

    def split(self, s, sep=None, maxsplit=-1):
        """@method
        文字を区切る。
        Params:
            sep?(Str): 区切り文字
            maxsplit?(Int): 区切り回数
        Returns:
            Tuple: データ
        """
        return s.split(sep, maxsplit=maxsplit)

    def rsplit(self, s, sep=None, maxsplit=-1):
        """@method
        文字を右から区切る。
        Params:
            sep?(Str): 区切り文字
            maxsplit?(Int): 区切り回数
        Returns:
            Tuple: データ
        """
        return s.rsplit(sep, maxsplit=maxsplit)

    def partition(self, s, sep):
        """ @method 
        文字を一か所で区切る。
        Params:
            sep(Str):
        Returns:
            Tuple: 前、区切り文字、後の3つの組
        """
        return s.partition(sep)

    def rpartition(self, s, sep):
        """ @method 
        右から文字を一か所で区切る。
        Params:
            sep(Str):
        Returns:
            Tuple: 前、区切り文字、後の3つの組
        """
        return s.rpartition(sep)

    def join(self, s, values):
        """@method
        文字を結合する。
        Params:
            values(Tuple):
        Returns:
            Str:
        """
        return s.join(values)

    def strip(self, s, chars=None):
        """ @method
        文字の両脇の空白を落とす。
        Params:
            chars?(str): 落とす文字の指定
        Returns:
            Str:
        """
        return s.strip(chars)
    
    def lstrip(self, s, chars=None):
        """ @method
        文字の左脇の空白を落とす。
        Params:
            chars?(str): 落とす文字の指定
        Returns:
            Str:
        """
        return s.lstrip(chars)

    def rstrip(self, s, chars=None):
        """ @method
        文字の右脇の空白を落とす。
        Params:
            chars?(str): 落とす文字の指定
        Returns:
            Str:
        """
        return s.rstrip(chars)

    def splitlines(self, s, keepends=False):
        """ @method
        行で分割する。
        Params: 
            keepends? (bool): 改行文字を保存する
        Returns:
            Tuple:
        """
        return s.splitlines(keepends)
    
    #
    # 文字寄せ
    #
    def center(self, s, width, fillchar=None):
        """ @method
        中央に寄せる。
        Params:
            width(int): 幅
            fillchar?(str): 埋める文字
        Returns:
            Str:
        """
        return s.center(width, fillchar)

    def ljust(self, s, width, fillchar=None):
        """ @method
        文字を左に寄せる。
        Params:
            width(int): 
            fillchar?(str):
        Returns:
            Str:
        """
        return s.ljust(width, fillchar)
        
    def rjust(self, s, width, fillchar=None):
        """ @method
        文字を右に寄せる。
        Params:
            width(int): 
            fillchar?(str):
        Returns:
            Str:
        """
        return s.rjust(width, fillchar)

    def zerofill(self, s, width):
        """ @method
        数値の文字列を0で埋める。
        Params:
            width(int):
        Returns:
            Str:
        """
        return s.zfill(width)

    #
    # 変換
    #
    def convertas_literals(self, s, context):
        """ @method context alias-name [as-literal]
        値を適当な型に変換する。
        Params:
        Returns:
            Object: 新たな型の値
        """
        from machaon.core.message import select_literal
        return select_literal(context, s)
  
    def expandtabs(self, s, tabsize=None):
        """ @method
        タブをスペースに展開する
        Params:
            tabsize?(int):
        Returns:
            Str:
        """
        if tabsize is None:
            return s.expandtabs()
        else:
            return s.expandtabs(tabsize)
          
    def encode(self, s, encoding, errors=None):
        """ @method
        バイト列にエンコードする。
        Params:
            encoding(str): エンコーディング
            errors?(str): エラー処理
        Returns:
            Bytes:
        """
        if errors:
            return s.encode(encoding, errors)
        else:
            return s.encode(encoding)

    def chars(self, s):
        """ @method
        文字のタプルに変換する。
        Returns:
            Tuple:
        """
        return [c for c in s]
        
    def normalize(self, s, form):
        """ @method
        Unicode正規化を行う。
        Params:
            form(str): NFD, NFC, NFKD, NFKCのいずれか
        Returns:
            Str:
        """
        import unicodedata
        return unicodedata.normalize(form, s) # 全角と半角など

    #
    # 文字の種類
    #
    def isalnum(self, s):
        """ @method 
        アルファベットと文字列。
        Returns:
            bool:
        """
        return s.isalnum()

    def isalpha(self, s):
        """ @method 
        アルファベット。
        Returns:
            bool:
        """
        return s.isalpha()
    
    def isascii(self, s):
        """ @method 
        ASCIIの範囲内の文字。
        Returns:
            bool:
        """
        return s.isascii()

    def isdecimal(self, s):
        """ @method 
        Unicodeで定められた10進数を表す文字。
        Returns:
            bool:
        """
        return s.isdecimal()

    def isdigit(self, s):
        """ @method 
        Unicodeで定められた数字の桁を表す文字。
        Returns:
            bool:
        """
        return s.isdigit()

    def isnumeric(self, s):
        """ @method 
        Unicodeで定められた数字を表す文字。
        Returns:
            bool:
        """
        return s.isnumeric()

    def isxdigit(self, s):
        """ @method
        16進数で使用する文字。Unicodeの定義は参照しない。
        Returns:
            bool:
        """
        return all(c in string.hexdigits for c in s)
    
    def isodigit(self, s):
        """ @method
        8進数で使用する文字。Unicodeの定義は参照しない。
        Returns:
            bool:
        """
        return all(c in string.octdigits for c in s)
    
    def isprintable(self, s):
        """ @method 
        印刷できる文字。
        Returns:
            bool:
        """
        return s.isprintable()

    def isspace(self, s):
        """ @method 
        Unicodeで定められた空白文字。
        Returns:
            bool:
        """
        return s.isspace()

    def isnumberpunct(self, ch):
        """ @method [isnumpunct]
        符号。
        Returns:
            bool:
        """
        return ch in ("-", "+", ".", ",")

    def is0xob(self, ch):
        """ @method
        2/8/16進数の接頭辞。
        Returns:
            bool:
        """
        return ch.lower() in ("0","x","o","b")
    
    def ispyident(self, s):
        """ @method 
        Pythonの識別名として使用できる文字。
        Returns:
            bool:
        """
        return s.isidentifier()

    def extract(self, s, context, *classes):
        """ @method context
        特定の文字を抽出する
        Params:
            +classes(Any): 文字クラス[セレクタ|regex=正規表現]
        Returns:
            Str:
        """
        testers = []
        for klass in classes:
            if isinstance(klass, str) and klass.startswith("regex="):
                reg = re.compile(klass[6:])
                testers.append(reg.match)
            else:
                fn = parse_sequential_function(klass, context)
                testers.append(fn)
        
        buf = []
        for ch in s:
            if any(tester(ch) for tester in testers):
                buf.append(ch)
        
        return "".join(buf)
    
    def desuffix(self, s, value):
        """ @method
        接尾辞を取り除く。
        Params:
            value(Str):
        Returns:
            Str:
        """
        i = s.rfind(value)
        if i == -1 or i > (len(s) - len(value)):
            raise ValueError("'{}'には接尾辞'{}'がありません".format(s, value))
        return s[:i]

    def deprefix(self, s, value):
        """ @method
        接頭辞を取り除く。
        Params:
            value(Str):
        Returns:
            Str:
        """
        i = s.find(value)
        if i != 0:
            raise ValueError("'{}'には接頭辞'{}'がありません".format(s, value))
        return s[len(value):]
    
    # 
    # コード実行
    #
    def do(self, s, context, _app, subject=None):
        """ @task context
        文字列をメッセージとして評価する。例外を発生させる。
        Params:
            subject(Object): *引数
        Returns:
            Object: 返り値
        """
        from machaon.core.function import run_function
        return run_function(s, subject, context, raiseerror=True)

    def fn(self, s):
        """ @method
        文字列を関数として返す。
        Returns:
            Function:
        """
        from machaon.core.function import parse_function
        return parse_function(s)
    
    def seqfn(self, s):
        """ @method
        文字列を関数として返す。
        Returns:
            Function:
        """
        from machaon.core.function import  parse_sequential_function
        return parse_sequential_function(s)
    
    def do_external(self, s, context, app):
        """ @task context [doex do-ex]
        文字列をメッセージを記述したファイルの名前として評価し、実行して返す。
        Returns:
            Object: 返り値
        """
        o = context.new_object(s, type="Stored")
        ret = o.value.do(context, app)
        return ret

    def do_python(self, expr, _app):
        """ @task [dopy do-py]
        Pythonの式として評価し、実行して返す。
        先頭に[name1 name2...]と書くことでモジュールをインポートできる。
        Returns:
            Any:
        """
        expr = expr.strip()
        if expr.startswith("["):
            from machaon.core.importer import module_loader
            rparen = expr.find("]")
            if rparen == -1:
                raise ValueError("モジュール指定の括弧が閉じていません")
            imports = expr[1:rparen].strip().split()
            body = expr[rparen+1:].strip()

            if body.startswith("."):
                body = imports[0] + body
        else:
            imports = []
            body = expr

        class submodule:
            pass

        glob = {}
        for impname in imports:
            loader = module_loader(impname)
            mod = loader.load_module()

            par = mod
            chi = mod
            nameparts = impname.split(".")
            for namepart in reversed(nameparts[1:]):
                par = submodule()
                setattr(par, namepart, chi)
                chi = par

            glob[nameparts[0]] = par
        
        return eval(body, glob, {})
    
    def load_python(self, expr):
        """ @method alias-name [py]
        Pythonの関数または定数の呼び出しオブジェクトを作成する。
        Returns:
            Any:
        """
        from machaon.core.importer import attribute_loader
        from machaon.core.invocation import FunctionInvocation
        loader = attribute_loader(expr)
        return FunctionInvocation(loader())
    
    def load_python_module(self, expr):
        """ @method alias-name [pymod]
        Pythonのモジュールとして読み込み、モジュールオブジェクトを返す。
        Returns:
            Any:
        """
        from machaon.core.importer import module_loader
        loader = module_loader(expr)
        return loader.load_module()

    def run_command(self, string, app, *params):
        """ @task
        シェルのコマンドを実行し、終わるまで待つ。入出力をキャプチャする。
        Params:
            *params(Any): コマンド引数
        """
        if not string:
            return
        from machaon.types.shell import run_command_capturing
        pa = [string, *params]
        run_command_capturing(app, pa)

    # 
    # その他
    #
    def copy(self, string, spirit):
        """ @task
        クリップボードに文字列をコピーする。
        """
        spirit.clipboard_copy(string)

    #
    # コンストラクタ
    #


    
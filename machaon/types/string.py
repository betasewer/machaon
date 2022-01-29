import re
import string
from turtle import pos

class StrType():
    """ [fundamental] Pythonの文字列型。
    """
    def constructor(self, _context, v):
        """ @meta 
        Params:
            Any:
        """
        return str(v)
    
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
        return s.replace(old, new, count)

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

    def ispyident(self, s):
        """ @method 
        Pythonの識別名として使用できる文字。
        Returns:
            bool:
        """
        return s.isidentifier()

    #
    # 文字列を分解・合成する
    #
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
            chars: 落とす文字の指定
        Returns:
            Str:
        """
        return s.strip(chars)
    
    def lstrip(self, s, chars=None):
        """ @method
        文字の左脇の空白を落とす。
        Params:
            chars: 落とす文字の指定
        Returns:
            Str:
        """
        return s.lstrip(chars)

    def rstrip(self, s, chars=None):
        """ @method
        文字の右脇の空白を落とす。
        Params:
            chars: 落とす文字の指定
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
        from machaon.core.message import run_function
        r = run_function(s, subject, context, raiseerror=True)
        return r
    
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
        先頭に{name1 name2...}と書くことでモジュールをインポートできる。
        Returns:
            Any:
        """
        expr = expr.strip()
        if expr.startswith("{"):
            from machaon.core.importer import module_loader
            rparen = expr.find("}")
            if rparen == -1:
                raise ValueError("モジュール指定の括弧が閉じていません")
            imports = expr[1:rparen].split()
            body = expr[rparen+1:]
        else:
            imports = []
            body = expr

        glob = {}
        for impname in imports:
            loader = module_loader(impname)
            glob[impname] = loader.load_module()
        
        return eval(body, glob, {})
    
    def call_python(self, expr, _app, *params):
        """ @task alias-name [call]
        Pythonの関数または定数を評価する。
        Params:
            *params(Any): 引数
        Returns:
            Any:
        """
        from machaon.core.importer import attribute_loader
        loader = attribute_loader(expr)
        value = loader()
        if callable(value):
            return value(*params)
        else:
            # 引数は無視される
            return value
    
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
# サブタイプ
#
class RStrip:
    """ @type subtype
    固定の接尾辞を付す。
    BaseType:
        Str:
    """
    def constructor(self, context, s, postfix):
        """ @meta extraargs 
        Params:
            s(str):
            postfix(str):
        """
        i = s.rfind(postfix)
        if i == -1:
            return s
        return s[:i]
        
    def reflux(self, context, s, postfix):
        """ @meta extraargs 
        Params:
            s(Str):
            postfix(Str):
        """
        return s + postfix


class LStrip:
    """ @type subtype
    固定の接頭辞を付す。
    BaseType:
        Str:
    """
    def constructor(self, context, s, prefix):
        """ @meta extraargs 
        Params:
            s(Str):
            prefix(Str):
        """
        i = s.find(prefix)
        if i == -1:
            return s
        return s[i+len(prefix):]

    def reflux(self, s, prefix):
        """ @meta extraargs 
        Params:
            prefix(Str):
        """
        return prefix + s

class Strip:
    """ @type subtype
    前後に文字列を付す。
    BaseType:
        Str:
    """
    def constructor(self, context, s, prefix, postfix):
        """ @meta extraargs 
        Params:
            s(Str):
            prefix(Str):
            postfix(Str):
        """
        i = s.find(prefix)
        j = s.rfind(postfix)
        if i == -1:
            return s
        if i != -1 and j != -1:
            return s[i+len(prefix):j]
        elif j == -1:
            return s[i+len(prefix):]
        elif i == -1:
            return s[:j]
        else:
            return s
        
    def reflux(self, s, prefix, postfix):
        """ @meta extraargs 
        Params:
            prefix(Str):
            postfix(Str):
        """
        return prefix + s + postfix


    
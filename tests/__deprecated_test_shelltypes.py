
#
# 引数型
#
def test_simplex_complex():
    assert types.str.is_simplex_type()
    assert types.int.is_simplex_type()
    assert types.bool.is_simplex_type()
    assert types.float.is_simplex_type()
    assert types.complex.is_simplex_type()

    assert not types.separated_value_list.is_simplex_type()
    assert types.separated_value_list.is_compound_type()
    assert not types.separated_value_list.is_sequence_type()
    
    assert not types.filepath.is_simplex_type()
    assert types.filepath.is_compound_type()
    assert types.filepath.is_sequence_type()


def test_separated_list():
    csv_list = types.separated_value_list(sep=",")
    assert csv_list.convert_from_string("neko, inu, saru, azarashi") == ["neko", "inu", "saru", "azarashi"]

    int_list = types.separated_value_list(types.int)
    assert int_list.convert_from_string("1 -2 3 -4") == [1, -2, 3, -4]

def test_filepath():
    fpath = types.filepath
    ifpath = types.input_filepath
    dpath = types.dirpath
    idpath = types.input_dirpath

    # filepath
    from machaon.process import TempSpirit
    spi = TempSpirit(cd="basic")

    assert fpath.convert_from_string("users/desktop/memo.txt bin/appli.exe", spi) == [
        "basic\\users\\desktop\\memo.txt", "basic\\bin\\appli.exe"
    ]

    # input-filepath: globパターンを受け入れ、実在するパスを集める
    spi = TempSpirit(cd = "c:\\Windows")
    assert len(ifpath.convert_from_string("System32/*.dll py.exe", spi)) > 2

    #
    spi = TempSpirit(cd="users")
    assert dpath.convert_from_string("desktop/folder bin", spi) == [
        "users\\desktop\\folder", "users\\bin"
    ]

    #
    spi = TempSpirit(cd = "c:\\Windows")
    assert len(idpath.convert_from_string("system32/* system")) > 2



#
# --typeset 13Q 50x20 8H --typeset 11Q 6H
# pick
# kumiteisai 13Q 50x20 8H
# estimate <kumi> <xu.format.46> <layout>
# margin 4 6 7 8
"""
一つのコマンドのパラメータはすべて型が異なっている。
型によって実引数を適切な仮引数に振り分ける。

parameterという名のパラメータは特別扱いになり、渡された文字列がそのまま入る。

コマンドは任意個のオブジェクトを返すことができる。
オブジェクトは型ごとに一つのリストへ追加される。
リストを分けたいなら別の型にする。

def init_process(self, outfile, options):
    pass

def process_target(self, parameter):
    parts = parameter.split()
    ...
    self.app.yield_object(kumi_teisai(q, h, space))

def exit_process(self):
    pass


"""

"""
def describe_entry(signature):
    Typeset,
    CreateTypeset,
    TypesetConverter,


class Typeset:
    def __init__(self, *, q=None, space=None, length=None, count=None):
        self.q = q
        self.space = space
        self.line_length = length
        self.line_count = count
    
    @property
    def leading(self):
        if None in (self.space, self.q):
            return None
        return self.space + self.q
    
    @property
    def total_length(self):
        if None in (self.line_length, self.q):
            return None
        return self.q * self.line_length
    
    @property
    def total_width(self):
        if None in (self.line_count, self.q, self.space):
            return None
        return self.line_count * self.q + (self.line_count-1) * self.space
    
    def is_specified(self):
        return not any(x is None for x in (self.q, self.space, self.line_length, self.line_count))

    def display(self, app):
        values = {
            "q" : self.q,
            "llength" : self.line_length,
            "lcount" : self.line_count,
            "space" : self.space,
            "leading" : self.leading,
            "total_length" : self.total_length,
            "total_width" : self.total_width
        }
        for k, v in values.items():
            if v is None:
                values[k] = "？"

        app.message-em("{q}Q, {llength}字詰 {lcount}行, 行間{space}H（歯送{leading}H）".format(**values))
        tate = "  タテ：{total_length}H".format(**values)
        yoko = "  ヨコ：{total_width}H".format(**values)
        
        tate += "（{}mm）".format(h_to_mm(values["total_length"]))
        yoko += "（{}mm）".format(h_to_mm(values["total_width"]))

        if basic and basic.is_specified() and self.is_specified():
            tate += "［基本版面{:+}H］".format(self.total_length-basic.total_length)
            yoko += "［基本版面{:+}H］".format(self.total_width-basic.total_width)
        
        app.message(tate)
        app.message(yoko)

    def convert(self, other):
        # 字詰
        new_length1 = floor(self.total_length / other.q)
        new_count1 = floor((self.total_width + other.space) / other.leading)
        ts1 = Typeset(q=other.q, space=other.space, length=new_length1, count=new_count1)
        # 字詰
        new_length2 = ceil(self.total_length / other.q)
        new_count2 = ceil((self.total_width + other.space) / other.leading)
        ts2 = Typeset(q=other.q, space=other.space, length=new_length2, count=new_count2)
        return ts1, ts2
        
    @classmethod
    def describe_object(cls, signature):
        signature(
            "typeset",
            "版面"
        )["leading l"](
            "歯送り"
        )["q"](
            "級数"
        )["basic": "typeset"](
            "基本版面"
        )["pprint": "printer"](
            "詳細の表示"
        )
        

class CreateTypeset:
    def __call__(self, app, parameter) -> Typeset:
        q = None
        space = None
        length = None
        count = None

        parts = arg.split()
        for part in parts:
            if part.endswith(("Q","q","級")):
                q = int(part[:-1])
            elif part.endswith(("H","h","歯")):
                space = int(part[:-1])
            elif part.endswith(("L","l","行")):
                count = int(part[:-1])
            elif part.endswith(("C","c","字")):
                length = int(part[:-1])
            elif "x" in part or "X" in part:
                p1, _, p2 = part.partition("x")
                n1 = int(p1)
                n2 = int(p2)
                if n1 > n2:
                    length = n1
                    count = n2
                else:
                    length = n2
                    count = n1
            else:
                raise ValueError("解釈不能な値: '{}'".format(part))
        
        return Typeset(q=q, space=space, length=length, count=count)

    # describe_function -> __call__
    # 返ってきたオブジェクトをapp.yield_object(obj)し、可能ならobj.display(app)する。
    # Noneの場合は、何もしない。
    
    @classmethod
    def describe_function(cls, signature):
        signature(
        )["target": "parameter"](
            help="版面の級数、字詰、歯送[13Q 50x20 6H]",
        )["yield": "typeset"](
            help="生成された版面"
        )


class TypesetCalculator():
    def __call__(self, app, src, dest, format, typeset):        
        if format:
            hori = (format.width - grid.total_width) / 2
            vert = (format.height - grid.total_length ) / 2 #
            self.app.message("【{}判：余白】".format(format.name))
            self.app.message("　天地 {}mm".format(h_to_mm(vert)))
            self.app.message("　左右 {}mm".format(h_to_mm(hori)))
            self.app.message("")
        
        # 小さい
        new_length1 = floor(src.total_length / dest.q)
        new_count1 = floor((src.total_width + dest.space) / dest.leading)
        ts1 = Typeset(q=dest.q, space=dest.space, length=new_length1, count=new_count1, basic=src)

        # 大きい
        new_length2 = ceil(src.total_length / dest.q)
        new_count2 = ceil((src.total_width + dest.space) / dest.leading)
        ts2 = Typeset(q=dest.q, space=dest.space, length=new_length2, count=new_count2, basic=src)

        # ちょうどいい
        ts3 = None
        
        #
        self.app.title("{}Q 行間{}Hで、同一版面の候補".format(cvtgrid.q, cvtgrid.space))
        self.app.print_object(ts1, label="近い版面（内）")
        self.app.print_object(ts2, label="近い版面（外）")
        self.app.print_object(ts3, label="近い版面（近）")
    
    @classmethod
    def describe_function(cls, cmd):
        cmd.describe(
        )["target typeset src"](
            help="版面",
        )["target typeset dest"](
            help="変換したい版面の級数、歯送[11Q 8H]",
        )["target page-format format"](
            help="判型",
        )["yield typeset"](
            help="変換された完全な版面"
        )["yield page-margin"](
            help="変換後の余白"
        )

"""

#
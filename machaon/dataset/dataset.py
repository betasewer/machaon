from typing import Sequence, List, Any, Tuple, Dict, DefaultDict, Optional
from collections import defaultdict

from machaon.object.variable import variable, variable_defs
from machaon.object.operation import variable_valuerow_def
from machaon.dataset.filter import DataFilter
from machaon.dataset.sort import DataSortKey
from machaon.cui import get_text_width

#
#
#
class ResultIndexError(Exception):
    def __init__(self, count):
        self.count = count

    def __str__(self):
        if self.count is None:
            return "まだ検索していません"
        return "検索結果({}件)の範囲外です".format(self.count)

#
class InvalidColumnNames(Exception):
    def __init__(self, names):
        self.names = names

    def __str__(self):
        return "不明なカラム名です:{}".format(", ".join(self.names))

#
#
#
"""
class DataMethod():
    def __init__(self, name):
        self.name = name

    def __call__(self, item):
        p = getattr(item, self.name)
        return p()
"""

#
#
#
class DataReference():
    def __init__(self, *, itemclass):
        self.columns = variable_defs()
        self.itemclass: Any = itemclass

        self.defaultcolumns = {
            "table" : "long",
            "wide" : "short",
            "link" : "short",
        }
        self.columns.set_alias("long", "_top")
        self.columns.set_alias("short", "_top")

    # データアイテムのインターフェースを定義する構文
    def __getitem__(self, name_expr):        
        if isinstance(name_expr, slice):
            deftype = name_expr.stop
            names = name_expr.start.split()
        else:
            deftype = None
            names = name_expr.split()
        first_name = names[0]

        def parameters(
            disp="", 
            type=None,
            value=None,
            alias=None,
        ):
            if alias is not None:
                for n in names:
                    self.columns.set_alias(n, alias)
                return

            if value is None:
                method_name = first_name.replace("-","_")
                value = DataMethod(method_name)
            elif isinstance(value, str):
                method_name = value
                value = DataMethod(method_name)
            elif not callable(value):
                raise ValueError("DataReference.parameters.value")
            
            if type is None and deftype is not None:
                type = deftype

            self.columns.new(names, type, description=disp, value=value)
            return self

        return parameters

#
#
#
class DataView():
    def __init__(self, ref, datas, rows=None, viewtype=None, viewvars=None):
        self.ref = ref
        self.datas = datas
        self.rows = rows or []
        # 
        self.viewvars: List[variable] = viewvars or []
        self.viewtype: str = viewtype or "table"
        self.selecting: Optional[int] = None
    
    def assign(self, otherview):
        r = otherview
        self.ref = r.ref
        self.datas = r.datas
        self.rows = r.rows
        self.viewvars = r.viewvars
        self.viewtype = r.viewtype
        self.selecting = r.selecting
        return self

    # アクセス
    def row(self, i):
        _itemindex, row = self.rows[i]
        return row

    def valid_index(self, index):
        if not self.rows:
            return False
        return 0 <= index < len(self.rows)
    
    def count(self):
        return len(self.rows)
    
    def nothing(self):
        return not self.datas

    # 選択
    def select(self, index=None, *, advance=None):
        if index is None and advance is not None:
            index = self.selecting + advance

        if not self.valid_index(index):
            raise ResultIndexError(len(self.rows))
        else:
            self.selecting = index

    def deselect(self):
        self.selecting = None

    def selection(self):
        return self.selecting
    
    def selection_item(self):
        if self.selecting is None:
            return None
        return self.datas[self.selecting]
    
    #
    def get_viewtype(self):
        return self.viewtype

    def set_viewtype(self, viewtype):
        self.viewtype = viewtype
    
    #
    def get_current_columns(self) -> List[variable]:
        return self.viewvars
    
    def get_all_columns(self) -> List[variable]:
        if self.ref is None:
            return []
        return self.ref.columns.getall()
    
    def find_column(self, name) -> Optional[variable]:
        return self.ref.columns.get(name)
    
    def get_first_column(self) -> variable:
        return self.ref.columns.top_entry()
    
    def get_link_column(self) -> variable:
        e = self.ref.columns.selectone("link")
        if e:
            return e
        return self.get_first_column()

    def get_default_columns(self) -> List[variable]:
        c = self.ref.get_default_columnname(self.viewtype)
        es, _ = self.ref.columns.select(c)
        if es:
            return es
        else:
            return [self.ref.columns.get_first_column()] # 先頭カラム

    #
    #
    #
    def rows_to_string_table(self) -> Tuple[
        List[Tuple[int, List[str]]], 
        List[int]
    ]:
        colwidth = [0 for _ in self.viewvars]
        srows = []
        for itemindex, row in self.rows:
            srow = ["" for _ in self.viewvars]
            for i, va in enumerate(self.viewvars):
                s = va.predicate.value_to_string(row[i])
                srow[i] = s
                colwidth[i] = max(colwidth[i], get_text_width(s))
            srows.append((itemindex, srow))
        return srows, colwidth

    #
    # べつのビューを作る
    #
    def create_view(self, viewtype, column_names=None, filter=None, sortkey=None, *, trunc=True):
        # 空のデータからは空のビューしか作られない
        if not self.datas:
            return DataView(self.ref, [])

        # 列の変数を取得する
        if column_names:
            columns, invalids = self.ref.columns.select(column_names)
            if invalids:
                raise InvalidColumnNames(invalids)
        else:
            columns = self.get_default_columns()

        # 一行で使用する変数の並びを決める
        rowdef = variable_valuerow_def(self.viewvars)
        _newcolumn_indices = rowdef.register_variables(columns)
        if filter:
            filter_indices = rowdef.register_variables(filter.get_related_variables())
        if sortkey:
            sort_indices = rowdef.register_variables(sortkey.get_related_variables())

        # データを展開する
        if trunc:
            rows = [(i, rowdef.make_valuerow(item)) for i, item in enumerate(self.datas)]
        else:
            newvars = rowdef.get_variables()[len(self.viewvars):]
            if newvars:
                # 足りない列を新しく計算して結合する
                newrowdef = variable_valuerow_def(newvars)
                newrows = [(i, newrowdef.make_valuerow(self.datas[i])) for i, row in self.rows]
                rows = [(i, row1+row2) for (i, row1), (_, row2) in zip(self.rows, newrows)]
            else:
                rows = self.rows
        
        # 関数を適用する
        if filter:
            # 関連するカラムの値を渡し、判定
            rows = [r for r in rows if filter(filter_indices.make_context(r))]
        if sortkey:
            def key(row):
                # 同じく、関連するカラムの値を渡し、判定
                return sortkey(sort_indices.make_context(row))
            rows.sort(key=key)

        return DataView(self.ref, self.datas, rows, viewtype, rowdef.get_variables())
    
    # /v name path date /where date within 2015y 2017y /sortby ~date name /list
    # コマンドからビューを作成する
    #
    # syntax:
    # <column-name>... ? <column-name> <filter-operator> <?args...> @ <column-name> <?sort-operator>
    # :list name path date ? date within 2015/04/08 2016/01/03
    def command_create_view(self, expression=None, *, trunc=True, filter_query=None, sort_query=None):
        dispmode = False

        # コマンド文字列を解析する
        column_part = None
        viewtype_part = None
        filter_part = None
        sorter_part = None
        parts = []
        if expression:
            parts = expression.split("/")
            for i, part in enumerate(parts):
                if part.startswith("where"):
                    filter_part = part[len("where"):].strip()
                elif part.startswith("sortby"):
                    sorter_part = part[len("sortby"):].strip()
                elif part.startswith("pred"):
                    column_part = part[len("pred"):].strip()
                elif i == 0:
                    column_part = part.strip()
                elif part and not part.startswith(" "):
                    viewtype_part = part.strip()
        
        # 表の表示形式
        if viewtype_part is not None:
            viewtype = viewtype_part
            if viewtype == "disp":
                dispmode = True
                viewtype = self.viewtype
        else:
            viewtype = self.viewtype

        # 述語リスト
        if column_part is not None:
            columns = column_part.split()
        else:
            columns = [] # デフォルトのカラムになる

        # フィルタ指示
        filter_ = None
        if filter_part is not None:
            filter_query = filter_part
        if filter_query:
            filter_ = DataFilter(self.ref, filter_query, dispmode)
            if filter_.failure:
                raise filter_.failure

        # ソート指示
        sortkey = None
        if sorter_part is not None:
            sort_query = sorter_part # /sortby を落とす
        if sort_query:
            sortkey = DataSortKey(self.ref, sort_query, dispmode)

        # 新たなビューを構築する
        return self.create_view(viewtype, columns, filter_, sortkey, trunc=trunc)

#
#
#
class _DataViewFactory():
    def __init__(self):
        self.refs = {}

    def get_reference(self, dataclass):
        """ データクラスが未登録なら、登録する """
        ref = self.refs.get(dataclass.__name__, None)
        if ref is None:
            ref = DataReference(itemclass=dataclass)
            dataclass.describe(ref)
            self.refs[dataclass.__name__] = ref
        return ref

    def __call__(self, items, *command_args, **command_kwargs):
        if not items:
            return DataView(None, []) # 空のビュー   
        firstitem = items[0]
        ref = self.get_reference(type(firstitem))
        dataview = DataView(ref, datas=items)
        return dataview.command_create_view(*command_args, **command_kwargs)

#
DataViewFactory = _DataViewFactory()

"""
dref = describe_data_reference(
    description=""
)
["name n"](
    help="card name",
    type=str,
    value=lambda e:e.name
)
["name n"](
    help="card name",
    type=str,
    value=lambda e:e.name,
)
["#wiki w"](
    value=cls.view_as_wiki,
    help="",
)

def view_as_wiki(app):
    app.


?[predicate] [operator] [parameter...]

%
　直前のプロセスのデータを表示
  デフォルトのカラムを用いる
% name type --process 4
　4番目のプロセスのデータを、name type欄でリスト表示する
% name ? attack > 2500
  attackが2500以上であるアイテムのnameを取得する
% name type --select 4
　name type欄でリスト表示し、4番目を選択する

%name ?attack > 2500
@wikilike

dataset = select_dataset(app, index)
item = dataset.selection()
item = select_dataset_item(app, index, YgoproCard)

hex128
@wikilike
carddb
cardwiki
cardscript
cardpic

carddb 100001
hex 


"""



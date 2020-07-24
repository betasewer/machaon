from typing import Sequence, List, Any, Tuple, Dict, DefaultDict, Optional, Generator
from collections import defaultdict

from machaon.object.type import TypeTraits, TypeMethod
from machaon.object.desktop import ObjectDesktop
from machaon.object.conditional import EvalContext, parse_conditional
from machaon.object.operator import parse_operator_expression
from machaon.dataset.sort import parse_sortkey
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
class DataColumn():
    def __init__(self, method, type):
        self.method = method
        self.type = type

    def get_name(self):
        return self.method.get_name()
    
    def get_help(self):
        return self.method.get_help()
    
    def make_value_string(self, value):
        return self.type.convert_to_string(value)
    
    def make_value(self, subject):
        return self.method.call(self.type, subject) # 引数なしで呼び出す
    
    def make_compare_operator(self, lessthan=True):
        if lessthan:
            return parse_operator_expression("lt", self.type)
        else:
            return parse_operator_expression("!lt", self.type)

#
#
#
class DataView():
    def __init__(self, itemtype, items, valuerows=None, viewtype=None, viewcolumns=None):
        self.itemtype = itemtype
        self.items = items
        self.rows = valuerows or []
        # 
        self.viewcols: List[DataColumn] = viewcolumns or []
        self.viewtype: str = viewtype or "table"
        self.selecting: Optional[int] = None
    
    def assign(self, otherview):
        r = otherview
        self.itemtype = r.itemtype
        self.items = r.items
        self.rows = r.rows
        self.viewcolumns = r.viewcolumns
        self.viewtype = r.viewtype
        self.selecting = r.selecting
        return self

    # メンバ値へのアクセス
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
        return not self.items

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
        return self.items[self.selecting]
    
    #
    def get_viewtype(self):
        return self.viewtype

    def set_viewtype(self, viewtype):
        self.viewtype = viewtype
    
    # アイテムのメンバを表の列とする
    def get_item_type(self) -> TypeTraits:
        return self.itemtype

    def all_item_members(self) -> Generator[TypeMethod, None, None]:
        if self.itemtype is None:
            return
        for meth in self.itemtype.enum_methods(arity=1):
            yield meth
    
    def make_column(self, name, objdesk: ObjectDesktop) -> Optional[DataColumn]:
        meth = self.itemtype.get_method(name)
        if meth:
            coltype = objdesk.get_type(meth.get_result_codetype())
            col = DataColumn(meth, coltype)
            return col
        else:
            return None
    
    def get_current_columns(self) -> List[DataColumn]:
        return self.viewcolumns
    
    def get_top_column_name(self) -> Optional[str]:
        a = self.itemtype.get_method_alias("view-top")
        if a is None:
            for meth in self.itemtype.enum_methods(arity=1):
                return meth.name
        return None
    
    def get_link_column_name(self) -> Optional[str]:
        a = self.itemtype.get_method_alias("view-link")
        if a is None:        
            return self.itemtype.get_method_alias("view-top")
        return None

    def get_default_column_names(self) -> List[str]:
        alias = self.itemtype.get_method_alias("view-set-{}".format(self.viewtype))
        if alias:
            names = alias.split()
            return names
        else:
            alias = self.itemtype.get_method_alias("view-top") # 先頭カラム
            if alias:
                return [alias]
            return [] 

    # 計算済みのメンバ値をすべて文字列へ変換する
    def rows_to_string_table(self) -> Tuple[
        List[Tuple[int, List[str]]],    # 文字列にした一行ともとの行番号からなる表
        List[int]                       # 各列ごとの、文字列の最大長
    ]:
        colwidth = [0 for _ in self.viewcolumns]
        srows = []
        for itemindex, row in self.rows:
            srow = ["" for _ in self.viewcolumns]
            for i, column in enumerate(self.viewcolumns):
                s = column.make_value_string(row[i])
                srow[i] = s
                colwidth[i] = max(colwidth[i], get_text_width(s))
            srows.append((itemindex, srow))
        return srows, colwidth

    #
    # 新しい条件でビューを作る
    #
    def create_view(self, objdesk, viewtype, column_names=None, filter=None, sortkey=None, *, trunc=True):
        # 空のデータからは空のビューしか作られない
        if not self.items:
            return DataView(self.itemtype, [])

        # ユーザー指定の列を構築する
        if not column_names:
            column_names = self.get_default_column_names()

        columns = []
        invalids = []
        for column in column_names:
            col = self.make_column(column, objdesk)
            if col is None:
                invalids.append(column)
            else:
                columns.append(col)
        if invalids:
            raise InvalidColumnNames(invalids)

        # 使用する全ての列を決定する
        rowindexer = DataViewRowIndexer(self.viewcolumns)
        _newcolumn_indices = rowindexer.create_column_indexrow(columns)
        if filter:
            filter_col_indexrow = rowindexer.create_column_indexrow(filter.get_related_members())
        if sortkey:
            sort_col_indexrow = rowindexer.create_column_indexrow(sortkey.get_related_members())
        
        columns, newcolumns = rowindexer.create_columns(self, objdesk)

        # データを展開する
        if trunc:
            # すべて新たに計算する
            newcolumns = columns + newcolumns
            self.rows = []
        
        if newcolumns:
            # 新たに値を計算
            newrows = []
            for rowindex, item in enumerate(self.items):
                row = []
                for column in newcolumns:
                    val = column.make_value(item)
                    row.append(val)
                newrows.append((rowindex, row))
            # 列を後ろに結合
            rows = [(i, row1+row2) for (i, row1), (_, row2) in zip(self.rows, newrows)]
        else:
            rows = self.rows
            
        # 
        def conditional_context(indicesmap, row: List[Any]):
            valuemap = {k:row[i] for k,i in indicesmap.items()}
            return EvalContext(valuemap)

        # 関数を適用する
        if filter:
            # 関連するカラムの値を渡し、判定
            rows = [row for row in rows if filter(conditional_context(filter_col_indexrow, row))]

        if sortkey:
            def key(row):
                # 同じく、関連するカラムの値を渡し、判定
                return sortkey(conditional_context(sort_col_indexrow, row))
            rows.sort(key=key)

        return DataView(self.itemtype, self.items, rows, viewtype, columns)
    
    # /v name path date /where date within 2015y 2017y /sortby ~date name /list
    # コマンドからビューを作成する
    #
    # syntax:
    # <column-name>... ? <column-name> <filter-operator> <?args...> @ <column-name> <?sort-operator>
    # :list name path date ? date within 2015/04/08 2016/01/03
    def command_create_view(self, objdesk, expression=None, *, trunc=True, filter_query=None, sort_query=None):
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
            filter_ = parse_conditional(filter_query, self.itemtype, objdesk)

        # ソート指示
        sortkey = None
        if sorter_part is not None:
            sort_query = sorter_part # /sortby を落とす
        if sort_query:
            sortkey = parse_sortkey(sort_query, self, objdesk)

        # 新たなビューを構築する
        return self.create_view(viewtype, columns, filter_, sortkey, trunc=trunc)


#
# 実行コンテキストをつくる
#
class DataViewRowIndexer():
    def __init__(self, columns: Sequence[DataColumn]):
        self.columns: List[DataColumn] = [*columns]
        self._new_columnnames: List[str] = []
    
    # 登録し、キャッシュのインデックスを返す
    def create_column_indexrow(self, column_names: Sequence[str]) -> Dict[str, int]: # {column_name : index}
        indicemap: Dict[str, int] = {}
        for colname in column_names:
            for i, col in enumerate(self.columns):
                if col.get_name() == colname:
                    index = i
                    break
            else:
                self._new_columnnames.append(colname)
                index = len(self.columns)+len(self._new_columnnames)-1

            indicemap[colname] = index
        return indicemap

    # 新規追加されたものを含め、カラムを作成する
    def create_columns(self, dataview, objdesk):
        oldcols = [*self.columns]
        cols = []
        for newcolname in self._new_columnnames:
            col = dataview.make_column(newcolname, objdesk)
            cols.append(col)
        self.columns.extend(cols)
        self._new_columnnames.clear()
        return oldcols, cols
        
#
#
#
def create_dataview(objdesk, items, *command_args, itemtypecode=None, **command_kwargs):
    if itemtypecode is None:
        if items:
            itemtypecode = type(items[0])
    itemtype = objdesk.get_type(itemtypecode)
    dataview = DataView(itemtype, items)
    return dataview.command_create_view(*command_args, **command_kwargs)


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



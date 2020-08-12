from typing import Sequence, List, Any, Tuple, Dict, DefaultDict, Optional, Generator, Iterable
from collections import defaultdict

from machaon.object.type import TypeTraits, TypeModule
from machaon.object.object import Object
from machaon.object.invocation import MemberInvocationContext, select_type_method, select_method
from machaon.object.formula import ValuesEvalContext, parse_formula
from machaon.object.sort import parse_sortkey
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
    def __init__(self, method_inv, type):
        self.method_inv = method_inv
        self.type = type
    
    @property
    def method(self):
        return self.method_inv.method

    def get_name(self):
        return self.method.get_name()
    
    def get_help(self):
        return self.method.get_help()
    
    def make_value_string(self, value):
        return self.type.convert_to_string(value)
    
    def make_value(self, cxt: MemberInvocationContext):
        self.method_inv.invoke(cxt)
        return cxt.get_evaluated_value()
    
    def make_compare_operator(self, lessthan=True):
        if lessthan:
            return select_method("lt", self.type, arity=2, return_type="bool")
        else:
            return select_method("!lt", self.type, arity=2, return_type="bool")

#
def make_data_columns(type, typemodule: TypeModule, *member_names) -> List[DataColumn]:
    columns = []
    invalid_names = []

    names: List[str] = []
    for member_name in member_names:
        aliases = type.get_method_alias(member_name)
        if aliases is not None:
            names.extend(aliases)
        else:
            names.append(member_name)

    for member_name in names:
        methinv = select_type_method(member_name, type)
        if methinv:
            rtype = methinv.method.get_first_result_typename()
            if rtype is None:
                raise ValueError("データカラムで表示しようとしたメソッド'{}'が値を返しません".format(member_name))
            coltype = typemodule.new(rtype)
            columns.append(DataColumn(methinv, coltype))
        else:
            invalid_names.append(member_name)

    if invalid_names:
        raise InvalidColumnNames(invalid_names)
    return columns

#
#
#
class DataView():
    def __init__(self, itemtype, items, rows=None, viewtype=None, viewcolumns=None):
        self.itemtype = itemtype
        self.items = items
        self.rows = rows or []
        self.viewcolumns: List[DataColumn] = viewcolumns or []
        self.viewtype: str = viewtype or "table"

        self._selection: Optional[Tuple[int, int]] = None # itemindex, rowindex

    def assign(self, otherview):
        r = otherview
        self.itemtype = r.itemtype
        self.items = r.items
        self.rows = r.rows
        self.viewcolumns = r.viewcolumns
        self.viewtype = r.viewtype
        self._selection = r._selection
        return self

    # メンバ値へのアクセス
    def row(self, index):
        _itemindex, row = self.rows[index]
        return row
    
    def row_from_item(self, itemindex) -> Optional[int]:
        # 素朴に線形で探索
        for irow, (iitem, _row) in enumerate(self.rows):
            if iitem == itemindex:
                return irow
        return None
    
    def item_from_row(self, rowindex) -> int:
        return self.rows[rowindex][0]
    
    def count(self):
        return len(self.rows)
    
    def nothing(self):
        return not self.items

    # 選択
    def select(self, rowindex) -> bool:
        if 0 <= rowindex < len(self.rows):
            itemindex = self.rows[rowindex][0]
            self._selection = (itemindex, rowindex)
            return True
        return False

    def select_by_item(self, itemindex) -> bool:
        if 0 <= itemindex < len(self.items):
            rowindex = self.row_from_item(itemindex)
            if rowindex is not None:
                self._selection = (itemindex, rowindex)
                return True
        return False
    
    def deselect(self):
        self._selection = None

    def selection(self): # rowindexを返す
        if self._selection is None:
            return None
        return self._selection[1]
    
    def selection_item(self):
        if self._selection is None:
            return None
        return self.items[self._selection[0]]

    def selection_row(self):
        if self._selection is None:
            return None
        _index, row = self.rows[self._selection[1]]
        return row

    #
    def get_viewtype(self):
        return self.viewtype

    def set_viewtype(self, viewtype):
        self.viewtype = viewtype
    
    # アイテムのメンバを表の列とする
    def get_item_type(self) -> TypeTraits:
        return self.itemtype
    
    def get_current_columns(self) -> List[DataColumn]:
        return self.viewcolumns
    
    def find_current_column(self, name) -> Optional[DataColumn]:
        for c in self.viewcolumns:
            if c.get_name() == name:
                return c
        return None
    
    def new_current_column(self, objectdesk, name):
        cols = make_data_columns(self.itemtype, objectdesk, name)
        self.viewcolumns.append(cols[0])
    
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
            name = self.get_top_column_name() # 先頭カラム
            if name is not None:
                return [name]
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
    def create_view(self, 
        typemodule: TypeModule, 
        viewtype: str, 
        column_names=None, 
        filterformula=None, 
        sortkey=None, 
        *, 
        trunc=True
    ):
        # 空のデータからは空のビューしか作られない
        if not self.items:
            return DataView(self.itemtype, [])

        # ユーザー指定の列を構築する
        if not column_names:
            column_names = self.get_default_column_names()

        # 使用する全ての列を決定する
        cur_column_names = [x.get_name() for x in self.viewcolumns]
        rowindexer = DataViewRowIndexer(cur_column_names)
        _newcolumn_indices = rowindexer.create_column_indexmap(column_names)
        if filterformula:
            filter_col_indexmap = rowindexer.create_column_indexmap(filterformula.get_related_members())
        if sortkey:
            sort_col_indexmap = rowindexer.create_column_indexmap(sortkey.get_related_members())
        
        # 列を新規作成  使用しない列は削除？
        new_column_names = rowindexer.pop_new_columns()
        columns = make_data_columns(self.itemtype, typemodule, *cur_column_names, *new_column_names)

        # データを展開する
        newrowlayout: Iterable[Tuple[int, List[Any]]]
        if trunc:
            # すべて新たに計算する
            newcolumns = columns
            newrowlayout = ((index,[]) for (index,_) in enumerate(self.items))
        else:
            # 新規追加された欄のみ
            newcolumns = columns[len(cur_column_names):]
            newrowlayout = iter(self.rows) # 現在使用されているアイテムに結合

        if newcolumns:
            # 新たに値を計算
            newrows = []
            for itemindex, currow in newrowlayout:
                newrow = []
                item = self.items[itemindex]
                inv = MemberInvocationContext(self.itemtype, item)
                for column in newcolumns:
                    val = column.make_value(inv)
                    newrow.append(val)
                newrows.append((itemindex, currow+newrow)) # 既存の行の後ろに結合
            rows = newrows
        else:
            rows = self.rows
        
        # ひとまず新しいビューのインスタンスを作成
        dataview = DataView(self.itemtype, self.items, rows, viewtype, columns)

        def formula_context(indicesmap, row: List[Any]):
            valuemap = {k:row[i] for k,i in indicesmap.items()}
            return ValuesEvalContext(valuemap)

        # 関数を行に適用する
        if filterformula:
            def fn(entry):
                _index, row = entry
                return filterformula(formula_context(filter_col_indexmap, row))
            rows = list(filter(fn, rows))

        if sortkey:
            sortkey.setup_operators(dataview) # 新しいカラムから演算子を決める
            def key(entry):
                _index, row = entry
                return sortkey(formula_context(sort_col_indexmap, row))
            rows.sort(key=key)
        
        dataview.rows = rows
        
        # 選択を引き継ぐ
        if self._selection is not None:
            itemindex, _rowindex = self._selection
            dataview.select_by_item(itemindex)
            
        return dataview

#
# 実行コンテキストをつくる
#
class DataViewRowIndexer():
    def __init__(self, column_names: Sequence[str]):
        self._columnnames: List[str] = [*column_names]
        self._new_columnnames: List[str] = []
    
    # 登録し、キャッシュのインデックスを返す
    def create_column_indexmap(self, column_names: Sequence[str]) -> Dict[str, int]: # {column_name : index}
        indicemap: Dict[str, int] = {}
        for colname in column_names:
            for i, curcolname in enumerate(self._columnnames):
                if curcolname == colname:
                    index = i
                    break
            else:
                self._new_columnnames.append(colname)
                self._columnnames.append(colname)
                index = len(self._columnnames)-1

            indicemap[colname] = index
        return indicemap

    # 新規追加されたカラム名を返し、バッファを空にする
    def pop_new_columns(self) -> List[str]:
        newcols = self._new_columnnames[:]
        self._new_columnnames.clear()
        return newcols
        
#
#
#
def parse_new_dataview(typemodule, items, expression=None, *, itemtype=None, filter_query=None, sort_query=None):
    if itemtype is None:
        if not items:
            raise ValueError("アイテムの型を推定できません")
        itemtype = type(items[0])
    item_t = typemodule.new(itemtype)
    dataview = DataView(item_t, items)
    return parse_dataview(typemodule, dataview, expression, trunc=True, filter_query=filter_query, sort_query=sort_query)

#
#
# コマンドからビューを作成する
# /v name path date /where date within 2015y 2017y /sortby ~date name /list
#
def parse_dataview(typemodule, dataview, expression=None, *, trunc=True, filter_query=None, sort_query=None):
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
    else:
        viewtype = dataview.viewtype

    # 述語リスト
    if column_part is not None:
        columns = column_part.split()
    else:
        columns = [] # デフォルトのカラムになる

    # フィルタ指示
    if filter_part is not None:
        filter_query = filter_part

    filter_ = None
    if filter_query:
        filter_ = parse_formula(filter_query, typemodule, dataview.itemtype)

    # ソート指示
    if sorter_part is not None:
        sort_query = sorter_part

    sortkey = None
    if sort_query:
        sortkey = parse_sortkey(sort_query)

    # 新たなビューを構築する
    return dataview.create_view(typemodule, viewtype, columns, filter_, sortkey, trunc=trunc)


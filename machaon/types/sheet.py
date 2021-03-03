from typing import Sequence, List, Any, Tuple, Dict, DefaultDict, Optional, Generator, Iterable, Union
from collections import defaultdict

from machaon.core.type import Type, TypeModule
from machaon.core.object import Object
from machaon.core.message import MessageEngine, MemberGetter, select_method
from machaon.core.invocation import InvocationContext
from machaon.process import ProcessError
from machaon.cui import get_text_width

from machaon.types.tuple import ObjectTuple, ElemObject
from machaon.types.fundamental import NotFound

#
#
#
class NotSelected(Exception):
    def __str__(self):
        return "選択がありません"

class InvalidColumnNames(Exception):
    def __init__(self, names):
        self.names = names

    def __str__(self):
        return "不明なカラム名です:{}".format(", ".join(self.names))

#
DATASET_STRINGIFY = 0
DATASET_STRINGIFY_SUMMARIZE = 1

#
#
#
class DataColumn():
    def __init__(self, function, typename=None, *, name=None):
        self._getter = function
        self._typename = typename
        self._name = name
        self._t = None
    
    def get_name(self):
        if self._name is None:
            return self._getter.get_expression()
        return self._name
    
    def get_type(self, context):
        if self._t is None:
            self._t = context.select_type(self._typename or "Any")
        return self._t
    
    def get_function(self):
        return self._getter
    
    def is_nonstring_column(self):
        return self._typename and self._typename != "Str" and self._typename != "Any"
    
    def eval(self, subject, context):
        obj = self._getter.run_function(subject, context)
        if self._typename is None and not obj.is_error(): # 型を記憶する
            self._typename = obj.get_typename()
            self._t = obj.type
        return obj.value
    
    def stringify(self, context, value, method=DATASET_STRINGIFY):
        if isinstance(value, ProcessError):
            return "<error: {}>".format(value.summarize())
        if method == DATASET_STRINGIFY_SUMMARIZE:
            return self.get_type(context).summarize_value(value)
        else:
            return self.get_type(context).convert_to_string(value)

    def make_compare_operator(self, context, lessthan=True):
        typ = self.get_type(context)
        if lessthan:
            inv = select_method("lt", typ)
        else:
            inv = select_method("!lt", typ)
        if inv is None:
            return None
        inv.set_result_typehint("Bool")
        return inv

#
class DataItemItselfColumn():
    def __init__(self, type):
        self.type = type
    
    @property
    def method(self):
        return None

    def get_name(self):
        return "="
    
    def get_doc(self):
        return "要素"
    
    def get_type(self, _context):
        return self.type
    
    def eval(self, subject, _context):
        return subject
    
    def is_nonstring_column(self):
        return not self.type.is_any() and self.type.get_typename() != "Str"
    
    def stringify(self, context, value, method=DATASET_STRINGIFY):
        if method == DATASET_STRINGIFY_SUMMARIZE:
            return self.get_type(context).summarize_value(value)
        else:
            return self.get_type(context).convert_to_string(value)

    def make_compare_operator(self, _context, lessthan=True):
        if lessthan:
            inv = select_method("lt", self.type)
        else:
            inv = select_method("!lt", self.type)
        if inv is None:
            return None
        inv.set_result_typehint("Bool")
        return inv

#
DataColumnUnion = Union[DataColumn, DataItemItselfColumn]

#
def make_data_columns(type, *expressions) -> List[DataColumnUnion]:
    columns: List[DataColumnUnion] = []
    invalid_names = []

    names: List[str] = []
    for expr in expressions:
        aliases = type.get_member_group(expr)
        if aliases is not None:
            names.extend(aliases)
        else:
            names.append(expr)

    for member_name in names:
        if member_name == "=":
            columns.append(DataItemItselfColumn(type))
            continue

        methinv = select_method(member_name, type)
        if methinv:
            fn = MemberGetter(member_name, methinv)
            specs = methinv.get_result_specs()
            col = DataColumn(fn, specs[0].get_typename())
            columns.append(col)
        else:
            invalid_names.append(member_name)

    if invalid_names:
        raise InvalidColumnNames(invalid_names)
    return columns

#
SEARCH_METHOD_EQUAL = 1
SEARCH_METHOD_FORWARD_MATCH = 2
SEARCH_METHOD_BACKWARD_MATCH = 3
SEARCH_METHOD_PARTIAL_MATCH = 4

def make_data_search_predicate(code, column, bound_context):
    if code == SEARCH_METHOD_EQUAL:
        def pred(l, r):
            return l == r
    elif code == SEARCH_METHOD_FORWARD_MATCH:
        def pred(l, r):
            return column.stringify(bound_context, l).startswith(r)
    elif code == SEARCH_METHOD_BACKWARD_MATCH:
        def pred(l, r):
            return column.stringify(bound_context, l).endswith(r)
    elif code == SEARCH_METHOD_PARTIAL_MATCH:
        def pred(l, r):
            return r in column.stringify(bound_context, l)
    else:
        raise ValueError("Unknown search method")
    
    return pred

#
#
#
class Sheet():  
    """ @type
    同じ型のオブジェクトに対する式を縦列とするデータの配列。
    Typename: Sheet
    """
    def __init__(self, items, itemtype, context=None, column_names=None, viewtype=None, *, uninitialized=False):
        self.itemtype = itemtype
        self.items = items
        self.rows = []
        self.viewcolumns: List[DataColumnUnion] = []
        self.viewtype: str = viewtype or "table"

        self._selection: Optional[Tuple[int, int]] = None # itemindex, rowindex

        if not uninitialized:
            if not context or not column_names:
                self.generate_rows_identical()
            else:
                new_columns = make_data_columns(self.itemtype, *column_names)
                self.generate_rows(context, new_columns)
    
    # アイテムにアクセスする
    def __iter__(self):
        return self.current_items()

    #
    # メンバ値へのアクセス
    #
    def at(self, row):
        """ @method [#]
        アイテムオブジェクトを行インデックスで指定して取得する。
        Params:
            row(int): 行インデックス
        Returns:
            Object: 値
        """
        itemindex, _r = self.rows[row]
        item = self.items[itemindex]
        return Object(self.itemtype, item)
    
    def top(self):
        """ @method [t]
        0番目のアイテムオブジェクトを取得する。
        Returns:
            Object: 値
        """
        return self.at(0)
    
    def last(self):
        """ @method [l]
        最後のアイテムオブジェクトを取得する。
        Returns:
            Object: 値
        """
        return self.at(-1)
    
    def get(self, context, column, row):
        """ @method context
        値をカラム名と行インデックスで指定して取得する。
        Params:
            column(str): 列名
            row(int): 行インデックス
        Returns:
            Object: 値
        """
        itemindex, r = self.rows[row]
        icol, col = self.select_column(column)
        if icol == -1:
            val = col.eval(self.items[itemindex], context)
        else:
            val = r[icol]

        valtype = col.get_type(context)
        return Object(valtype, val)
    
    def find(self, context, app, column, value):
        """ @method task context
        値をカラム名とインデックスで指定して取得する。
        Params:
            column(str): 列名+一致タイプ指定（前方*／*後方／*部分*）
            value(Any): 検索する値
        Returns:
            ElemObject: 値
        """
        # 一致タイプ
        method = SEARCH_METHOD_PARTIAL_MATCH
        if len(column)>1:
            if column[0] == "#": 
                method = SEARCH_METHOD_EQUAL
                column = column[1:-1]
            elif column[0] == "*":
                method = SEARCH_METHOD_BACKWARD_MATCH
                column = column[1:]
            elif column[-1] == "*":
                method = SEARCH_METHOD_FORWARD_MATCH
                column = column[:-1]
        
        icol, col = self.select_column(column)
        if col.is_nonstring_column():
            method = SEARCH_METHOD_EQUAL

        pred = make_data_search_predicate(method, col, context)
        
        # 順に検索
        for ival, obj in enumerate(self.column_values(context, icol, col)):
            if pred(obj.value, value):
                item = self.items[self.get_item_from_row(ival)]
                index = context.new_object("Int", ival)
                ovalue = col.get_type(context).new_object(obj.value)
                return ElemObject(item, index, ovalue)

        raise NotFound() # 見つからなかった

    def get_row(self, index):
        """ 行を取得する。 """
        _itemindex, row = self.rows[index]
        return row
    
    def get_row_from_item(self, itemindex) -> int:
        """ アイテムIDから行番号を取得する。 線形探索を行う。"""
        for irow, (iitem, _row) in enumerate(self.rows):
            if iitem == itemindex:
                return irow
        raise ValueError("Invalid item index")
    
    def get_item_from_row(self, rowindex) -> int:
        """ 行番号からアイテムIDを取得する。"""
        iitem, _row = self.rows[rowindex]
        return iitem

    def current_rows(self):
        """ 現在あるすべての行を取得する。 """
        for itemindex, rows in self.rows:
            yield itemindex, rows
    
    def current_items(self):
        """ 現在あるすべての行のアイテムを取得する。 """
        for itemindex, _ in self.rows:
            yield self.items[itemindex]

    def column_values(self, context, index, column=None):
        """ @method context
        ある列をタプルにして得る。
        Params:
            column(Str): カラム名
        Returns:
            Tuple:
        """
        if column is None:
            icol, col = self.select_column(index)
        else:
            icol, col = index, column

        if icol == -1:
            # 新しいカラムを増やす
            self.generate_rows_concat(context, [col])
            icol = len(self.viewcolumns)
            self.viewcolumns.append(col)

        valtype = col.get_type(context)
        for itemindex, _row in self.rows:
            subject = Object(self.itemtype, self.items[itemindex])
            value = col.eval(subject, context)
            yield Object(valtype, value)
    
    #
    # シーケンス関数
    # 
    def append(self, context, *items):
        """ @method context
        アイテムを追加する。
        Params:
            *items: 
        """
        self.items.extend(items)
        self.append_generate_rows(context, items)

    def count(self):
        """ @method [len]
        行の数を取得する。
        Params:
        Returns:
            int: 個数
        """
        return len(self.rows)

    # 選択
    def select(self, rowindex):
        """ @method
        インデックスによって指定した行を選択する。
        Params:
            rowindex(int): 行インデックス
        Returns:
            bool: 選択できたか
        """
        if 0 <= rowindex < len(self.rows):
            itemindex = self.rows[rowindex][0]
            self._selection = (itemindex, rowindex)
            return True
        return False

    def select_by_item(self, itemindex):
        """ @method
        アイテムIDによって指定した行を選択する。
        Params:
            itemindex(int): アイテムID
        Returns:
            bool: 選択できたか
        """
        if 0 <= itemindex < len(self.items):
            rowindex = self.get_row_from_item(itemindex)
            if rowindex is not None:
                self._selection = (itemindex, rowindex)
                return True
        return False
    
    def deselect(self):
        """ @method
        選択を解除する。
        Returns: 
            Self:
        """
        self._selection = None

    def selection(self):
        """ @method [sel]
        選択中のアイテムを得る。
        Returns:
            Object: アイテム
        """
        if self._selection is None:
            raise NotSelected()
        return Object(self.itemtype, self.items[self._selection[0]])

    def selection_index(self):
        """ @method [seli]
        選択中の行インデックスを得る。
        Returns:
            Int: 行ID
        """
        if self._selection is None:
            raise NotSelected()
        return self._selection[1]
    
    def selection_row(self):
        """ 選択中の行を得る。 """
        if self._selection is None:
            raise NotSelected()
        _index, row = self.rows[self._selection[1]]
        return row

    def _reselect(self):
        """ データ変更後に選択を引き継ぐ """
        if self._selection is not None:
            itemindex, _rowindex = self._selection
            self.select_by_item(itemindex)

    #
    def get_viewtype(self):
        """ @method
        表示タイプを得る。
        Returns:
            Str: タイプ
        """
        return self.viewtype or "table"

    def set_viewtype(self, viewtype):
        """ @method
        表示タイプを設定する。
        Params:
            viewtype(Str): タイプ
        Returns: 
            Self:
        """
        self.viewtype = viewtype
    
    def get_item_type(self) -> Type:
        """ アイテムの型。 """
        return self.itemtype
    
    #
    def select_column(self, name) -> Tuple[int, DataColumnUnion]:
        for icol, col in enumerate(self.viewcolumns):
            if col.get_name() == name:
                return icol, col
        else:
            col, *_ = make_data_columns(self.itemtype, name)
            return -1, col
    
    def get_current_columns(self) -> List[DataColumnUnion]:
        return self.viewcolumns
        
    def get_current_column_names(self) -> List[str]:
        return [x.get_name() for x in self.viewcolumns]
    
    def add_column(self, name):
        cols = make_data_columns(self.itemtype, name)
        self.viewcolumns.append(cols[0])
    
    def get_top_column_name(self) -> Optional[str]:
        a = self.itemtype.get_member_group("view-top")
        if a is not None:
            return a[0]
        for meth in self.itemtype.enum_methods():
            if meth.get_required_argument_min() == 0:
                return meth.name
        return None
    
    def get_link_column_name(self) -> Optional[str]:
        a = self.itemtype.get_member_group("view-link")
        if a is not None:        
            return a[0]
        return self.itemtype.get_member_group("view-top")

    def rows_to_string_table(self, context, method=None) -> Tuple[
        List[Tuple[int, List[str]]],    # 文字列にした一行ともとの行番号からなる表
        List[int]                       # 各列ごとの、文字列の最大長
    ]:
        """ 計算済みのメンバ値をすべて文字列へ変換する。 """
        colwidth = [0 for _ in self.viewcolumns]
        srows = []
        if method == "summarize":
            meth = DATASET_STRINGIFY_SUMMARIZE
        else:
            meth = DATASET_STRINGIFY
        for itemindex, row in self.rows:
            srow = ["" for _ in self.viewcolumns]
            for i, column in enumerate(self.viewcolumns):
                s = column.stringify(context, row[i], meth)
                srow[i] = s
                colwidth[i] = max(colwidth[i], get_text_width(s))
            srows.append((itemindex, srow))
        return srows, colwidth

    def generate_rows(self, context, newcolumns):
        """ 値を計算し、新たに設定する """
        newrows = []
        for itemindex, item in enumerate(self.items):
            subject = Object(self.itemtype, item)
            newrow = [col.eval(subject, context) for col in newcolumns]
            newrows.append((itemindex, newrow)) # 新しい行
        self.rows = newrows
        self.viewcolumns = newcolumns

    def generate_rows_concat(self, context, newcolumns):
        """ 値を計算し、現在の列の後ろに追加する """
        newrows = []
        for itemindex, currow in self.rows:
            item = self.items[itemindex]
            subject = Object(self.itemtype, item)
            newrow = [col.eval(subject, context) for col in newcolumns]
            newrows.append((itemindex, currow+newrow)) # 既存の行の後ろに結合
        self.rows = newrows
        self.viewcolumns = self.viewcolumns + newcolumns
    
    def generate_rows_identical(self):
        """ アイテム自体を値とし、"="演算子を列に設定する """
        newrows = []
        for itemindex, item in enumerate(self.items):
            newrows.append((itemindex, [item]))
        self.rows = newrows
        self.viewcolumns = [DataItemItselfColumn(self.itemtype)] # identical
    
    def append_generate_rows(self, context, items):
        """ 値を計算し、行を追加する """
        if not self.viewcolumns:
            raise ValueError("uninitialized")
        
        start = len(self.rows)
        if isinstance(self.viewcolumns[0], DataItemItselfColumn):
            for itemindex, item in enumerate(items, start=start):
                self.rows.append((itemindex, [item]))
        else:
            for itemindex, item in enumerate(items, start=start):
                item = self.items[itemindex]
                subject = Object(self.itemtype, item)
                newrow = [col.eval(subject, context) for col in self.viewcolumns]
                self.rows.append((itemindex, newrow))

    # 
    # ビューの列を変更する
    #
    def view(self, context, column_names):
        """ @method context
        列を変更する。
        Params:
            column_names(Tuple): カラム名
        """
        # 空のデータからは空のビューしか作られない
        if not self.items:
            self.rows = []
            return self

        # 列を新規作成
        newcolumns = make_data_columns(self.itemtype, *column_names)

        # 新たに値を計算
        self.generate_rows(context, newcolumns)
        
    def view_append(self, context, column_names):
        """ @method context alias-name [view++]
        列を追加する。
        Params:
            column_names(List[Str]): カラム名
        """
        # 空のデータからは空のビューしか作られない
        if not self.items:
            self.rows = []
            return self
        
        cur_column_names = self.get_current_column_names()
        new_column_names = []
        for cname in column_names:
            if cname not in cur_column_names:
                new_column_names.append(cname)

        # 列を新規作成
        newcolumns = make_data_columns(self.itemtype, *new_column_names)

        # データを展開する：列を追加
        self.generate_rows_concat(context, newcolumns)
    
    def operate(self, context, function, name=None):
        """ @method context [opr]
        任意の関数によって新しいカラムを作成し、最後に追加する。
        Params:
            function(Function): 1変数関数
            name(Str): *カラム名
        """
        # 空のデータからは空のビューしか作られない
        if not self.items:
            self.rows = []
            return self

        col = DataColumn(function, None, name=name) # 型は推定する
        self.generate_rows_concat(context, [col])
    
    def clone(self):
        """ @method
        このビューと同一の別のビューを作る。
        Returns:
            Sheet: 新たなビュー
        """
        r = Sheet(self.items, self.itemtype, uninitialized=True)
        r.rows = self.rows.copy()
        r.viewcolumns = self.viewcolumns.copy()
        r.viewtype = self.viewtype
        if self._selection is not None:
            r._selection = tuple(self._selection)
        return r

    #
    # アイテム関数
    #
    def map(self, context, predicate):
        """ @method context
        アイテムに値に関数を適用し、タプルとして返す。
        Params:
            predicate(Function): 述語関数
        Returns:
            Tuple:
        """
        values = []
        for item in self.current_items():
            o = Object(self.itemtype, item)
            v = predicate.run_function(o, context)
            values.append(v)
        return values

    def collect(self, context, predicate):
        """ @method context
        アイテムに関数を適用し、同じ型の有効な返り値のみを集めたタプルを返す。
        Params:
            predicate(Function): 述語関数
        Returns:
            Tuple:
        """
        values = []
        for item in self.current_items():
            o = Object(self.itemtype, item)
            v = predicate.run_function(o, context)
            if v.type is self.itemtype:
                values.append(v)
        return values
    
    def convertas(self, context, type):
        """ @method context alias-name [as]
        アイテムを新しい型に変換し、変換に成功した値のみを集めたタプルを返す。
        Params:
            type(Type): 新しい型
        Returns:
            Tuple:
        """
        if type is self.itemtype:
            return self.getitems()
        values = []
        for item in self.current_items():
            try:
                v = type.conversion_construct(context, item)
            except Exception as e:
                values.append(context.new_process_error_object(e))
            else:
                values.append(Object(type, v))
        return values
    
    #
    # 行関数
    #
    def row_to_object(self, context, itemindex, row):
        """ 
        表の一行を読み取り用オブジェクトに変換する 
        """
        values = {
            "#delegate" : Object(self.itemtype, self.items[itemindex])
        }
        for i, col in enumerate(self.viewcolumns):
            key = col.get_name()
            valtype = col.get_type(context)
            values[key] = Object(valtype, row[i])
        return context.get_type("ObjectCollection").new_object(values)

    def foreach(self, context, predicate):
        """ @method context
        行に関数を適用する。
        Params:
            predicate(Function): 関数
        """
        for entry in self.rows:
            subject = self.row_to_object(context, *entry)
            predicate.run_function(subject, context)
    
    def filter(self, context, predicate):
        """ @method context
        行を絞り込む。
        Params:
            predicate(Function): 述語関数
        """
        # 関数を行に適用する
        def fn(entry):
            subject = self.row_to_object(context, *entry)
            return predicate.run_function(subject, context).value
        
        self.rows = list(filter(fn, self.rows))

        # 選択を引き継ぐ
        self._reselect()
    
    def sort(self, context, key):
        """ @method context
        行の順番を並べ替える。
        Params:
            sorter(Function): 並べ替え関数
        """
        def sortkey(entry):
            subject = self.row_to_object(context, *entry)
            return key.run_function(subject, context).value

        self.rows.sort(key=sortkey)
        
        # 選択を引き継ぐ
        self._reselect()
    
    # any
    
    #
    # タプルの取得
    #
    def getallitems(self):
        """ @method alias-name [items]
        全アイテムオブジェクトのタプルを得る。
        Returns:
            Tuple: 
        """
        return [Object(self.itemtype, x) for x in self.items]

    def getitems(self):
        """ @method alias-name [curitems]
        現在の行のアイテムをタプルで得る。
        Returns:
            Tuple
        """
        return [Object(self.itemtype, x) for x in self.current_items()]
    
    def column(self, context, name):
        """ @method context
        ある列をタプルにして得る。
        Params:
            name(Str): カラム名
        Returns:
            Tuple:
        """
        objs = []
        for obj in self.column_values(context, name):
            objs.append(obj)
        return ObjectTuple(objs)
    
    def row(self, context, index):
        """ @method context
        ある行をタプルにして得る。
        Params:
            index(Str): 行番号
        Returns:
            Tuple:
        """
        objs = []
        row = self.get_row(index)
        for col, value in zip(self.viewcolumns, row):
            valtype = col.get_type(context)
            objs.append(Object(valtype, value))
        return ObjectTuple(objs)

    #
    # オブジェクト共通関数
    #
    def summarize(self):
        col = ", ".join([x.get_name() for x in self.get_current_columns()])
        return "{}({}) {}件のアイテム".format(self.itemtype.typename, col, self.count()) 

    def pprint(self, app):
        if len(self.rows) == 0:
            text = "結果は0件です" + "\n"
            app.post("message", text)
        else:
            context = app.get_process().get_last_invocation_context() # 実行中のコンテキスト
            app.post("object-setview", data=self, context=context)

    def conversion_construct(self, context, value, itemtypename, *columnnames):
        if not isinstance(value, list):
            value = list(value)

        itemtype = context.select_type(itemtypename)
        return Sheet(value, itemtype, context, columnnames)




class _RowToObject():
    def __init__(self, dataset, context):
        """ 型を初期化する """
        prototype = {
            "Typename" : "SetRowObject",
            "Delegate" : dataset.itemtype
        }
        for i, col in enumerate(dataset.viewcolumns):
            key = col.get_name()
            valtype = col.get_type(context)
            prototype[key] = valtype.typename
        
        self.type = Type(prototype).load()
        self.dataset = dataset
        self.context = context

    def row_object(self, itemindex, row):
        """ 行をオブジェクトに変換する """




    
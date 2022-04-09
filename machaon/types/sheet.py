from machaon.core.invocation import BasicInvocation
from machaon.core.object import Object
from typing import Sequence, List, Any, Tuple, Dict, DefaultDict, Optional, Generator, Iterable, Union

from machaon.core.message import select_method_by_object
from machaon.core.function import MemberGetExpression, parse_function

from machaon.types.tuple import ElemObject
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

SIGIL_ITEM_ITSELF = "@"

#
#
#
class BasicDataColumn():
    def get_type_conversion(self):
        raise NotImplementedError()
    
    def convert(self, context, object):
        conv = self.get_type_conversion()
        if conv:
            return context.new_object(object.value, conversion=conv)
        else:
            return object

    def stringify(self, context, object, method=DATASET_STRINGIFY):
        object = self.convert(context, object)

        if object.is_error():
            return "<{}>".format(object.summarize())
        if object.value is None:
            return "-"

        if method == DATASET_STRINGIFY_SUMMARIZE:
            return object.summarize()
        else:
            return object.stringify()

class SelectorColumn(BasicDataColumn):
    """
    メッセージの返す値
    """
    def __init__(self, selector, *, name=None):
        self._sel = selector
        self._name = name
    
    def get_name(self):
        if self._name is None:
            if hasattr(self._sel, "get_expression"):
                expr = self._sel.get_expression()
            elif isinstance(self._sel, BasicInvocation):
                expr = self._sel.display()[1]
            else:
                expr = str(self._sel)
            return '"{}"'.format(expr)
        return self._name
    
    def get_doc(self):
        return '"{}"'.format(self._sel)

    def get_type_conversion(self):
        if hasattr(self._sel, "get_type_conversion"):
            return self._sel.get_type_conversion()
        else:
            return None

    def eval(self, subject, context):
        selector = context.new_object(self._sel)
        invocation = select_method_by_object(selector, subject.type, reciever=subject.value)
        entry = invocation.prepare_invoke(context, subject)
        return entry.invoke(context)


class ItemItselfColumn(BasicDataColumn):
    """
    アイテムそのものを返す
    """
    def __init__(self, conversion=None):
        self._conv = conversion

    def get_type_conversion(self):
        return self._conv
    
    def get_name(self):
        return "@"
    
    def get_doc(self):
        return "要素自体"
    
    def eval(self, subject, _context):
        return subject

#
DataColumnUnion = Union[SelectorColumn, ItemItselfColumn]

def make_data_columns(*expressions):
    """
    カラムオブジェクトを返す
    Params:
        expressions(Sequence[Any]): カラム表現のリスト
    Returns:
        List[DataColumnUnion]:
    """
    columns: List[DataColumnUnion] = []
    for expression in expressions:
        if isinstance(expression, str):
            expression = expression.strip()
            if expression == SIGIL_ITEM_ITSELF:
                columns.append(ItemItselfColumn())
                continue
            
            if " " in expression:
                fn = parse_function(expression)
                if isinstance(fn, MemberGetExpression):
                    columns.append(SelectorColumn(fn, name=fn.get_expression()))
                else:
                    columns.append(SelectorColumn(fn))
            else:
                columns.append(SelectorColumn(expression, name=expression))
        else:
            columns.append(SelectorColumn(expression))
    
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
    Params:
        itemtype(Type): 要素の型（全要素に適用する）
        *columns(Any): カラム表現（@またはアイテムへのセレクタ）
    """
    def __init__(self, items, *, typeconversion=None, context=None, columns=None, uninitialized=False):
        self.items = items
        self.rows = []
        self.viewcolumns: List[DataColumnUnion] = []
        self.typeconversion = typeconversion

        self._selection: Optional[Tuple[int, int]] = None # itemindex, rowindex

        if not uninitialized:
            if self.items:
                if not isinstance(self.items[0], Object):
                    raise TypeError("'items' must be a sequence of Object")
            if not context or not columns:
                self.generate_rows_identical()
            elif not context:
                raise ValueError("Context is needed at Sheet constructor with columns")
            else:
                new_columns = make_data_columns(*columns)
                self.generate_rows(context, new_columns)
    
    def __iter__(self):
        """ アイテムオブジェクトを返す """
        return self.current_items()

    def get_item_type_conversion(self):
        """ アイテムの型。 
        Returns:
            str:
        """
        return self.typeconversion
    
    #
    # メンバ値へのアクセス
    #
    def at(self, row):
        """ @method 
        アイテムオブジェクトを行インデックスで指定して取得する。
        Params:
            row(int): 行インデックス
        Returns:
            Object: 値
        """
        itemindex, _r = self.rows[row]
        item = self.items[itemindex]
        return item
    
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
            obj = col.eval(self.items[itemindex], context)
        else:
            obj = r[icol]
        return obj
    
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
            if pred(obj, value):
                item = self.items[self.get_item_from_row(ival)]
                index = context.new_object(ival, type="Int")
                return ElemObject(item, index, obj)

        raise NotFound() # 見つからなかった
    
    def pick_in_first_column(self, context, _app, value):
        """ @method task context [#]
        最初のカラムの値で検索を行う。
        前方一致で見つからなければ後方一致の結果を返す。
        Params:
            value(Str): 検索する値
        Returns:
            Object: アイテム
        """
        fi, bi = None, None
        col = self.get_first_column()
        for ival, obj in enumerate(self.column_values(context, None, col)):
            s = col.stringify(context, obj)
            if s.startswith(value):
                fi = ival
                break
            elif bi is None and s.endswith(value):
                bi = ival

        iitem = fi if fi is not None else bi
        if iitem is None:
            raise NotFound()
        return self.items[self.get_item_from_row(iitem)]

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
        """ 現在有効なすべての行を取得する。 """
        for itemindex, rows in self.rows:
            yield itemindex, rows
    
    def current_items(self):
        """ 現在有効なアイテムを取得する。 """
        for itemindex, _ in self.rows:
            yield self.items[itemindex]

    def columns(self):
        """ @method
        カラムを返す。
        Returns:
            Tuple[Any]:
        """
        return self.viewcolumns
    
    def column_values(self, context, index, column=None):
        """ @method context
        ある列をタプルで得る。
        Params:
            index(Str): カラム番号／カラム名
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

        for itemindex, _row in self.rows:
            subject = self.items[itemindex]
            obj = col.eval(subject, context)
            yield obj
    
    def row_values(self, index):
        """ @method
        ある行をタプルで得る。
        Params:
            index(Int): 行番号
        Returns:
            Tuple:
        """
        _itemindex, row = self.rows[index]
        return row
    
    #
    # シーケンス関数
    # 
    def append(self, context, *items):
        """ @method context
        アイテムを末尾に追加する。
        Params:
            *items: 
        """
        self.insert(context, -1, *items)

    def insert(self, context, rowindex, *items):
        """ @method context
        アイテムを追加する。
        Params:
            rowindex(Int): 行インデックス
            *items: 
        """
        items = [context.new_object(x) for x in items]
        self.insert_items_and_generate_rows(context, rowindex, items)

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
        インデックスで行を選択する。
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
        アイテムIDで行を選択する。
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
        return self.items[self._selection[0]]
    
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
    # カラムを操作する
    #
    def select_column(self, column):
        """ @method 
        名前でカラムオブジェクトを取得する。無ければ作成する（追加はされない）
        Params:
            column(Any): カラム名またはセレクタ表現
        Returns:
            Tuple[int, DataColumnUnion]: カラムインデックスとオブジェクト 
        """
        if isinstance(column, str):
            for icol, col in enumerate(self.viewcolumns):
                if col.get_name() == column:
                    return icol, col
        
        col, *_ = make_data_columns(column)
        return -1, col
    
    def get_current_columns(self):
        """ @method　
        現在表示中のカラムオブジェクト
        Returns:
            List[DataColumnUnion]: 
        """
        return self.viewcolumns
        
    def get_current_column_names(self):
        """ @method 
        現在表示中のカラムの名前
        Returns:
            List[str]:
        """
        return [x.get_name() for x in self.viewcolumns]
    
    def get_first_column(self):
        """ @method 
        先頭に定義されたカラムオブジェクト
        Returns:
            DataColumnUnion:
        """
        if len(self.viewcolumns) == 0:
            raise ValueError("No columns")
        return self.viewcolumns[0]
    
    def add_column(self, column):
        """ @method
        カラムを追加する
        Params:
            column(Any): カラム表現
        """
        col, *_ = make_data_columns(column)
        self.viewcolumns.append(col)

    #
    # 行の生成
    #
    def generate_rows(self, context, newcolumns):
        """ 値を計算し、新たに設定する """
        newrows = []
        for itemindex, item in enumerate(self.items):
            newrow = [col.eval(item, context) for col in newcolumns]
            newrows.append((itemindex, newrow)) # 新しい行

        self.rows = newrows
        self.viewcolumns = newcolumns

    def generate_rows_concat(self, context, newcolumns):
        """ 値を計算し、現在の列の後ろに追加する """
        newrows = []
        for itemindex, currow in self.rows:
            item = self.items[itemindex]
            newrow = [col.eval(item, context) for col in newcolumns]
            newrows.append((itemindex, currow+newrow)) # 既存の行の後ろに結合

        self.rows = newrows
        self.viewcolumns = self.viewcolumns + newcolumns
    
    def generate_rows_identical(self):
        """ アイテム自体を値とし、"@"演算子を列に設定する """
        newrows = []
        for itemindex, item in enumerate(self.items):
            newrows.append((itemindex, [item]))
        self.rows = newrows
        self.viewcolumns = [ItemItselfColumn()] # identical
    
    def insert_items_and_generate_rows(self, context, rowindex, items):
        """ 一連のアイテムを追加し、値を計算して行も追加する """
        if not self.viewcolumns:
            raise ValueError("uninitialized")
        
        indexstart = rowindex if rowindex != -1 else len(self.items)
        
        # 行の値を生成する
        newrows = []
        for i, item in enumerate(items, start=indexstart):
            newrow = [col.eval(item, context) for col in self.viewcolumns]
            newrows.append((i, newrow))
        
        if rowindex == -1:
            # 後ろに追加する
            self.items = self.items + list(items)
            self.rows = self.rows + newrows
        
        else:
            # 後ろの行のインデックスをずらす
            tailrows = []
            offset = rowindex + len(items)
            for row in self.rows[rowindex:]:
                index, values = row
                tailrows.append((index+offset, values))
        
            # 挿入する
            self.items = self.items[:rowindex] + list(items) + self.items[rowindex:]
            self.rows = self.rows[:rowindex] + newrows + tailrows


    def rows_to_string_table(self, context, method=None): 
        """ 
        計算済みのメンバ値をすべて文字列へ変換する。 
        Params:
            context(InvocationContext):
            method(int): DATASET_STRINGIFY_XXXフラグ
        Returns:
            List[Tuple[int, List[str]]]: 行番号と値の文字列からなる行のリスト
        """
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
            srows.append((itemindex, srow))
        return srows

    # 
    # ビューの列を変更する
    #
    def _apply_view(self, context, columns, rowcommand):
        # 空のデータからは空のビューしか作られない
        if not self.items:
            self.rows = []
            return

        # 列を新規作成
        newcolumns = make_data_columns(*columns)
        
        # 行を設定する
        if rowcommand is None:
            self.generate_rows(context, newcolumns)
        elif rowcommand is "c":
            self.generate_rows_concat(context, newcolumns)

    def view(self, context, columns):
        """ @method context
        列を表示する。
        Params:
            columns(Tuple[Any]): カラム表現
        """
        self._apply_view(context, columns, None)
    
    def view_union(self, context, columns):
        """ @method context alias-name [view+]
        列を追加する。同名の既に存在する列は追加しない。
        Params:
            columns(Tuple[Any]): カラム表現
        """
        # 空のデータからは空のビューしか作られない
        new_columns = []
        if self.items:
            cur_column_names = self.get_current_column_names()
            for col in columns:
                if isinstance(col, str) and col not in cur_column_names:
                    new_columns.append(col)

        self._apply_view(context, new_columns, "c")
    
    def view_add(self, context, column, name=None):
        """ @method context alias-name [operate opr]
        カラムを一つ追加する。
        Params:
            column(Any): カラム表現
        """
        self._apply_view(context, [column], "c")

    #
    # アイテム関数
    #
    def map(self, context, _app, predicate):
        """ @task context
        アイテムに関数を適用し、タプルとして返す。
        Params:
            predicate(Function[](seq)): 述語関数
        Returns:
            Tuple:
        """
        values = []
        for item in self.current_items():
            v = predicate.run(item, context)
            values.append(v)
        return values

    def collect(self, context, _app, predicate):
        """ @task context
        アイテムに関数を適用し、偽でない返り値のみをタプルとして返す。
        Params:
            predicate(Function[](seq)): 述語関数
        Returns:
            Tuple:
        """
        values = []
        for item in self.current_items():
            o = predicate.run(item, context)
            if o.is_truth():
                values.append(o)
        return values
    
    #
    # 行関数
    #
    def row_to_object(self, context, itemindex, row):
        """ 
        表の一行を読み取り用オブジェクトに変換する 
        """
        values = {"#delegate" : self.items[itemindex]}
        for i, col in enumerate(self.viewcolumns):
            key = col.get_name()
            values[key] = row[i]
        return context.new_object(values, type="ObjectCollection")

    def foreach(self, context, _app, predicate):
        """ @task context [%]
        行に関数を適用する。
        Params:
            predicate(Function[](seq)): 関数
        """
        for entry in self.rows:
            subject = self.row_to_object(context, *entry)
            predicate.run(subject, context)
    
    def filter(self, context, _app, predicate):
        """ @task context [&]
        行を絞り込む。
        Params:
            predicate(Function[](seq)): 述語関数
        """
        # 関数を行に適用する
        def fn(entry):
            subject = self.row_to_object(context, *entry)
            return predicate.run(subject, context).test_truth()
        
        self.rows = list(filter(fn, self.rows))

        # 選択を引き継ぐ
        self._reselect()
    
    def sort(self, context, _app, sorter):
        """ @task context
        行の順番を並べ替える。
        Params:
            sorter(Function[](seq)): 並べ替え関数
        """
        def sortkey(entry):
            subject = self.row_to_object(context, *entry)
            return sorter.run(subject, context).test_truth()

        self.rows.sort(key=sortkey)
        
        # 選択を引き継ぐ
        self._reselect()
    
    # any
    
    #
    # タプルの取得
    #
    def get_all_items(self):
        """ @method context alias-name [items]
        全てのアイテムオブジェクトを得る。
        Returns:
            Tuple: 
        """
        return self.items

    def get_current_items(self):
        """ @method context alias-name [cur-items]
        現在有効な行のアイテムオブジェクトを得る。
        Returns:
            Tuple
        """
        return self.current_items()

    #
    #
    #
    def clone(self):
        """ @method
        このビューと同一の別のビューを作る。
        Returns:
            Sheet: 新たなビュー
        """
        r = Sheet(self.items, typeconversion=self.typeconversion, uninitialized=True)
        r.rows = self.rows.copy()
        r.viewcolumns = self.viewcolumns.copy()
        if self._selection is not None:
            r._selection = tuple(self._selection)
        return r
    
    #
    # オブジェクト共通関数
    #
    def constructor(self, context, value, itemtype=None, *columns):
        """ @meta context
        Params:
            Any: イテラブル型
        """
        try:
            iter(value)
        except TypeError:
            value = (value,)
        # 型変換を行う
        objs = [context.new_object(x, type=itemtype) for x in value]
        return Sheet(objs, context=context, columns=columns)
    
    def summarize(self, itemtype, *_column_names):
        """ @meta """
        col = ", ".join([x.get_name() for x in self.get_current_columns()])
        conv = "({})".format(itemtype.get_conversion()) if itemtype else ""
        return "[{}]{} {}件のアイテム".format(col, conv, self.count()) 

    def pprint(self, app, itemtype, *_column_names):
        """ @meta """
        if len(self.rows) == 0:
            text = "空です" + "\n"
            app.post("message", text)
        else:
            context = app.get_process().get_last_invocation_context() # 実行中のコンテキスト
            rows = self.rows_to_string_table(context, "summarize")
            columns = [x.get_name() for x in self.get_current_columns()]
            app.post("object-sheetview", rows=rows, columns=columns, context=context)

    
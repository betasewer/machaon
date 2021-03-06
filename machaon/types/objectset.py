from typing import Sequence, List, Any, Tuple, Dict, DefaultDict, Optional, Generator, Iterable, Union
from collections import defaultdict

from machaon.core.type import Type, TypeModule
from machaon.core.object import Object
from machaon.core.message import MessageEngine, MemberGetter, select_method
from machaon.core.invocation import InvocationContext
from machaon.cui import get_text_width
from machaon.types.tuple import ObjectTuple

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
DATASET_STRINGIFY = 0
DATASET_STRINGIFY_SUMMARIZE = 1

#
#
#
class DataColumn():
    def __init__(self, expression, method_inv, typename):
        self.getter = MemberGetter(expression, method_inv)
        self.typename = typename
        self._t = None
    
    @property
    def invocation(self):
        return self.getter.method

    def get_name(self):
        return self.invocation.get_method_name()
    
    def get_doc(self):
        return self.invocation.get_method_doc()
    
    def get_type(self, context):
        if self._t is None:
            self._t = context.select_type(self.typename)
        return self._t
    
    def eval(self, subject, context):
        obj = self.getter.run_function(subject, context)
        return obj.value
    
    def stringify(self, context, value, method):
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
            specs = methinv.get_result_specs()
            if not specs:
                raise ValueError("データカラムで参照中のメソッド'{}'は値を返しません".format(member_name))
            col = DataColumn(member_name, methinv, specs[0].get_typename())
            columns.append(col)
        else:
            invalid_names.append(member_name)

    if invalid_names:
        raise InvalidColumnNames(invalid_names)
    return columns

#
#
#
class FoundItem():
    """ @type
    データ集合に含まれる値。
    """
    def __init__(self, type=None, value=None, rowindex=None):
        self.type = type
        self.value = value
        self.rowindex = rowindex

#
#
#
class ObjectSet():  
    """ @type
    オブジェクトのメンバを縦列とするデータの配列。
    Typename: ObjectSet
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
        for itemindex, _row in self.rows:
            yield self.items[itemindex]

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
        return Object(self.itemtype, item)
    
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
    
    def find(self, context, column, value):
        """ @method context
        値をカラム名とインデックスで指定して取得する。
        Params:
            column(str): 列名+一致タイプ指定（前方*／*後方／*部分*）
            value(Any): 検索する値
        Returns:
            FoundItem: 値
        """
        # 一致タイプ
        code = 0
        if len(column)>1:
            if column[0] == "*" and column[-1] == "*": 
                code = 3
                column = column[1:-1]
            elif column[0] == "*":
                code = 2
                column = column[1:]
            elif column[-1] == "*":
                code = 1
                column = column[:-1]
        
        icol, col = self.select_column(column)

        if code == 0:
            def pred(l, r):
                return l == r
        elif code == 1:
            def pred(l, r):
                return col.stringify(context, l).startswith(r)
        elif code == 2:
            def pred(l, r):
                return col.stringify(context, l).endswith(r)
        elif code == 3:
            def pred(l, r):
                return r in col.stringify(context, l)
        
        # 順に検索
        for ival, val in enumerate(self.select_column_values(icol, col, context)):
            if pred(val, value):
                valtype = col.get_type(context)
                return FoundItem(valtype, val, ival)

        return FoundItem() # 見つからなかった

    def row(self, index):
        """ 行を取得する。 """
        _itemindex, row = self.rows[index]
        return row
    
    def get_row_from_item(self, itemindex) -> int:
        """ アイテムIDから行番号を取得する。 線形探索を行う。"""
        for irow, (iitem, _row) in enumerate(self.rows):
            if iitem == itemindex:
                return irow
        raise ValueError("Invalid item index")
    
    def get_current_items(self):
        """ 現在あるすべての行のアイテムを取得する。 """
        items = []
        for itemindex, _ in self.rows:
            items.append(self.items[itemindex])
        return items
    
    def count(self):
        """ @method
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

    def selection(self): # rowindexを返す
        """ @method
        選択中の行インデックスを得る。
        Returns:
            Optional[Int]: 行ID
        """
        if self._selection is None:
            return None
        return self._selection[1]
    
    def selection_item(self):
        """ @method
        選択中のアイテムを得る。
        Returns:
            Optional[Object]: アイテム
        """
        if self._selection is None:
            return None
        return Object(self.itemtype, self.items[self._selection[0]])

    def selection_row(self):
        """ 選択中の行を得る。 """
        if self._selection is None:
            return None
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
        
    def expand_view(self, context, column_names):
        """ @method context
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

    def clone(self):
        """ @method
        このビューと同一の別のビューを作る。
        Returns:
            Self: 新たなビュー
        """
        r = ObjectSet(self.items, self.itemtype, uninitialized=True)
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
        for item in self.get_current_items():
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
        for item in self.get_current_items():
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
        for item in self.get_current_items():
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
    def foreach(self, context, predicate):
        """ @method context
        行に関数を適用する。
        Params:
            predicate(Function): 関数
        """
        converter = RowToObject(self, context)
        for entry in self.rows:
            subject = converter.row_object(*entry)
            predicate.run_function(subject, context)
    
    def filter(self, context, predicate):
        """ @method context
        行を絞り込む。
        Params:
            predicate(Function): 述語関数
        """
        # 関数を行に適用する
        converter = RowToObject(self, context)
        def fn(entry):
            subject = converter.row_object(*entry)
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
        converter = RowToObject(self, context)
        def sortkey(entry):
            subject = converter.row_object(*entry)
            return key.run_function(subject, context).value

        self.rows.sort(key=sortkey)
        
        # 選択を引き継ぐ
        self._reselect()
    
    # any
    
    #
    def getallitems(self):
        """ @method alias-name [items]
        全アイテムオブジェクトのタプルを得る。
        Returns:
            Tuple: 
        """
        return [Object(self.itemtype, x) for x in self.items]

    #
    def getitems(self):
        """ @method alias-name [curitems]
        現在の行のアイテムをタプルで得る。
        Returns:
            Tuple
        """
        return [Object(self.itemtype, x) for x in self.get_current_items()]
    
    #
    def column(self, context, column):
        """ @method context
        ある列をタプルにして得る。
        Params:
            column(Str): カラム名
        Returns:
            Tuple:
        """
        icol, col = self.select_column(column)
        if icol == -1:
            # 新しいカラムを増やす
            self.generate_rows_concat(context, [col])
            icol = len(self.viewcolumns)
            self.viewcolumns.append(col)

        valtype = col.get_type(context)
        objs = []
        for itemindex, _row in self.rows:
            subject = Object(self.itemtype, self.items[itemindex])
            value = col.eval(subject, context)
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
        return ObjectSet(value, itemtype, context, columnnames)


class RowToObject():
    """ 
    表の一行を読み取り用オブジェクトに変換する 
    """
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
        values = {
            "/delegate" : self.dataset.items[itemindex]
        }
        for i, col in enumerate(self.dataset.viewcolumns):
            key = col.get_name()
            valtype = col.get_type(self.context)
            values[key] = Object(valtype, row[i])
        return Object(self.type, values)




    
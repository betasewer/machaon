from machaon.core.object import Object
from typing import Sequence, List, Any, Tuple, Dict, DefaultDict, Optional, Generator, Iterable, Union

from machaon.core.type import Type, TypeModule
from machaon.core.message import MessageEngine, MemberGetter, select_method
from machaon.core.symbol import BadTypename, SIGIL_DEFAULT_RESULT

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

#
#
#
class BasicDataColumn():
    def __init__(self):
        self._t = None # この列の値の、概ね共通の型
    
    def get_type(self):
        return self._t
    
    def set_type(self, t):
        self._t = t
    
    def is_type_unspecified(self):
        return self._t is None

    def current_type(self, context):
        if self._t is None:
            return context.get_type("Any")
        return self._t

    def new_object(self, context, value):
        t = self.current_type(context)
        return context.new_object(value, type=t)

    def stringify(self, context, object, method=DATASET_STRINGIFY):
        if object.is_error():
            return "<{}>".format(object.summary())
        if isinstance(object.value, str) and object.value == SIGIL_DEFAULT_RESULT:
            return object.value

        if method == DATASET_STRINGIFY_SUMMARIZE:
            return object.summary()
        else:
            return object.to_string()
    
    def is_nonstring_column(self):
        if self.is_type_unspecified():
            return True
        return not self._t.is_any() and self._t.typename != "Str"
    
    def make_compare_operator(self, context, lessthan=True):
        typ = self.current_type(context)
        if lessthan:
            inv = select_method("lt", typ)
        else:
            inv = select_method("!lt", typ)
        if inv is None:
            return None
        inv.set_result_typehint("Bool")
        return inv
    
    def _compose_last_eval_type(self, newtype, context):
        lasttype = self._t
        if lasttype:
            if lasttype.is_any():
                return
            elif lasttype.is_supertype(newtype):
                pass
            else:
                newtype = context.get_type("Any")
        self.set_type(newtype)

class DataOperationColumn(BasicDataColumn):
    def __init__(self, function, *, name=None):
        super().__init__()
        self._fn = function
        self._name = name
    
    def get_name(self):
        if self._name is None:
            return '"{}"'.format(self._fn.get_expression())
        return self._name
    
    def get_function(self):
        return self._fn

    def eval(self, subject, context):
        obj = self._fn.run_function(subject, context)
        # 共通型を定義しなおす：値型ではなく、宣言された型を参照する
        entry = context.get_last_invocation()
        decltype = context.get_type(entry.result_spec().get_typename()) # 最後の呼び出しの返り値型
        self._compose_last_eval_type(decltype, context)
        return obj

class DataMemberColumn(BasicDataColumn):
    def __init__(self, membername):
        super().__init__()
        self._name = membername
        self._method = "&" + membername
    
    def get_name(self):
        return self._name
    
    def eval(self, subject, context):
        # 呼び出しの度に解決する
        inv = select_method(self._method, subject.type, reciever=subject.value)
        fn = MemberGetter(self._method, inv)
        obj = fn.run_function(subject, context)
        # 共通型を定義しなおす：値型ではなく、宣言された型を参照する
        decltype = context.get_type(inv.get_result_spec().get_typename())
        self._compose_last_eval_type(decltype, context)
        return obj

class DataItemItselfColumn(BasicDataColumn):
    def __init__(self, type):
        super().__init__()
        self.set_type(type)
    
    @property
    def method(self):
        return None

    def get_name(self):
        return "="
    
    def get_doc(self):
        return "要素"
    
    def eval(self, subject, _context):
        return subject

#
DataColumnUnion = Union[DataMemberColumn, DataOperationColumn, DataItemItselfColumn]

#
def make_data_columns(itemtype, *expressions) -> List[DataColumnUnion]:
    columns: List[DataColumnUnion] = []

    names: List[str] = []
    for expr in expressions:
        aliases = itemtype.get_member_group(expr)
        if aliases is not None:
            names.extend(aliases)
        else:
            names.append(expr)

    for member_name in names:
        if member_name == "=":
            columns.append(DataItemItselfColumn(itemtype))
            continue
        
        parts = member_name.split()
        if len(parts) == 1:
            columns.append(DataMemberColumn(member_name))
        elif len(parts) > 1:
            columns.append(DataOperationColumn(member_name))

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
    """
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
            elif not context:
                raise ValueError("Context is needed at Sheet constructor with columns")
            else:
                new_columns = make_data_columns(self.itemtype, *column_names)
                self.generate_rows(context, new_columns)
    
    # アイテムにアクセスする
    def __iter__(self):
        return self.current_items()

    #
    # メンバ値へのアクセス
    #
    def at(self, context, row):
        """ @method context 
        アイテムオブジェクトを行インデックスで指定して取得する。
        Params:
            row(int): 行インデックス
        Returns:
            Object: 値
        """
        itemindex, _r = self.rows[row]
        item = self.items[itemindex]
        return context.new_object(item, type=self.itemtype)
    
    def top(self, context):
        """ @method context [t]
        0番目のアイテムオブジェクトを取得する。
        Returns:
            Object: 値
        """
        return self.at(context, 0)
    
    def last(self, context):
        """ @method context [l]
        最後のアイテムオブジェクトを取得する。
        Returns:
            Object: 値
        """
        return self.at(context, -1)
    
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
    
    def pick_in_first_column(self, context, app, value):
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
            elif s.endswith(value):
                bi = ival

        iitem = fi if fi is not None else bi
        if iitem is not None:
            item = self.items[self.get_item_from_row(iitem)]
            return context.new_object(item, type=self.itemtype)
        raise NotFound()

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
            subject = context.new_object(self.items[itemindex], type=self.itemtype)
            obj = col.eval(subject, context)
            yield obj
    
    def row_values(self, index):
        """ @method
        ある行をタプルで得る。
        Params:
            index(Str): 行番号
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

    def selection(self, context):
        """ @method context [sel]
        選択中のアイテムを得る。
        Returns:
            Object: アイテム
        """
        if self._selection is None:
            raise NotSelected()
        return context.new_object(self.items[self._selection[0]], type=self.itemtype)

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
    
    def get_first_column(self):
        if len(self.viewcolumns) == 0:
            raise ValueError("No columns")
        return self.viewcolumns[0]
    
    def add_column(self, name):
        cols = make_data_columns(self.itemtype, name)
        self.viewcolumns.append(cols[0])

    def rows_to_string_table(self, context, method=None) -> List[Tuple[int, List[str]]]: # 文字列にした値と行番号からなる行のリスト
        """ 計算済みのメンバ値をすべて文字列へ変換する。 """
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

    def generate_rows(self, context, newcolumns):
        """ 値を計算し、新たに設定する """
        newrows = []
        for itemindex, item in enumerate(self.items):
            subject = context.new_object(item, type=self.itemtype)
            newrow = [col.eval(subject, context) for col in newcolumns]
            newrows.append((itemindex, newrow)) # 新しい行

        self.rows = newrows
        self.viewcolumns = newcolumns

    def generate_rows_concat(self, context, newcolumns):
        """ 値を計算し、現在の列の後ろに追加する """
        newrows = []
        for itemindex, currow in self.rows:
            item = self.items[itemindex]
            subject = context.new_object(item, type=self.itemtype)
            newrow = [col.eval(subject, context) for col in newcolumns]
            newrows.append((itemindex, currow+newrow)) # 既存の行の後ろに結合

        self.rows = newrows
        self.viewcolumns = self.viewcolumns + newcolumns
    
    def generate_rows_identical(self):
        """ アイテム自体を値とし、"="演算子を列に設定する """
        newrows = []
        for itemindex, item in enumerate(self.items):
            subject = Object(self.itemtype, item)
            newrows.append((itemindex, [subject]))
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
                subject = context.new_object(item, type=self.itemtype)
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
            column_names(Tuple[Str]): カラム名
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
    
    def operate(self, context, message, name=None):
        """ @method context [opr]
        任意の関数によって新しいカラムを作成し、最後に追加する。
        Params:
            message(Str): カラム名/1変数関数
            name(Str): *カラム名
        """
        # 空のデータからは空のビューしか作られない
        if not self.items:
            self.rows = []
            return self

        cols = make_data_columns(self.itemtype, message)
        self.generate_rows_concat(context, cols)
    
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
    def map(self, context, _app, predicate):
        """ @task context
        アイテムに値に関数を適用し、タプルとして返す。
        Params:
            predicate(Function): 述語関数
        Returns:
            Tuple:
        """
        values = []
        for item in self.current_items():
            o = context.new_object(item, type=self.itemtype)
            v = predicate.run_function(o, context,)
            values.append(v)
        return values

    def collect(self, context, _app, predicate):
        """ @task context
        アイテムに関数を適用し、同じ型の有効な返り値のみを集めたタプルを返す。
        Params:
            predicate(Function): 述語関数
        Returns:
            Tuple:
        """
        values = []
        for item in self.current_items():
            o = context.new_object(item, type=self.itemtype)
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
            return self.getitems(context)
        values = []
        for item in self.current_items():
            try:
                v = type.conversion_construct(context, item)
            except Exception as e:
                values.append(context.new_process_error_object(e))
            else:
                values.append(type.new_object(v))
        return values
    
    #
    # 行関数
    #
    def row_to_object(self, context, itemindex, row):
        """ 
        表の一行を読み取り用オブジェクトに変換する 
        """
        values = {
            "#delegate" : context.new_object(self.items[itemindex], type=self.itemtype)
        }
        for i, col in enumerate(self.viewcolumns):
            key = col.get_name()
            obj = row[i]
            if obj.value == "-" and col.is_nonstring_column():  # boilerplate
                obj = col.new_object(context, None)       #
            values[key] = obj
        return context.new_object(values, type="ObjectCollection")

    def foreach(self, context, _app, predicate):
        """ @task context [%]
        行に関数を適用する。
        Params:
            predicate(Function): 関数
        """
        for entry in self.rows:
            subject = self.row_to_object(context, *entry)
            predicate.run_function(subject, context)
    
    def filter(self, context, _app, predicate):
        """ @task context [&]
        行を絞り込む。
        Params:
            predicate(Function): 述語関数
        """
        # 関数を行に適用する
        def fn(entry):
            subject = self.row_to_object(context, *entry)
            return predicate.run_function(subject, context).test_truth()
        
        self.rows = list(filter(fn, self.rows))

        # 選択を引き継ぐ
        self._reselect()
    
    def sort(self, context, _app, sorter):
        """ @task context
        行の順番を並べ替える。
        Params:
            sorter(Function): 並べ替え関数
        """
        def sortkey(entry):
            subject = self.row_to_object(context, *entry)
            return sorter.run_function(subject, context).test_truth()

        self.rows.sort(key=sortkey)
        
        # 選択を引き継ぐ
        self._reselect()
    
    # any
    
    #
    # タプルの取得
    #
    def get_all_items(self, context):
        """ @method context alias-name [items]
        全てのアイテムオブジェクトを得る。
        Returns:
            Tuple: 
        """
        return [context.new_object(x, type=self.itemtype) for x in self.items]

    def get_current_items(self, context):
        """ @method context alias-name [cur-items]
        現在有効な行のアイテムオブジェクトを得る。
        Returns:
            Tuple
        """
        return [context.new_object(x, type=self.itemtype) for x in self.current_items()]

    #
    # オブジェクト共通関数
    #
    def constructor(self, context, value, itemtypename, *columnnames):
        """ @meta extra-args 
        Params:
            value(Any): イテラブル型・
            itemtypename(Str): 型名
            *columnnames(Str): カラム名のリスト
        """
        if not isinstance(value, list):
            value = list(value)

        itemtype = context.select_type(itemtypename)
        if itemtype is None:
            raise BadTypename(itemtypename)

        # 型変換を行う
        if len(value)>0:
            if not itemtype.check_value_type(type(value[0])): # 先頭だけ調べる（全て同型が前提）
                value = [context.new_object(x, type=itemtype).value for x in value]

        return Sheet(value, itemtype, context, columnnames)
    
    def summarize(self):
        """ @meta """
        col = ", ".join([x.get_name() for x in self.get_current_columns()])
        return "{}({}) {}件のアイテム".format(self.itemtype.typename, col, self.count()) 

    def pprint(self, app):
        """ @meta """
        if len(self.rows) == 0:
            text = "結果は0件です" + "\n"
            app.post("message", text)
        else:
            context = app.get_process().get_last_invocation_context() # 実行中のコンテキスト
            rows = self.rows_to_string_table(context, "summarize")
            columns = [x.get_name() for x in self.get_current_columns()]
            app.post("object-sheetview", rows=rows, columns=columns, context=context)




    
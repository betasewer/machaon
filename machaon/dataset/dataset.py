from typing import Sequence, List, Any, Tuple, Dict, DefaultDict, Optional
from collections import defaultdict

#from machaon.valuetype.predicate import predicate, predicate_defs
from machaon.dataset.filter import DataFilter
from machaon.dataset.sort import DataSortKey
from machaon.dataset.predicate import Predicate, BadPredicateError
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
class DataMethod():
    def __init__(self, name):
        self.name = name

    def __call__(self, item):
        p = getattr(item, self.name)
        return p()

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
    def __init__(self, ref, datas, rows=None, viewtype=None, viewpreds=None):
        self.ref = ref
        self.datas = datas
        self.rows = rows or []
        # 
        self.viewpreds: List[predicate] = viewpreds or []
        self.viewtype: str = viewtype or "table"
        self.selecting: Optional[int] = None
    
    def assign(self, otherview):
        r = otherview
        self.ref = r.ref
        self.datas = r.datas
        self.rows = r.rows
        self.viewpreds = r.viewpreds
        self.viewtype = r.viewtype
        self.selecting = r.selecting
        return self

    # アクセス
    def row(self, i):
        return self.rows[i]

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
    def get_current_columns(self):
        return self.viewpreds
    
    def get_all_columns(self):
        if self.ref is None:
            return []
        return self.ref.columns.getall()
    
    def find_column(self, name):
        return self.ref.columns.find(name)
    
    def get_first_column(self):
        e = self.ref.columns.top_entry()
        if e is None:
            raise ValueError("No column")
        return e[0]
    
    def get_link_column(self):
        e = self.ref.columns.selectone("link")
        if e:
            return e
        return self.get_first_column()

    def get_default_columns(self):
        c = self.ref.get_default_columnname(self.viewtype)
        es, _ = self.ref.columns.select(c)
        if es:
            return es
        else:
            return [self.ref.columns.get_first_column()] # 先頭カラム

    #
    #
    #
    def expand_item_to_rows(self, predicates):
        rows = []
        for item in self.datas:
            row = []
            for pred in predicates:
                lhs = pred.get_value(item)
                row.append(lhs)
            rows.append(row)
        return rows

    def rows_to_string_table(self):
        colwidth = [0 for _ in self.viewpreds]
        srows = []
        for row in self.rows:
            srow = []
            for i in range(len(self.viewpreds)):
                s = self.viewpreds[i].value_to_string(row[i])
                colwidth[i] = max(colwidth[i], get_text_width(s))
                srow.append(s)
            srows.append(srow)
        return srows, colwidth

    #
    # べつのビューを作る
    #
    def create_view(self, viewtype, columns=None, filter=None, sortkey=None, *, trunc=True):
        # 空のデータからは空のビューしか作られない
        if not self.datas:
            return DataView(self.ref, [])

        # 列を決定する
        if not columns:
            columns = self.get_default_columns()

        total_columns = []
        total_columns.extend(self.ref.columns.normalize_names(columns))

        def add_related_columns(total, targets):
            indices = []
            for column in self.ref.columns.normalize_names(targets):
                if column not in total:
                    total.append(column)
                    indices.append(len(total)-1)
                else:
                    indices.append(total.index(column))
            return indices

        if filter:
            filter_indices = add_related_columns(total_columns, filter.get_related_variables())
        if sortkey:
            sort_indices = add_related_columns(total_columns, sortkey.get_related_variables())

        predicates, invalids = self.ref.columns.select(total_columns)
        if invalids:
            raise InvalidColumnNames(invalids)
        
        # データを展開する
        if trunc:
            rows = self.expand_item_to_rows(predicates)
        else:
            rows = self.rows
        
        # 関数を適用する
        if filter:
            # 関連するカラムの値をリストで渡し、判定
            rows = [row for row in rows if filter([row[i] for i in filter_indices])]
        if sortkey:
            def key(row):
                # 同じく、関連するカラムの値をリストで渡し、判定
                return sortkey([row[i] for i in sort_indices])
            rows.sort(key=key)

        #viewpreds =  predicates[0:len(columns)-1]
        return DataView(self.ref, self.datas, rows, viewtype, predicates)
    
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



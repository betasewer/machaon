from typing import Sequence, List, Any, Tuple, Dict, DefaultDict
from collections import defaultdict

from machaon.dataset.filter import Predicate, DataFilter
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
class DataReference():
    def __init__(self, *, itemclass):
        self._predicates: Dict[str, Tuple[str, Predicate]] = {}
        self.firstpred: str = None
        self.itemclass: Any = itemclass
        self.defcolumns: Dict[str, Tuple[str]] = {}
    
    #
    # 検索述語
    #
    def add_pred(self, names, p):
        kwd = names[0]
        if not self._predicates:
            self.firstpred = kwd
        for name in names:
            self._predicates[name] = (kwd, p)
    
    def get_first_pred(self):
        if not self.firstpred:
            raise ValueError("")
        name, pred = self._predicates[self.firstpred]
        return name, pred
    
    def get_all_preds(self) -> List[Tuple[Predicate, List[str]]]:
        predset: DefaultDict[Predicate, List[str]] = defaultdict(list)
        for key, (_topkey, pred) in self._predicates.items():
            predset[pred].append(key)

        entries = list(predset.items())
        entries.sort(key=lambda e:e[1][0])
        return entries

    def get_default_columns(self, viewtype):
        if viewtype in self.defcolumns:
            return self.defcolumns[viewtype]
        else:
            return [self.firstpred] # 先頭カラム
    
    def normalize_column(self, name):
        return self._predicates[name][0]

    def find_pred(self, column_name):
        entry = self._predicates.get(column_name)
        if entry:
            return entry[1]
        return None
    
    def select_preds(self, column_names):
        preds = []
        invalids = []
        for column_name in column_names:
            if column_name in self._predicates:
                preds.append(self._predicates[column_name][1])
            else:
                invalids.append(column_name)
        return preds, invalids
        
    #
    def __getitem__(self, name_expr):
        first_name, *names = name_expr.split()
        def _parameters(
            disp="", 
            type=None,
            value=None,
        ):
            if value is None:
                value = getattr(self.itemclass, first_name, None)
            p = Predicate(predtype=type, description=disp, value=value)
            self.add_pred((first_name, *names), p)
            return self
        return _parameters
    
    def default_columns(self, 
        table = None,
        wide = None,
    ):
        self.defcolumns = {
            "table" : table,
            "wide" : wide,
        }
        return self

#
#
#
class DataView():
    def __init__(self, ref, datas, rows=None, viewtype="table", viewpreds=None):
        self.ref = ref
        self.datas = datas
        self.rows = rows or []
        # 
        self.viewpreds = viewpreds
        self.viewtype = viewtype
        self.selecting = None
    
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
    def get_predicates(self):
        return self.viewpreds
    
    def get_all_predicates(self):
        if self.ref is None:
            return []
        return self.ref.get_all_preds()
        
    #
    #
    #
    def to_string_table(self):
        colwidth = [0 for _ in self.viewpreds]
        srows = []
        for row in self.rows:
            srow = []
            for i in range(len(self.viewpreds)):
                s = str(row[i])
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
            columns = self.ref.get_default_columns(viewtype)

        total_columns = []
        total_columns.extend([self.ref.normalize_column(x) for x in columns])

        def add_related_columns(total, targets):
            indices = []
            for target in targets:
                column = self.ref.normalize_column(target)
                if column not in total:
                    total.append(column)
                    indices.append(len(total)-1)
                else:
                    indices.append(total.index(column))
            return indices

        if filter:
            filter_indices = add_related_columns(total_columns, filter.get_related_columns())
        if sortkey:
            sort_indices = add_related_columns(total_columns, sortkey.get_related_columns())

        predicates, invalids = self.ref.select_preds(total_columns)
        if invalids:
            raise InvalidColumnNames(invalids)
        
        # データを展開する
        if trunc:
            rows = []
            for item in self.datas:
                row = []
                for pred in predicates:
                    lhs = pred.make_operator_lhs(item)
                    row.append(lhs)
                rows.append(row)
        else:
            rows = self.rows
        
        # 関数を適用する
        if filter:
            rows = [row for row in rows if filter([row[i] for i in filter_indices])]
        if sortkey:
            def key(row):
                return sortkey([row[i] for i in sort_indices])
            rows.sort(key=key)

        #viewpreds =  predicates[0:len(columns)-1]
        return DataView(self.ref, self.datas, rows, viewtype, predicates)
    
    #
    # コマンドからビューを作成する
    #
    # syntax:
    # <column-name>... ? <column-name> <filter-operator> <?args...> @ <column-name> <?sort-operator>
    # :list name path date ? date within 2015/04/08 2016/01/03
    def command_create_view(self, expression=None, *, trunc=True, filter_query=None, sort_query=None):
        dispmode = False

        # コマンド文字列を解析する
        column_part = 0
        viewtype_part = None
        filter_part = None
        sorter_part = None
        parts = []
        if expression:
            parts = expression.split()
            for i, part in enumerate(parts):
                if i == 0 and part.startswith(":"):
                    viewtype_part = 0
                    column_part = 1
                elif filter_part is None and part.startswith("?"):
                    filter_part = i                
                elif sorter_part is None and part.startswith("@"):
                    sorter_part = i

        if viewtype_part is not None:
            viewtype = parts[viewtype_part][1:]
            if viewtype == "disp":
                dispmode = True
                viewtype = self.viewtype
        else:
            viewtype = self.viewtype
        
        columns = parts[column_part:filter_part]

        filter_ = None
        if filter_part is not None:
            filter_query = " ".join(parts[filter_part:sorter_part])[1:] # ? を落とす
        if filter_query:
            filter_ = DataFilter(self.ref, filter_query, dispmode)
            if filter_.failure:
                raise filter_.failure

        sortkey = None
        if sorter_part is not None:
            sort_query = " ".join(parts[sorter_part:])[1:] # @ を落とす
        if sort_query:
            raise NotImplementedError("sort expression")
            
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



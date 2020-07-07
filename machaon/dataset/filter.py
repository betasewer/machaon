from typing import Sequence, List, Any, Tuple
from machaon.dataset.predicate import Predicate, BadOperatorError, BadPredicateError

# (A and B) or (C and D)
# A B and C D and or
#
class CondOperation():
    def __init__(self, left_index, left_name, operator, *right_args, notbit=False):
        self.fn = operator
        self.largi = left_index
        self.largname = left_name # デバッグ用
        self.rargs = right_args
        self.bit = not notbit

    def __call__(self, row):
        lhs = row[self.largi]
        test = (self.fn(lhs, *self.rargs) == self.bit)
        return test
        
    def display(self, row, _level=1):
        lhs = row[self.largi]
        fn = self.fn.__name__
        if not self.bit: fn = "!" + fn
        return "({} {})".format(fn, " ".join(["<{}: {}>".format(self.largname, lhs)] + [str(x) for x in self.rargs]))

#
class CondAndClause():
    def __init__(self, left, right):
        self.l = left
        self.r = right

    def __call__(self, row):
        return self.l(row) and self.r(row)

    def display(self, row, level=1):
        return "(AND \n{0}{1} \n{0}{2})".format(" "*level, self.l.display(row, level+1), self.r.display(row, level+1))

#
class CondOrClause():
    def __init__(self, left, right):
        self.l = left
        self.r = right

    def __call__(self, row):
        return self.l(row) or self.r(row)
    
    def display(self, row, level=1):
        return "(OR \n{0}{1} \n{0}{2})".format(" "*level, self.l.display(row, level+1), self.r.display(row, level+1))

#
#
#
class FilterConditionParseError(Exception):
    pass

#
#
#
OP_AND = 1
OP_OR = 2

TOKEN_TERM = 0x01
TOKEN_BLOCK_BEGIN = 0x02
TOKEN_TERM_END = 0x04
TOKEN_BLOCK_END = 0x10

# <column-name> <operator> <args>... の順番は絶対
class _OperationStack():
    def __init__(self, ref):
        self.ref = ref
        self.clear()
        self.related_columns = []

    def clear(self):
        self.col = None
        self.opr = None
        self.args = []
        self.notbit = False
    
    def push(self, term):
        if not self.col:
            # 述語を決定する
            if term == "_":
                term, pred = self.ref.get_first_pred()
            else:
                pred = self.ref.find_pred(term)
            if pred is None:
                raise BadPredicateError(term)
            self.col = (term, pred)
        elif not self.opr:
            # 演算子は構文木構築時に生成する
            if term.startswith("!") and term != "!=":
                self.opr = term[1:]
                self.notbit = True
            else:
                self.opr = term
        elif self.opr and self.col:
            self.args.append(term)
        else:
            raise FilterConditionParseError()
    
    def pop(self):
        col = self.col
        opr = self.opr
        args = self.args
        notbit = self.notbit
        self.clear()
        if col and opr:
            colname, pred = col
            if colname in self.related_columns:
                colindex = self.related_columns.index(colname)
            else:
                self.related_columns.append(colname)
                colindex = len(self.related_columns)-1

            operator = pred.parse_operation(opr)
            operands = pred.parse_operands(args)
            return CondOperation(colindex, colname, operator, *operands, notbit=notbit)
        return None

#
# トークンの解析
#
def _tokenize(inputseq, ref):
    curblock = []
    blocks = [curblock]
    opstack = _OperationStack(ref)
    term = ""

    def tokens(expr):
        for ch in expr:
            if ch == "(":
                tok = TOKEN_BLOCK_BEGIN
            elif ch == ")":
                tok = TOKEN_BLOCK_END | TOKEN_TERM_END
            elif ch.isspace():
                tok = TOKEN_TERM_END
            else:
                tok = TOKEN_TERM
            yield tok, ch
        yield TOKEN_BLOCK_END | TOKEN_TERM_END, None

    for token, ch in tokens(inputseq):
        if token & TOKEN_BLOCK_BEGIN:
            block = []
            curblock.append(block)
            blocks.append(block)
            curblock = block

        if token & TOKEN_TERM_END:
            combiner = None
            if term == "||":
                combiner = OP_OR
            elif term == "&&":
                combiner = OP_AND
            
            if combiner:
                op = opstack.pop()
                if op:
                    curblock.append(op)
                curblock.append(combiner)
            elif term:
                opstack.push(term)
            term = ""
        
        if token & TOKEN_TERM:
            term += ch

        if token & TOKEN_BLOCK_END:
            op = opstack.pop()
            if op:
                curblock.append(op)
            blocks.pop()
            if blocks:
                curblock = blocks[-1]
            else:
                return curblock, opstack.related_columns

    return None, None

#
# 構文木をつくる
#
def _build_ast(token):
    if isinstance(token, list):
        tokenitr = iter(token)
        stack = []
        while True:
            child = next(tokenitr, None)
            if child is None:
                break
            chi = _build_ast(child)
            if chi in (OP_OR, OP_AND):
                lhs = stack.pop()
                rhs = _build_ast(next(tokenitr))
                tree = None
                if chi == OP_AND:
                    tree = CondAndClause(lhs, rhs)
                elif chi == OP_OR:
                    tree = CondOrClause(lhs, rhs)
                stack.append(tree)
            else:
                stack.append(chi)
        return stack[0]
    else:
        return token

#
#
#
class DataFilter():
    def __init__(self, ref, expression, dispmode=False):
        self.failure = None
        columns = None
        ast = None
        try:
            tokens, columns = _tokenize(expression, ref)
            if tokens:
                ast = _build_ast(tokens)
        except (BadPredicateError, BadOperatorError, FilterConditionParseError) as e:
            self.failure = e
        
        if dispmode:
            def _dispast(row):
                ret = ast(row)
                print("row: {} -> {}".format(row, ret))
                print("ast:")
                print(ast.display(row))
                print("")
                return ret
            fn = _dispast
        else:
            fn = ast

        self.fn = fn
        self.related_columns = columns
        self.ref = ref
    
    def __call__(self, row):
        if self.fn is None:
            raise ValueError("bad function")
        return self.fn(row)
    
    def get_related_columns(self):
        return self.related_columns

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



#
# ? name like 25 and column != 34 or datetime within (2020/01/05 2020/02/03)
# ? (or (and (like name 25) (!= column 34)) (within datetime 2020/01/05 2020/02/03))
# ? name like 25 && column != 34 || datetime between 2020/01/05 2020/02/03
#

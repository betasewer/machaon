import ast

from machaon.valuetype.predicate import predicate

#
class BadExpression(Exception):
    pass

#
# 1. トークンへの変換
#

TOKEN_TERM = 0x01
TOKEN_BLOCK_BEGIN = 0x02
TOKEN_TERM_END = 0x04
TOKEN_BLOCK_END = 0x10


def tokenize(expression):
    buffer = []
    def _flush(buf):
        if buf:
            yield "".join(buf)
            buf.clear()
    
    yield TOKEN_BLOCK_BEGIN

    for ch in expression:
        if ch == "(":
            yield from _flush(buffer)
            yield TOKEN_BLOCK_BEGIN
        elif ch == ")":
            yield from _flush(buffer)
            yield TOKEN_BLOCK_END
        else:
            buffer.append(ch)

    yield from _flush(buffer)
    yield TOKEN_BLOCK_END


#
# 2. 構文木の構築
#
def build_ast(cxt, tokens):
    blockstack = []
    for token in tokens:
        if token == TOKEN_BLOCK_BEGIN:
            blockstack.append([])

        elif token == TOKEN_BLOCK_END:
            if not blockstack:
                raise BadExpression("Could not find beginning of block")

            newblock = blockstack.pop()

            # 式を解析する
            expr = cxt.parse(*newblock)
            if not blockstack:
                # 全体のブロックの解析が終わった
                return expr
            
            # 上位のブロックの要素として追加する
            blockstack[-1].append(expr)
        
        else:
            # 文字部分を解析する
            if not blockstack:
                raise BadExpression("Could not find beginning of block")

            blockstack[-1].append(token)
    
    raise BadExpression("Could not find end of block")

#
# 2-1. 式を解析する
#
class expression_context:
    def __init__(self, typelib=None, predicatelib=None):
        self.typelib = typelib
        self.predlib = predicatelib

    # 2-1. 式の解析
    def parse(self, *tokens):
        operands = []
        for token in tokens:
            if isinstance(token, expression):
                operands.append(token)
            elif isinstance(token, str):
                if len(operands)>=2: # LEFT OP >RIGHT<
                    operands.append(token)
                else:
                    toks = token.split(maxsplit=2-len(operands))
                    operands.extend(toks)
        
        if len(operands) == 1:
            args = [operands[0]]
            opr = None
        elif len(operands) == 2:
            args = [operands[0]]
            opr = operands[1]
        elif len(operands) >= 3:
            args = [operands[0], *operands[2:]]
            opr = operands[1]
        else:
            raise BadExpression("empty expression")

        if opr is not None:
            opr = self.parse_operator(opr, args[0])    
        args = [self.parse_literal(x) for x in args]
        return expression(opr, args)

    # 2-2. リテラルの分析
    def parse_literal(self, s):
        # 1. Pythonのリテラルとみなす
        try:
            return ast.literal_eval(s)
        except ValueError:
            pass
        
        # 2. 述語とみなす
        if self.predlib is not None:
            pred = self.predlib.find_pred(s)
            if pred is not None:
                return pred
    
        # 10. 文字列とみなす
        return s

    # 2-3. 演算子の分析
    def parse_operator(self, name, left):
        # 左辺値の型に定義された演算子
        mood = None # type_traits
        if isinstance(left, predicate):
            mood = left.get_type()
        else:
            typename = str(left)
            mood = self.typelib.generate(typename)
        
        if mood is not None:
            opr = mood.get_operator(name)
            if opr is not None:
                return opr
        
        # 標準の演算子
        import operator
        opr = getattr(operator, name, None)
        if opr is not None:
            return opr
        
        # 左辺値に定義されたメソッドを呼び出す
        def lhs_operation(left, *args):
            if not hasattr(left, name):
                raise BadExpression("value '{}' has no method like '{}'".format(left, name))
            return getattr(left, name)(*args)
        return lhs_operation
    
#
#
#
class expression():
    def __init__(self, opr, args):
        self.opr = opr
        self.args = args
    
    def S(self):
        args = []
        for x in self.args:
            if isinstance(x, expression):
                args.append(x.S())
            elif isinstance(x, str):
                args.append("'{}'".format(x))
            else:
                args.append(str(x))
        return "({})".format(" ".join([self.opr, *args]))

    
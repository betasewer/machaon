import ast
from typing import Dict, Any, List, Sequence

from machaon.object.type import TypeTraits
from machaon.object.object import Object
from machaon.object.desktop import ObjectDesktop
from machaon.object.operator import parse_operator_expression


#
class BadExpressionError(Exception):
    pass

#
FORMULA_OPERAND_REF_SIGIL = "@"

#
# 2-1. 式を解析する
#
class FormulaParser:
    def __init__(self, 
            subject_type=None,
            objdesk=None
        ):
        self.objdesk = objdesk
        self.subject_type: TypeTraits = subject_type
        self.related_members: List[str] = [] 
        
    # 1. トークンを受け取る
    def parse(self, tokens):
        blockstack = []
        for token in tokens:
            if token == TOKEN_BLOCK_BEGIN:
                blockstack.append([])

            elif token == TOKEN_BLOCK_END:
                if not blockstack:
                    raise BadExpressionError("Could not find beginning of block")

                newblock = blockstack.pop()

                # 式を解析する
                expr = self.parse_block(*newblock)
                if not blockstack:
                    # 全体のブロックの解析が終わった
                    return expr
                
                # 上位のブロックの要素として追加する
                blockstack[-1].append(expr)
            
            else:
                # 文字部分を解析する
                if not blockstack:
                    raise BadExpressionError("Could not find beginning of block")

                blockstack[-1].append(token)
        
        raise BadExpressionError("Could not find end of block")

    # 2. 式の解析
    def parse_block(self, *tokens):
        operands = []
        for token in tokens:
            if isinstance(token, FormulaExpression):
                operands.append(token)
            elif isinstance(token, str):
                if len(operands)>=2: # LEFT OP >RIGHT<
                    operands.append(token)
                else: # >LEFT< OP RIGHT
                    toks = token.split()
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
            raise BadExpressionError("empty expression")

        argvalues = []
        for arg in args:
            if isinstance(arg, str):
                val = self.parse_arg_string(arg)
            else:
                val = arg
            argvalues.append(val)

        operator = None
        if opr is not None:
            operator = self.parse_operator(opr, argvalues[0])

        return FormulaExpression(operator, argvalues)

    # 3. リテラルの分析
    def parse_arg_string(self, s: str):
        # 1. 明示的リテラル表記 

        # 2. オブジェクトのメンバかどうか
        if s.startswith(FORMULA_OPERAND_REF_SIGIL):
            if self.subject_type is not None:
                name = s[1:]
                method = self.subject_type.get_method(name)
                if method is not None:
                    self.related_members.append(method.get_name())
                    return FormulaOperand(method.get_name(), method.get_result_typecode())

        # 3. Pythonのリテラルとみなす
        try:
            return ast.literal_eval(s)
        except Exception:
            pass

        # 4. 暗黙的リテラル
    
        # X. 暗黙的に文字列とみなす
        return s

    # 4. 演算子の分析
    def parse_operator(self, name, left):
        # 左辺値の型を取得
        lefttype = None
        if self.objdesk:
            if isinstance(left, FormulaOperand):
                lefttype = self.objdesk.get_type(left.get_typecode())
            elif isinstance(left, FormulaExpression):
                hint = left.get_eval_typehint()
                if hint:
                    lefttype = self.objdesk.get_type(hint)
            else:
                lefttype = self.objdesk.get_type(type(left))
        
        # オペレータを作成
        opr = parse_operator_expression(name, lefttype)
        return opr
    
    #
    def get_related_members(self):
        return self.related_members

#
#
#
class FormulaOperand():
    def __init__(self, member_name, typecode):
        self.member_name = member_name
        self.typecode = typecode
    
    def get_name(self):
        return self.member_name
    
    def get_typecode(self):
        return self.typecode

#
#
#
class FormulaExpression():
    def __init__(self, opr, operands):
        self.opr = opr
        self.operands = operands
    
    def eval(self, evalcontext):
        args = []
        for operand in self.operands:
            if isinstance(operand, FormulaExpression):
                arg = operand.eval(evalcontext)
            elif isinstance(operand, FormulaOperand):
                arg = evalcontext.get_member_value(operand.get_name()) # 値を取得する
            else:
                arg = operand
            args.append(arg)

        ret = self.opr(*args)
        return ret
    
    def get_eval_typehint(self):
        return self.opr.get_result_typehint()

    def S(self, *, debug_operator=False):
        # for debug purpose
        args = []
        for operand in self.operands:
            if isinstance(operand, FormulaExpression):
                args.append(operand.S(debug_operator=debug_operator))
            elif isinstance(operand, str):
                args.append("'{}'".format(operand))
            elif isinstance(operand, FormulaOperand):
                args.append("[operand {}]".format(operand.get_name()))
            else:
                args.append(str(operand))
        
        if debug_operator and self.opr:
            opr = self.opr.resolution()
        elif hasattr(self.opr, "__name__"):
            opr = self.opr.__name__
        else:
            opr = str(self.opr)
        return "({})".format(" ".join([opr, *args]))

#
#
#
class EvalContext():
    def get_member_value(self, member_name):
        raise NotImplementedError()

class ValuesEvalContext(EvalContext):
    # メンバ名と値が入った辞書を渡す
    def __init__(self, membervalues: Dict[str, Any]):
        self.membervalues = membervalues

    def get_member_value(self, member_name):
        if member_name in self.membervalues:
            return self.membervalues[member_name]
        raise BadExpressionError("オペランド'{}'に対する値がありません".format(member_name))


#
########################################################################################
#
# エントリクラス・関数
#
########################################################################################
#
class Formula():
    def __init__(self, expr, subject_type, related_members):
        self.expr = expr
        self.subject_type = subject_type
        self.related_members = related_members
    
    def get_related_members(self) -> List[str]:
        return self.related_members
    
    def create_values_context(self, subject_value):
        values = {}
        for member_name in self.related_members:
            meth = self.subject_type.get_method(member_name)
            if meth:
                val = meth.resolve(self.subject_type)(subject_value)
                values[member_name] = val
        return ValuesEvalContext(values)

    def __call__(self, evalcontext: EvalContext):
        return self.expr.eval(evalcontext)

#
# 式からパースする
#
def parse_formula(expression: str, object_desk: ObjectDesktop = None, subject_type: TypeTraits = None) -> Formula:
    parser = FormulaParser(subject_type, object_desk)
    tokens = tokenize_expression(expression)
    expr = parser.parse(tokens)
    return Formula(expr, subject_type, parser.get_related_members())

#
# 式の文字列をトークンへ変換
#
TOKEN_TERM = 0x01
TOKEN_BLOCK_BEGIN = 0x02
TOKEN_TERM_END = 0x04
TOKEN_BLOCK_END = 0x10

def tokenize_expression(expression):
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





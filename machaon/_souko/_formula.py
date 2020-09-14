import ast
from typing import Dict, Any, List, Sequence, Optional

from machaon.object.type import Type, TypeModule
from machaon.object.object import Object

# imported from...
# desktop
# object
#
#

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
            typemodule=None
        ):
        self.typemodule: Optional[TypeModule] = typemodule
        self.subject_type: Optional[Type] = subject_type
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

        # 引数リテラルを解析
        argvalues = []
        for arg in args:
            if isinstance(arg, str):
                val = self.parse_arg_string(arg)
            else:
                val = arg
            argvalues.append(val)
        
        # 左辺値の型を取得
        block_subject_type = None
        if self.typemodule is not None:
            left = argvalues[0]
            if isinstance(left, FormulaOperand):
                block_subject_type = self.typemodule.new(left.get_typecode())
            elif isinstance(left, FormulaExpression):
                hint = left.get_eval_typehint()
                if hint:
                    block_subject_type = self.typemodule.new(hint)
            else:
                block_subject_type = self.typemodule.new(type(left))

        # 演算子を取得
        operator = None
        if opr is not None:
            operator = parse_operator_expression(opr, block_subject_type)

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
                    return FormulaOperand(method.get_name(), method.get_first_result_typename())

        # 3. Pythonのリテラルとみなす
        try:
            return ast.literal_eval(s)
        except Exception:
            pass

        # 4. 単位つきリテラル
    
        # X. 暗黙的に文字列とみなす
        return s
    
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
def parse_formula(expression: str, typemodule: TypeModule = None, subject_type: Type = None) -> Formula:
    parser = FormulaParser(subject_type, typemodule)
    tokens = tokenize_expression(expression)
    expr = parser.parse(tokens)
    return Formula(expr, subject_type, parser.get_related_members())

#
# ----------------------------------------------------------------------------
#
#
#
# ----------------------------------------------------------------------------
#
SIGIL_OBJECT_ID = "@"

#
#
class Message:
    def __init__(self, reciever=None, selector=None, args=None):
        self.reciever = reciever
        self.selector = selector
        self.args = args or []
    
    def is_reciever_specified(self):
        return self.reciever is not None
    
    def is_selector_specified(self):
        return self.selector is not None
        
    def is_max_arg_specified(self):
        if self.selector:
            return len(self.args) == self.selector.get_max_arity()
        return False
    
    def is_min_arg_specified(self):        
        if self.selector:
            return len(self.args) == self.selector.get_min_arity()
        return False
    
    def get_reciever_type(self):
        pass
    
    def get_return_type(self):
        pass

#
# 式の文字列をトークンへ変換
#
TOKEN_TERM = 0x01
TOKEN_BLOCK_BEGIN = 0x02
TOKEN_BLOCK_END = 0x04

EXPECT_NOTHING = 0
EXPECT_RECIEVER = 0x10
EXPECT_SELECTOR = 0x20
EXPECT_ARGUMENT = 0x40

TERM_NEW_BLOCK_RECIEVER = 1
TERM_NEW_BLOCK_SELECTOR = 2
TERM_LAST_BLOCK_SELECTOR = 3
TERM_LAST_BLOCK_ARG = 4
TERM_NEW_BLOCK_AS_LAST_RECIEVER = 5
TERM_NEW_BLOCK_AS_LAST_ARG = 6
TERM_LAST_BLOCK_ARG_END = 7

#
#
#
class MessageParser():
    def __init__(self, expression):
        self.source = expression
        self._readings = []
        self._sequence = []

    # 1.0
    def read_token(self):
        buffer = []

        def _terms(buf):
            if not buf:
                return
            yield from "".join(buf).split()
            buf.clear()
        
        for ch in self.source:
            if ch == "(":
                yield from _terms(buffer)
                yield TOKEN_BLOCK_BEGIN
            elif ch == ")":
                yield from _terms(buffer)
                yield TOKEN_BLOCK_END
            else:
                buffer.append(ch)

        yield from _terms(buffer)

    #
    def parse_syntax(self, token):
        reading = self.get_cur_reading()
        
        if reading is None:
            expect = EXPECT_NOTHING
        elif not reading.is_reciever_specified():
            expect = EXPECT_RECIEVER
        elif not reading.is_selector_specified():
            expect = EXPECT_SELECTOR
        elif not reading.is_max_arg_specified():
            expect = EXPECT_ARGUMENT

        # ブロック開始指示
        if token == TOKEN_BLOCK_BEGIN:
            if expect == EXPECT_SELECTOR:
                raise SyntaxError("メッセージはセレクタになりません")

            if expect == EXPECT_ARGUMENT:
                return (TERM_NEW_BLOCK_AS_LAST_ARG, None)

            if expect == EXPECT_NOTHING or expect == EXPECT_RECIEVER:
                return (TERM_NEW_BLOCK_AS_LAST_RECIEVER, None)

        # ブロック終了指示
        if token == TOKEN_BLOCK_END:
            if expect == EXPECT_RECIEVER:
                raise SyntaxError("レシーバオブジェクトがありません")

            if expect == EXPECT_SELECTOR:
                raise SyntaxError("セレクタがありません")

            if expect == EXPECT_ARGUMENT:
                if not reading.is_min_arg_specified():
                    raise SyntaxError("引数が足りません")
                return (TERM_LAST_BLOCK_ARG_END, None) # デフォルト引数で埋める
            
            return (TERM_LAST_BLOCK_ARG_END, None)
        
        # オブジェクト参照
        if token.startswith(SIGIL_OBJECT_ID):
            if expect == EXPECT_SELECTOR:
                raise SyntaxError("セレクタが必要です")

            obj = parse_object_specifier(token)
            if expect == EXPECT_ARGUMENT:
                return (TERM_LAST_BLOCK_ARG, obj) # 前のメッセージの引数になる
            else:
                return (TERM_NEW_BLOCK_RECIEVER, obj) # 新しいメッセージのレシーバになる

        # 型名
        tt = select_type(token)
        if tt is not None:
            if expect == EXPECT_SELECTOR:
                raise SyntaxError("セレクタが必要です")

            if expect == EXPECT_ARGUMENT:
                raise SyntaxError("型は引数にとれません")
            
            return (TERM_NEW_BLOCK_RECIEVER, tt) # 新しいメッセージのレシーバになる
        
        # メソッドかリテラルか、文脈で判断
        if expect == EXPECT_SELECTOR:
            meth = select_method(token, reading.get_reciever_type())
            if meth is not None:
                return (TERM_LAST_BLOCK_SELECTOR, meth) # 前のメッセージのセレクタになる
            raise SyntaxError("不明なセレクタです：{}".format(token))
        
        if expect == EXPECT_ARGUMENT:
            arg = parse_arg_literal(token)
            return (TERM_LAST_BLOCK_ARG, arg) # 前のメッセージの引数になる

        if expect == EXPECT_RECIEVER:
            arg = parse_arg_literal(token)
            return (TERM_NEW_BLOCK_RECIEVER, arg) 

        if expect == EXPECT_NOTHING:
            if self._sequence:
                # セレクタになるかまず試す
                seqlast = self._sequence[-1]
                meth = select_method(token, seqlast.get_return_type())
                if meth is not None:
                    return (TERM_NEW_BLOCK_SELECTOR, seqlast, meth)

            # レシーバオブジェクトのリテラルとする
            arg = parse_arg_literal(token)
            return (TERM_NEW_BLOCK_RECIEVER, arg) 

    # 3 メッセージの樹を構築する
    def build_ast_step(self, syntax_element):
        code, *values = syntax_element
        if code == TERM_NEW_BLOCK_RECIEVER:
            new_msg = Message(values[0])
            self._readings.append(new_msg)

        elif code == TERM_NEW_BLOCK_SELECTOR:
            new_msg = Message(values[0], values[1])
            self._readings.append(new_msg)

        elif code == TERM_LAST_BLOCK_SELECTOR:
            self._readings[-1].set_selector(values[0])

        elif code == TERM_LAST_BLOCK_ARG:
            self._readings[-1].add_arg(values[0])
        
        elif code == TERM_NEW_BLOCK_AS_LAST_RECIEVER:
            new_msg = Message()
            self._readings[-1].set_reciever(new_msg)
            self._readings.append(new_msg)
        
        elif code == TERM_NEW_BLOCK_AS_LAST_ARG:
            new_msg = Message()
            self._readings[-1].add_arg(new_msg)
            self._readings.append(new_msg)
        
        elif code == TERM_LAST_BLOCK_ARG_END:
            r = self._readings.pop()
            self._sequence.append(r)

# ---------------------------------------------------------------

    
    #
    def get_cur_subject_type(self):
        if not self._readings:
            return None
        last = self._readings[-1]
        return last.get_subject_type()
    




#
#
#
def parse_message(self, tokens):
    blockstack = []
    for token in tokens:
        if token == TOKEN_BLOCK_BEGIN:
            blockstack.append(Message())

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
    
#
#
#
def parse_message_part(tokens, msgstack, sequence):
    new_block = False
    new_reciever = None
    new_selector = None
    
    # 解決したメッセージを取り出して移す
    def harvest_message_stack():
        while msgstack:
            if msgstack[-1].is_specified():
                sequence.append(msgstack.pop())
    
    #
    class Literal():
        def __init__(self, s):
            self.string = s

    # レシーバか、セレクタか、順に調べてためす
    token = next(tokens, None)
    while token:
        if token == TOKEN_BLOCK_BEGIN:
            new_block = True
            break

        if token.startswith(SIGIL_OBJECT_ID):
            obj = parse_object_specifier(token)
            new_reciever = obj
            break

        tt = select_type(token)
        if tt is not None:
            new_reciever = tt
            break
        
        mt = select_method(token)
        if mt is not None:
            new_selector = mt
            break
        
        new_reciever = Literal(token)
    
    # ブロック
    if new_block:
        new_msg = Message(None)

        if not msgstack:
            msgstack.append(new_msg)
            return
        
        if not msgstack[-1].is_selector_specified():
            msgstack[-1].append(new_msg)



    # 新しいレシーバ
    if new_reciever:
        new_msg = Message(new_reciever)

        if not msgstack:
            msgstack.append(new_msg)
            return

        if not msgstack[-1].is_selector_specified():
            # このメッセージが前のメッセージのセレクタになる
            msgstack[-1].set_selector(new_msg)
            harvest_message_stack()
            msgstack.append(new_msg)

        if not msgstack[-1].is_args_specified():
            # このメッセージが前のメッセージの引数になる
            msgstack[-1].add_arg(new_msg)
            harvest_message_stack()
            msgstack.append(new_msg)

            
        if not msgstack:
            # sequenceから2つ取り出して、それを宛先・セレクタとする
            if len(sequence)<2:
                raise SyntaxError("宛先のない引数です：{}".format(token))
            leftmsg1 = sequence.pop()
            leftmsg2 = sequence.pop()
            newmsg = Message(leftmsg1, leftmsg2)
            argval = parse_arg_literal(new_arg, newmsg)
            newmsg.add_arg(argval)
            msgstack.append(newmsg)
            harvest_message_stack()
    
    # 新しいセレクタ
    if new_selector:
        if not msgstack:
            # sequenceから一つ取り出して、それを宛先とする
            if not sequence:
                raise SyntaxError("宛先のないセレクタです：{}".format(token))
            leftmsg = sequence.pop()
            msgstack.append(Message(leftmsg, new_selector))
            harvest_message_stack()

        if not msgstack[-1].is_selector_specified():
            msgstack[-1].set_selector(new_selector)
            harvest_message_stack()

        if not msgstack[-1].is_args_specified():
            # セレクタではなく引数とみなす
            new_arg = new_selector
            new_selector = None
    
    # 新しい引数
    if new_arg:
        if not msgstack:
            # sequenceから2つ取り出して、それを宛先・セレクタとする
            if len(sequence)<2:
                raise SyntaxError("宛先のない引数です：{}".format(token))
            leftmsg1 = sequence.pop()
            leftmsg2 = sequence.pop()
            newmsg = Message(leftmsg1, leftmsg2)
            argval = parse_arg_literal(new_arg, newmsg)
            newmsg.add_arg(argval)
            msgstack.append(newmsg)
            harvest_message_stack()

        
        if not msgstack[-1].is_selector_specified():
            raise SyntaxError("宛先のない引数です：{}".format(token))
        
        if not msgstack[-1].is_args_specified():
            argval = parse_arg_literal(new_arg, msgstack[-1])
            msgstack[-1].add_arg(new_arg)
            harvest_message_stack()




                
                

            


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

    # 引数リテラルを解析
    argvalues = []
    for arg in args:
        if isinstance(arg, str):
            val = self.parse_arg_string(arg)
        else:
            val = arg
        argvalues.append(val)
    
    # 左辺値の型を取得
    block_subject_type = None
    if self.typemodule is not None:
        left = argvalues[0]
        if isinstance(left, FormulaOperand):
            block_subject_type = self.typemodule.new(left.get_typecode())
        elif isinstance(left, FormulaExpression):
            hint = left.get_eval_typehint()
            if hint:
                block_subject_type = self.typemodule.new(hint)
        else:
            block_subject_type = self.typemodule.new(type(left))

    # 演算子を取得
    operator = None
    if opr is not None:
        operator = parse_operator_expression(opr, block_subject_type)

    return FormulaExpression(operator, argvalues)






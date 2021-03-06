from typing import Sequence, List, Any, Tuple, Dict, DefaultDict, Optional, Generator, Iterable, Union
from collections import defaultdict

from machaon.core.type import Type, TypeModule
from machaon.core.object import Object
from machaon.core.message import MessageEngine, MemberGetter, select_method
from machaon.core.invocation import InvocationContext
from machaon.core.sort import parse_sortkey
from machaon.cui import get_text_width

#
#
#
class FoundItem():
    """ @type
    データ集合に含まれる値。
    typename:
        FoundItem
    """
    def __init__(self, object=None, index=None):
        self.object = object
        self.index = index
    


#
#
#
class ObjectTuple():  
    """ @type
    異なる型のオブジェクトを格納する配列。
    Typename: Tuple
    """
    def __init__(self, objects):
        self.objects = objects

    # 要素にアクセスする
    def __iter__(self):
        for o in self.objects:
            yield o.value

    #
    # メンバ値へのアクセス
    #
    def at(self, index):
        """ @method
        値をインデックスで取得する。
        Params:
            index(int): インデックス
        Returns:
            Object: 値
        """
        return self.objects[index]
    
    # split find-if [@_ reg-match heck]
    def find(self, value):
        """ @method
        値を検索して取得する。（完全一致）
        Params:
            value(Any): 検索する値
        Returns:
            FoundItem: 値
        """
        # 順に検索
        for i, o in enumerate(self.objects):
            if o.value == value:
                return FoundItem(o, i)
        return FoundItem() # 見つからなかった

    def count(self):
        """ @method
        数を取得する。
        Params:
        Returns:
            int: 個数
        """
        return len(self.objects)
    
    def clone(self):
        """ @method
        すべての値の浅いコピーを作成する。
        Returns:
            Tuple: コピーされたタプル
        """
        objs = []
        for o in self.objects:
            objs.append(o.copy())
        return ObjectTuple(objs)
    
    def convertas(self, context, type):
        """ @method context alias-name [as]
        すべての値を指定の型に変換する。
        Params:
            type(Type): 新しい型
        Returns:
            Tuple: 結果のタプル
        """
        objs = []
        for x in self.objects:
            # 変換コンストラクタを呼び出す
            try:
                v = type.conversion_construct(context, x.value)
            except:
                continue
            objs.append(Object(type, v))
        return ObjectTuple(objs)

    #
    # アルゴリズム関数
    #
    def filter(self, context, predicate):
        """ @method context
        行を絞り込む。
        Params:
            predicate(Function): 述語関数
        """
        # 関数を行に適用する
        def fn(subject):
            return predicate.run_function(subject, context).value
        
        self.objects = list(filter(fn, self.objects))
    
    def sort(self, context, key):
        """ @method context
        行の順番を並べ替える。
        Params:
            key(Function): 並べ替え関数
        """
        def sortkey(subject):
            return key.run_function(subject, context).value

        self.objects.sort(key=sortkey)
        
    def foreach(self, context, predicate):
        """ @method context
        値に関数を適用する。
        Params:
            predicate(Function): 述語関数
        """
        for o in self.objects:
            predicate.run(o, context)

    def map(self, context, predicate):
        """ @method context
        値に関数を適用し、新しいタプルとして返す。
        Params:
            predicate(Function): 述語関数
        Returns:
            Tuple: 新しいタプル
        """
        rets: List[Object] = []
        for o in self.objects:
            r = predicate.run_function(o, context)
            rets.append(r)
        return ObjectTuple(rets)
    
    def reduce_(self, context, predicate, start=None):
        """ @method context alias-name [reduce]
        要素に次々と関数を適用し、一つの値として返す。
        Params:
            predicate(Function): 述語関数
            start(Object): *初期値
        Returns:
            Object: 結果
        """
        if start is None:
            if not self.objects:
                raise ValueError("タプルは空です")
            cur = self.objects[0]
            objs = self.objects[1:]
        else:
            cur = start
            objs = self.objects
        
        subject_type = Type({
            "Typename" : "TupleReduceSubject",
            "0": "Object",
            "1": "Object"
        }).load()
        for o in objs:
            subject = subject_type.new_object({"0": cur, "1": o})
            cur = predicate.run_function(subject, context)
            
        return cur

    # iota: 1 :to 10 reduce: [@/left + @/right] :start 
    
    #
    #
    #
    def join(self, sep):
        """ @method
        セパレータ文字で値を一つの文字列に連結する。
        Params:
            sep(Str): セパレータ文字
        Returns:
            Str: 結果の文字列
        """
        strs = [x.to_string() for x in self.objects]
        return sep.join(strs)

    #
    # オブジェクト共通関数
    #
    def summarize(self):
        if len(self.objects) < 5:
            summ = [o.summary() for o in self.objects]
            return ", ".join(summ)
        else:
            summ1 = [o.summary() for o in self.objects[0:2]]
            summ2 = [o.summary() for o in self.objects[-2:]]
            return ", ".join(summ1) + "..." + ", ".join(summ2)

    def pprint(self, app):
        if len(self.objects) == 0:
            text = "空です" + "\n"
            app.post("message", text)
        else:
            context = app.get_process().get_last_invocation_context() # 実行中のコンテキスト
            app.post("object-tupleview", data=self, context=context)

    def conversion_construct(self, context, value):
        try:
            iter(value)
        except TypeError:
            value = (value,)
        
        # 型を値から推定する
        objs = []
        for val in value:
            if isinstance(val, Object):
                objs.append(val)
            else:
                valtype = context.deduce_type(val)
                objs.append(Object(valtype, val))

        return ObjectTuple(objs)

from typing import Sequence, List, Any, Tuple, Dict, DefaultDict, Optional, Generator, Iterable, Union
from collections import defaultdict

from machaon.core.type import Type, TypeModule
from machaon.core.object import Object
from machaon.core.message import MessageEngine, MemberGetter, select_method
from machaon.core.invocation import InvocationContext
from machaon.core.sort import parse_sortkey
from machaon.cui import get_text_width
from machaon.types.fundamental import NotFound


#
#
#
class ElemObject():
    """ @type
    データ集合に含まれる値。
    """
    def __init__(self, object, key, value=None):
        self.object = object
        self.key = key
        self.value = value
    
    def get(self):
        """ @method [object]
        関連付けられたオブジェクトを得る。
        Returns:
            Object:
        """
        return self.object
 
    def getkey(self):
        """ @method alias-name [key]
        位置を示すキーを得る。
        Returns:
            Object:
        """
        return self.key

    def getvalue(self):
        """ @method alias-name [value]
        関連付けられた値を得る。
        Returns:
            Object:
        """
        return self.value

#
#
#
class ObjectTuple():  
    """
    異なる型のオブジェクトを格納する配列。
    """
    def __init__(self, objects):
        self.objects = objects

    # 要素にアクセスする
    def __iter__(self):
        for o in self.objects:
            yield o.value
        
    def __len__(self):
        return len(self.objects)

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
    
    def find(self, context, app, value):
        """ @method task context
        値を検索して取得する。（完全一致）
        Params:
            value(Any): 検索する値
        Returns:
            FoundItem: 値
        """
        # 順に検索
        for i, o in enumerate(self.objects):
            if o.value == value:
                index = context.new_object(i, type="Int")
                return ElemObject(o, index)        
        raise NotFound() # 見つからなかった
    
    def pick(self, app, value):
        """ @method task [#]
        値を検索して取得する。
        前方一致で見つからなければ後方一致の結果を返す。
        Params:
            value(Str):
        Returns:
            Object:
        """
        tlo = None
        for i, o in enumerate(self.objects):
            s = o.to_string()
            if s.startswith(value):
                return o
            elif s.endswith(value):
                tlo = o
        if tlo:
            return tlo
        raise NotFound()

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
                v = type.construct(context, x.value)
            except:
                continue
            objs.append(Object(type, v))
        return ObjectTuple(objs)

    #
    # アルゴリズム関数
    #
    def filter(self, context, _app, predicate):
        """ @task context [&]
        行を絞り込む。
        Params:
            predicate(Function): 述語関数
        """
        # 関数を行に適用する
        def fn(subject):
            return predicate.run_function(subject, context).test_truth()
        
        self.objects = list(filter(fn, self.objects))
    
    def sort(self, context, _app, key):
        """ @task context
        行の順番を並べ替える。
        Params:
            key(Function): 並べ替え関数
        """
        def sortkey(subject):
            return key.run_function(subject, context).test_truth()

        self.objects.sort(key=sortkey)
        
    def foreach(self, context, _app, predicate):
        """ @task context [%]
        値に関数を適用する。
        Params:
            predicate(Function): 述語関数
        """
        for o in self.objects:
            predicate.run_function(o, context)

    def map(self, context, _app, predicate):
        """ @task context
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
    
    def reduce_(self, context, _app, predicate, start=None):
        """ @task context alias-name [reduce]
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
        
        for o in objs:
            subject = context.new_object({"0": cur, "1": o})
            cur = predicate.run_function(subject, context)
            
        return cur

    # 1 to 10 reduce [@.left + @.right]
    
    #
    #
    #
    def push(self, value):
        """ @method
        要素を最後に追加する。
        Params:
            value(Object): 
        """
        self.objects.append(value)
    
    def pop(self):
        """ @method
        最後の要素を取り出す。
        Returns:
            Object:
        """
        return self.objects.pop()
    
    def shift(self):
        """ @method
        最初の要素を取り出す。
        Returns:
            Object:
        """
        return self.objects.pop(0)
    
    def unshift(self, value):
        """ @method
        要素を最初に追加する。
        Params:
            value(Object): 
        """
        self.objects.insert(0, value)

    def insert(self, pos, value):
        """ @method
        要素をある位置に挿入する。
        Params:
            pos(int):
            value(Object): 
        """
        self.objects.insert(pos, value)
    
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

    # 内部使用
    def values(self):
        return [x.value for x in self.objects]

    #
    # オブジェクト共通関数
    #
    def constructor(self, context, value, homotype=None):
        """ @meta extra-args """
        try:
            iter(value)
        except TypeError:
            value = (value,)
        
        objs = []
        # 型を値から推定する
        for val in value:
            if not isinstance(val, Object):
                val = context.new_object(val, type=homotype)
            objs.append(val)

        return ObjectTuple(objs)
    
    def summarize(self):
        """ @meta """
        if len(self.objects) < 5:
            summ = [o.summary() for o in self.objects]
            return "{}".format(", ".join(summ))
        else:
            summ1 = [o.summary() for o in self.objects[0:2]]
            summ2 = [o.summary() for o in self.objects[-2:]]
            return "{}".format(", ".join(summ1) + "..." + ", ".join(summ2))

    def pprint(self, app):
        """ @meta """
        if len(self.objects) == 0:
            text = "空です" + "\n"
            app.post("message", text)
        else:
            context = app.get_process().get_last_invocation_context() # 実行中のコンテキスト
            columns = ["値", "型"]
            rows = []
            for i, o in enumerate(self.objects):
                sm = o.summary()  
                tn = o.get_typename()
                rows.append((i, [sm, tn]))
            app.post("object-sheetview", rows=rows, columns=columns, context=context)

from machaon.core.symbol import full_qualified_name

METHODS_BOUND_TYPE_TRAIT_INSTANCE = 1
METHODS_BOUND_TYPE_INSTANCE = 2

#
# 型パラメータを与えられたインスタンス。
# ・オブジェクトの生成
# ・代入可能性の判定
#
class TypeProxy:
    def get_typedef(self):
        """ 型定義オブジェクトを返す
        Returns:
            Type: 
        """
        raise NotImplementedError()
    
    def get_value_type(self):
        """ 値型を返す
        Returns:
            type:
        """
        raise NotImplementedError()
    
    def get_typename(self):
        """ 型名を返す
        Returns:
            Str: 
        """
        raise NotImplementedError()

    def get_conversion(self):
        """ 型宣言を返す 
        Returns:
            Str:
        """
        raise NotImplementedError()

    def get_describer(self, mixin):
        """ 実装定義オブジェクトを返す
        Params:
            mixin(Int): ミキシン実装のインデックス
        Returns:
            TypeDescriber:
        """
        raise NotImplementedError()

    def get_describer_qualname(self, mixin=None):
        """ 実装定義オブジェクトの名前を返す
        Returns:
            Str:
        """
        describer = self.get_describer(mixin)
        return describer.get_full_qualname()
    
    def get_document(self):
        """
        Returns:
            Str:
        """
        raise NotImplementedError()
    
    def check_type_instance(self, type):
        """ 互換性のあるTypeインスタンスか """
        raise NotImplementedError()

    def check_value_type(self, valtype):
        """ 互換性のある値型か """
        raise NotImplementedError()
    
    def instantiate(self, context, args):
        """ 型引数を型変換し、束縛したインスタンスを生成する """
        raise NotImplementedError()

    def instantiate_params(self):
        raise NotImplementedError()
    
    def instantiate_args(self, context, argvals, *, params=None): # paramsはテスト用
        """ 引数を型チェックし生成する """
        from machaon.core.method import Method
        method = Method(params=self.instantiate_params() if params is None else params)
        argvals = method.make_argument_row(context, argvals, construct=True)
        return argvals

    # メソッド関連
    def select_method(self, name):
        """ メソッドを名前で検索する
        Returns:
            Optional[Method]:
        """
        raise NotImplementedError()
        
    def is_selectable_method(self, name):
        """ メソッドが存在するか確認する
        Returns:
            Bool:
        """
        raise NotImplementedError()

    def enum_methods(self):
        """ メソッドを列挙する
        Yields:
            Tuple[List[str], Method]: メソッド名のリスト、メソッドオブジェクト
        """
        raise NotImplementedError()
    
    def get_methods_bound_type(self):
        """ メソッドへのインスタンスの紐づけ方のタイプを返す
        Returns:
            Int: METHODS_BOUND_TYPE_XXX
        """
        raise NotImplementedError()

    def is_selectable_instance_method(self):
        """ インスタンスメソッドを参照可能か        
        """
        raise NotImplementedError()

    # 特殊メソッド
    def constructor(self, context, args):
        """ オブジェクトを構築する """
        raise NotImplementedError()
    
    def construct(self, context, value, *args):
        """ オブジェクトを構築して値を返す """
        # 同じ型ならコンストラクタを呼ばない
        if self.check_value_type(type(value)):
            return value
        # コンストラクタを呼び出す
        # TODO: Noneが渡された場合、デフォルトコンストラクタに分岐？
        ret = self.constructor(context, (value, *args))
        # 返り値を検査する
        if not self.check_value_type(type(ret)):
            raise ConstructorReturnTypeError(self, type(ret))
        return ret

    def construct_obj(self, context, value, *args):
        """ Objectのインスタンスを返す """
        from machaon.core.object import Object
        if isinstance(value, Object):
            value = value.value
        convval = self.construct(context, value, *args)
        return self.new_object(convval)
    
    def new_object(self, value, *, object_type=None):
        """ この型のオブジェクトを作る。型変換は行わない """
        from machaon.core.object import Object
        if isinstance(value, Object):
            if value.type.check_type_instance(self):
                raise ValueError("'{}' -> '{}' 違う型のオブジェクトです".format(value.get_typename(), self.typename))
            return value
        else:
            if not self.check_value_type(type(value)):
                raise ValueError("'{}' -> '{}' 値の型に互換性がありません".format(type(value).__name__, self.typename))
            if object_type is None:
                return Object(self, value)
            else:
                return object_type(self, value)

    def rebind_constructor(self, args):
        """ コンストラクタ引数を新たに束縛しなおしたインスタンスを作成する """
        t = self.get_typedef()
        if t is None:
            raise ValueError("No typedef is available")
        from machaon.core.type.instance import TypeInstance
        return TypeInstance(t, args)

    def stringify_value(self, value):
        raise NotImplementedError()
    
    def summarize_value(self, value):
        raise NotImplementedError()

    def pprint_value(self, app, value):
        raise NotImplementedError()
    
    #
    # 特殊型の判定
    #
    def is_none_type(self):
        from machaon.core.type.fundamental import NoneType
        return isinstance(self, NoneType)
    
    def is_object_collection_type(self):
        from machaon.core.type.fundamental import ObjectCollectionType
        return isinstance(self, ObjectCollectionType)



class RedirectProxy(TypeProxy):
    # typedef の先の実装に転送する
    def redirect(self):
        raise NotImplementedError()
    
    def get_value_type(self):
        return self.redirect().get_value_type()
    
    def get_typename(self):
        return self.redirect().get_typename()

    def get_conversion(self):
        return self.redirect().get_conversion()

    def get_describer(self, mixin):
        return self.redirect().get_describer(mixin)

    def get_describer_qualname(self, mixin=None):
        return self.redirect().get_describer_qualname(mixin)

    def get_document(self):
        return self.redirect().get_document()
    
    def check_type_instance(self, type):
        return self.redirect().check_type_instance(type)

    def check_value_type(self, valtype):
        return self.redirect().check_value_type(valtype)
        
    def instantiate(self, context, args):
        return self.redirect().instantiate(context, args)

    def instantiate_params(self):
        return self.redirect().instantiate_params()

    def select_method(self, name):
        return self.redirect().select_method(name)

    def is_selectable_method(self, name):
        return self.redirect().is_selectable_method(name)

    def enum_methods(self):
        return self.redirect().enum_methods()
    
    def get_methods_bound_type(self):
        return self.redirect().get_methods_bound_type()

    def is_selectable_instance_method(self):
        return self.redirect().is_selectable_instance_method()

    def constructor(self, context, args, typeargs=None):
        return self.redirect().constructor(context, args, typeargs)

    def stringify_value(self, value):
        return self.redirect().stringify_value(value)
    
    def summarize_value(self, value):
        return self.redirect().summarize_value(value)

    def pprint_value(self, spirit, value):
        return self.redirect().pprint_value(spirit, value)
    

class DefaultProxy(TypeProxy):
    # デフォルト値を提供する
    def get_typedef(self):
        return None
    
    def get_document(self):
        return "<no document>"

    def get_methods_bound_type(self):
        return METHODS_BOUND_TYPE_INSTANCE

    def is_selectable_instance_method(self):
        return False


#
# エラー
#
class ConstructorReturnTypeError(Exception):
    """ コンストラクタの返り値を検証する """
    def __str__(self):
        t, vt = self.args
        return "'{}.constructor'の返り値型'{}'は値型'{}'と互換性がありません".format(
            t.get_conversion(), 
            full_qualified_name(vt),
            full_qualified_name(t.get_value_type())
        )

class TypeConversionError(Exception):
    """ 引数での型チェックの失敗 """
    def __init__(self, srctype, desttype):
        if not isinstance(srctype, type) or not isinstance(desttype, str):
            raise TypeError("TypeConversionError requires args (type, str), but: ({}, {})".format(srctype, desttype))
        super().__init__(srctype, desttype)

    def __str__(self):
        srctype, desttype = self.args
        return "'{}'型の引数に'{}'型の値を代入できません".format(desttype, full_qualified_name(srctype))

# 型宣言における間違い
class BadTypeDeclaration(Exception):
    pass

# メソッド宣言における間違い
class BadMemberDeclaration(Exception):
    pass

# メソッド実装を読み込めない
class BadMethodDelegation(Exception):
    pass

# サポートされない
class UnsupportedMethod(Exception):
    pass



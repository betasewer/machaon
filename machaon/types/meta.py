"""
型のtrait実装を直接操作する
"""
from machaon.core.importer import attribute_loader


class Meta:
    def __init__(self, describer, *mixins, value=False):
        self._describer = describer
        self._mixins = mixins or []
        self._trait = not value
    
    def constructor(self, *args):
        """ この型のオブジェクトを作成する """
        return self._describer.constructor(self._describer, *args)

    def try_constructor(self, *args, default=None):
        """ 例外を許容する """
        try:
            return self.constructor(*args)
        except:
            return default

    def stringify(self, value):
        """ この型のオブジェクトを引数にとり、文字列として返す """
        if self._trait:
            return self._describer.stringify(self._describer, value)
        else:
            return self._describer.stringify(value)
    
    def pprint(self, app, value):
        """ この型のオブジェクトを引数にとり、文字列として表示する """
        if self._trait:
            return self._describer.pprint(self._describer, value, app)
        else:
            return self._describer.pprint(value, app)
    
    def get_method(self, method_name):
        """ 任意のメソッドを取り出す """
        def bind(fn):
            def wrapper(*a, **kwa):
                return fn(self._describer, *a, **kwa)
            return wrapper
                
        m = getattr(self._describer, method_name, None)
        if m is not None:
            if self._trait:
                return bind(m)
            else:
                return m
        for mixin in self._mixins:
            mi = getattr(mixin, method_name, None)
            if mi is not None:
                return bind(mi)
        return None

    def __getattr__(self, key):
        """ metaのメンバとしてメソッドを取得する """
        mth = self.get_method(key)
        if mth is not None:
            return mth
        raise KeyError(key)


class DefinedMeta:
    def __call__(self, describer, *mixins, value=False):
        def loadclass(x):
            if isinstance(x, str):
                return attribute_loader(x)() 
            else:
                return x

        d = loadclass(describer)
        mxs = [loadclass(x) for x in mixins]
        return Meta(d, *mxs, value=value)

    #
    # ショートカット
    #
    def _defined(desc, *mixins, value=False):
        def getter(self) -> Meta:
            return self(desc, *mixins, value=value)
        return property(fget=getter)

    # numeric
    LocaleInt       = _defined("machaon.types.numeric.LocaleInt")
    LocaleFloat     = _defined("machaon.types.numeric.LocaleFloat")
    # dateandtime
    Date            = _defined("machaon.types.dateandtime.DateType", "machaon.types.dateandtime.DateRepresent")
    Datetime        = _defined("machaon.types.dateandtime.DatetimeType")
    Time            = _defined("machaon.types.dateandtime.TimeType")


meta = DefinedMeta()




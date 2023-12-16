"""
型のtrait実装を直接操作する
"""
from machaon.core.importer import attribute_loader


class Meta:
    def __init__(self, describer, ctorname=None, *, value=False):
        self._describer = describer
        self._ctorname = ctorname
        self._trait = not value
    
    def constructor(self, *args):
        """ この型のオブジェクトを作成する """
        ctormethod = "from_"+self._ctorname if self._ctorname else "constructor"
        ctor = getattr(self._describer, ctormethod)
        return ctor(self._describer, *args)

    def try_constructor(self, *args, default=None):
        """ 例外を許容する """
        try:
            return self.constructor(*args)
        except:
            return default

    def stringify(self, value):
        """ この型のオブジェクトを引数にとり、文字列として返す """
        strmethod = self._ctorname if self._ctorname else "stringify"
        strg = getattr(self._describer, strmethod)
        if self._trait:
            return strg(self._describer, value)
        else:
            return strg(value)
    
    def pprint(self, app, value):
        """ この型のオブジェクトを引数にとり、文字列として表示する """
        if self._trait:
            return self._describer.pprint(self._describer, value, app)
        else:
            return self._describer.pprint(value, app)
    
    def call(self, method_name, *args, **kwargs):
        """ 任意のメソッドを呼び出す """
        m = getattr(self._describer, method_name)
        if self._trait:
            return m(self._describer, *args, **kwargs)
        else:
            return m(*args, **kwargs)

    
class MetaChoice:
    def __init__(self, types):
        self._choice = list(types)

    def select_constructor(self, *args):
        v = None
        for t in self._choice:
            try:
                v = t.constructor(*args)
            except:
                continue
            else:
                return t, v
        return None, None

    def constructor(self, *args):
        t, v = self.select_constructor(*args)
        if t is None:
            raise ValueError("No match constructor for ({})".format(args))
        return v

    def try_constructor(self, *args, default=None):
        t, v = self.select_constructor(*args)
        if t is None:
            return default
        else:
            return v




class DefinedMeta:
    def make(self, describer, ctorname=None, **kwargs):
        if isinstance(describer, str):
            d = attribute_loader(describer)()
        else:
            d = describer
        return Meta(d, ctorname, **kwargs)

    def __call__(self, describer, ctorname=None, **kwargs):
        return self.make(describer, ctorname, **kwargs)
    
    def choice(self, *types):
        return MetaChoice(types)

    #
    # ショートカット
    #
    def _shortcut(desc, ctorname=None, **kwargs):
        def getter(self) -> Meta:
            return self.make(desc, ctorname, **kwargs)
        return property(fget=getter)

    # numeric
    LocaleInt       = _shortcut("machaon.types.numeric.LocaleInt")
    LocaleFloat     = _shortcut("machaon.types.numeric.LocaleFloat")
    # dateandtime
    Date            = _shortcut("machaon.types.dateandtime.DateType")
    Datetime        = _shortcut("machaon.types.dateandtime.DatetimeType")
    Time            = _shortcut("machaon.types.dateandtime.TimeType")
    DateSeparated   = _shortcut("machaon.types.dateandtime.DateRepresent", "joined")
    MonthSeparated  = _shortcut("machaon.types.dateandtime.DateRepresent", "joined_month")
    Date8           = _shortcut("machaon.types.dateandtime.DateRepresent", "yyyymmdd")
    Date4           = _shortcut("machaon.types.dateandtime.DateRepresent", "mmdd")
    Month           = _shortcut("machaon.types.dateandtime.DateRepresent", "this_year_month")
    Day             = _shortcut("machaon.types.dateandtime.DateRepresent", "this_month_day")
    YearLowMonth    = _shortcut("machaon.types.dateandtime.DateRepresent", "yearlow_month")
    YearLowDate     = _shortcut("machaon.types.dateandtime.DateRepresent", "yearlow_date")


meta = DefinedMeta()




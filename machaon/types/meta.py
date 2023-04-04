"""
型のtrait実装を直接操作する
"""
from machaon.core.importer import attribute_loader


class Meta:
    def __init__(self, describer, *, value=False):
        self._describer = describer
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
    
    def convert_stringify(self, *args, dest=None):
        """ この型のオブジェクトを作成し、そのまま文字列にして返す """
        o = self.constructor(*args)
        if dest:
            return dest.stringify(o)
        else:
            return self.stringify(o)

    
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

    def convert_stringify(self, *args, dest=None, default=None):
        """ この型のオブジェクトを作成し、そのまま文字列にして返す """
        t, v = self.select_constructor(*args)
        if dest is not None:
            if t is None:
                v = default
            return dest.stringify(v)
        else:
            if t is None:
                raise ValueError("No match constructor for ({})".format(args))
            return t.stringify(v)




class DefinedMeta:
    def get(self, describer, **kwargs):
        if isinstance(describer, str):
            d = attribute_loader(describer)()
        else:
            d = describer
        return Meta(d, **kwargs)

    def __call__(self, describer, **kwargs):
        return self.get(describer, **kwargs)
    
    def choice(self, *types):
        return MetaChoice(types)

    #
    # ショートカット
    #
    def _shortcut(dest, **kwargs):
        def getter(self):
            return self.get(dest, **kwargs)
        return property(fget=getter)

    # numeric
    LocaleInt       = _shortcut("machaon.types.numeric.LocaleInt")
    LocaleFloat     = _shortcut("machaon.types.numeric.LocaleFloat")
    # dateandtime
    Date            = _shortcut("machaon.types.dateandtime.DateType")
    Datetime        = _shortcut("machaon.types.dateandtime.DatetimeType")
    Time            = _shortcut("machaon.types.dateandtime.TimeType")
    DateSeparated   = _shortcut("machaon.types.dateandtime.DateSeparated")
    MonthSeparated  = _shortcut("machaon.types.dateandtime.MonthSeparated")
    Date8           = _shortcut("machaon.types.dateandtime.Date8")
    Date4           = _shortcut("machaon.types.dateandtime.Date4")
    Month           = _shortcut("machaon.types.dateandtime.Month")
    Day             = _shortcut("machaon.types.dateandtime.Day")
    YearLowMonth    = _shortcut("machaon.types.dateandtime.YearLowMonth")
    YearLowDate     = _shortcut("machaon.types.dateandtime.YearLowDate")


meta = DefinedMeta()




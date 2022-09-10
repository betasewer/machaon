"""
型のtrait実装を直接操作する
"""
from machaon.core.importer import attribute_loader
from machaon.types.numeric import Oct


class Meta:
    def __init__(self, describer, *, valueclass=False):
        self._describer = describer
        self._trait = not valueclass
    
    def constructor(self, *args):
        """ この型のオブジェクトを作成する """
        return self._describer.constructor(self._describer, *args)

    def stringify(self, value):
        """ この型のオブジェクトを引数にとり、文字列として返す """
        if self._trait:
            return self._describer.stringify(self._describer, value)
        else:
            return self._describer.stringify(value)
    
    def pprint(self, app, value):
        """ この型のオブジェクトを引数にとり、文字列として返す """
        if self._trait:
            return self._describer.pprint(self._describer, value, app)
        else:
            return self._describer.pprint(value, app)
    
    def convert_stringify(self, *args):
        """ この型のオブジェクトを作成し、そのまま文字列にして返す """
        o = self.construct(*args)
        return self.stringify(o)
    

class DefinedMeta:
    def get(self, describer, **kwargs):
        if isinstance(describer, str):
            d = attribute_loader(describer)()
        else:
            d = describer
        return Meta(d, **kwargs)

    def __call__(self, describer, **kwargs):
        return self.get(describer, **kwargs)

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
    DateSeparated   = _shortcut("machaon.types.dateandtime.DateSeparated")
    Date8           = _shortcut("machaon.types.dateandtime.Date8")
    Date4           = _shortcut("machaon.types.dateandtime.Date4")
    Month           = _shortcut("machaon.types.dateandtime.Month")
    Day             = _shortcut("machaon.types.dateandtime.Day")
    YearLowMonth    = _shortcut("machaon.types.dateandtime.YearLowMonth")
    YearLowDate     = _shortcut("machaon.types.dateandtime.YearLowDate")


meta = DefinedMeta()

import datetime
import time

def parse_date(s):
    # YYYY/MM/DD
    parts = s.split("/")
    if len(parts) < 3:
        raise ValueError("不正な日付の形式です: "+ s)
    y, m, d = [int(x) for x in parts]
    return y, m, d

def parse_time(s):
    # HH:MM.SS
    h = None
    m = None
    c = None
    sh, sep, s = s.partition(":")
    if sep:
        h = int(sh)
    sm, sep, s = s.partition(".")
    if sep:
        m = int(sm)
        c = int(s)
    else:
        m = int(s)
    return h, m, c


def UTCOffset(utc_delta) -> datetime.tzinfo:
    """ UTCからの差分で表されるタイムゾーン """
    if utc_delta < 0:
        delta = -datetime.timedelta(hours=-utc_delta)
    else:
        delta = datetime.timedelta(hours=utc_delta)

    class _UTCOffset(datetime.tzinfo):
        def __repr__(self):
            return self.tzname(self)

        def utcoffset(self, dt):
            return delta

        def tzname(self, dt):
            return "UTC{+d}".format(utc_delta)

        def dst(self, dt):
            return datetime.timedelta(0)
        
    return _UTCOffset()

# 
#
#
class DatetimeType:
    """ @type trait [Datetime]
    日付と時刻
    ValueType:
        datetime.datetime
    """
    def constructor(self, v=None, m=None, d=None, h=None, mm=None, s=None):
        """ @meta 
        Params:
            v?(Int|Str|None): 西暦年/時刻表現
            m?(Int): 月
            d?(Int): 日
            h?(Int): 時間
            mm?(Int): 分
            s?(Int): 秒
        """
        if isinstance(v, int):
            if m is None or d is None:
                raise ValueError("指定された引数が足りません")
            if h is None or mm is None or s is None:
                return datetime.datetime(v, m, d)
            else:
                return datetime.datetime(v, m, d, h, mm, s)

        # 2009/12/01/12:50.49
        if isinstance(v, str):
            parts = v.split("/")
            if len(parts) >= 3:
                y, m, d = parse_date(v)
                if len(parts) == 4:
                    h, n, c = parse_time(parts[3])
                    return datetime.datetime(y, m, d, h, n, c)
                else:
                    return datetime.datetime(y, m, d)

        raise ValueError("不正な日付の形式です: " + v)

    def stringify(self, date):
        """ @meta """
        return date.strftime("%Y/%m/%d (%a) %H:%M.%S")

    def from_timestamp(self, value):
        """ @method external
        Params:
            value(Float):
        """
        return datetime.datetime.fromtimestamp(value)
    
    def from_timestamp_utc(self, value):
        """ @method external
        Params:
            value(Float): 
        """
        return datetime.datetime.utcfromtimestamp(value)
    
    def from_ordinal(self, value):
        """ @method external
        Params:
            value(Int):
        """
        return datetime.datetime.fromordinal(value)
    
    def from_iso(self, value):
        """ @method external
        Params:
            value(Str):
        """
        return datetime.datetime.fromisoformat(value)
    
    def now(self, tz=None):
        """ @method external
        現在の時刻を返す。
        Params:
            tz(Timezone): 
        """
        if not isinstance(tz, Timezone):
            tz = None
        return datetime.datetime.now(tz)

    def utcnow(self):
        """ @method external
        現在の時刻を返す。
        """
        return datetime.datetime.utcnow()
    
    #
    # 取得
    #
    def year(self, d):
        """ @method
        年
        Returns:
            Int:
        """
        return d.year

    def month(self, d):
        """ @method
        月
        Returns:
            Int:
        """
        return d.month

    def day(self, d):
        """ @method
        日
        Returns:
            Int:
        """
        return d.day

    def hour(self, d):
        """ @method
        時間（24）
        Returns:
            Int:
        """
        return d.hour

    def minute(self, d):
        """ @method
        分
        Returns:
            Int:
        """
        return d.minute

    def second(self, d):
        """ @method
        秒
        Returns:
            Int:
        """
        return d.second
        
    def microsecond(self, d):
        """ @method
        マイクロ秒
        Returns:
            Int:
        """
        return d.microsecond

    def weekday(self, d):
        """ @method
        曜日。（月が0にはじまり、日が6に終わる）
        Returns:
            Int: 0-6
        """
        return d.weekday()
        
    def isoweekday(self, d):
        """ @method
        曜日。（月が1にはじまり、日が7に終わる）
        Returns:
            Int: 1-7
        """
        return d.isoweekday()

    def date(self, d):
        """ @method
        日付を返す。
        Returns:
            Date:
        """
        return d.date()
        
    def time(self, d):
        """ @method
        時刻を返す。
        Returns:
            Time:
        """
        return d.time()

    def timetz(self, d):
        """ @method
        時刻を返す。
        Returns:
            Time:
        """
        return d.timetz()

    #
    # timezone
    #
    def timezone(self, d):
        """ @method
        タイムゾーンがあれば名前を返す。
        Returns:
            Str:
        """
        return d.tzname()
        
    def utcoffset(self, d):
        """ @method
        タイムゾーンがあればUTC時刻からの差分を返す。
        Returns:
            Any:
        """
        return d.utcoffset()
        
    def dst(self, d):
        """ @method
        タイムゾーンがあればそのサマータイム情報を返す。
        Returns:
            Any:
        """
        return d.dst()

    def with_timezone(self, d, tz=None):
        """ @method
        タイムゾーンを適用する。
        Returns:
            Datetime:
        """
        return d.astimezone(tz)

    #
    # さまざまな様式での日付時刻表現
    #
    def timetuple(self, d):
        """ @method
        time.struct_timeを返す。
        Returns:
            Any:
        """
        return d.timetuple()

    def utctimetuple(self, d):
        """ @method
        utc標準に変換して、time.struct_timeを返す。
        Returns:
            Any:
        """
        return d.utctimetuple()

    def ordinal(self, d):
        """ @method
        グレゴリオ歴上の日の序数を返す。
        Returns:
            Int:
        """
        return d.toordinal()
    
    def timestamp(self, d):
        """ @method
        POSIXのタイムスタンプを返す。
        Returns:
            Float:
        """
        return d.timestamp()
        
    def isocalendar(self, d):
        """ @method
        ISO year, ISO week number, ISO weekday の3つ組を返す。
        Returns:
            Any:
        """
        return d.isocalendar()

    def isoformat(self, d, sep=None, timespec=None):
        """ @method
        ISO 8601 で定められた様式で表現する。
        Params:
            sep?(Str):
            timespec?(Str):
        Returns:
            Str:
        """
        args = []
        if sep: args.append(sep)
        if timespec: args.append(timespec)
        return d.isoformat(*args)

    def ctime(self, d):
        """ @method
        Cのctime()の様式で表現する。
        Returns:
            Str:
        """
        return d.ctime()
    
    def format(self, d, format):
        """ @method
        指定の様式で表現する。
        Params:
            format(str):
        Returns:
            Str:
        """
        return d.strftime(format)

    
class DateType:
    """ @type trait [Date]
    日付型
    ValueType:
        datetime.date
    """
    def constructor(self, year=None, month=None, day=None):
        """ @meta 
        Params:
            year(Int):
            month(Int):
            day(Int):
        """
        if isinstance(year, int):
            return datetime.date(year, month, day)
        
        # 2009/12/01
        if isinstance(year, str):
            parts = year.split("/")
            if len(parts) >= 3:
                y, m, d = parse_date(year)
                return datetime.date(y, m, d)

        raise ValueError("不正な日付の形式です: " + year)

    def stringify(self, date):
        """ @meta """
        return date.strftime("%Y/%m/%d (%a) ")
    
    #
    #
    #
    def from_timestamp(self, s):
        """ @method external
        Params:
            s(Float):
        """
        return datetime.date.fromtimestamp(s)
    
    def from_iso(self, s):
        """ @method external
        Params:
            s(Str):
        """
        return datetime.date.fromisoformat(s)
    
    def from_ordinal(self, o):
        """ @method external
        Params:
            o(Int):
        """
        return datetime.date.fromordinal(o)
    
    def today(self):
        """ @method external
        今日の日付を表す。
        """
        return datetime.date.today()

    #
    # 取得
    #
    def year(self, d):
        """ @method
        年
        Returns:
            Int:
        """
        return d.year

    def month(self, d):
        """ @method
        月
        Returns:
            Int:
        """
        return d.month

    def day(self, d):
        """ @method
        日
        Returns:
            Int:
        """
        return d.day

    def weekday(self, d):
        """ @method
        曜日。（月が0にはじまり、日が6に終わる）
        Returns:
            Int: 0-6
        """
        return d.weekday()
        
    def isoweekday(self, d):
        """ @method
        曜日。（月が1にはじまり、日が7に終わる）
        Returns:
            Int: 1-7
        """
        return d.isoweekday()
    
    #
    # さまざまな様式での日付時刻表現
    #
    def timetuple(self, d):
        """ @method
        time.struct_timeを返す。
        Returns:
            Any:
        """
        return d.timetuple()

    def ordinal(self, d):
        """ @method
        グレゴリオ歴上の日の序数を返す。
        Returns:
            Int:
        """
        return d.toordinal()
    
    def isocalendar(self, d):
        """ @method
        ISO year, ISO week number, ISO weekday の3つ組を返す。
        Returns:
            Any:
        """
        return d.isocalendar()

    def isoformat(self, d):
        """ @method
        ISO 8601 で定められた様式で表現する。
        Returns:
            Str:
        """
        return d.isoformat()

    def ctime(self, d):
        """ @method
        Cのctime()の様式で表現する。
        Returns:
            Str:
        """
        return d.ctime()
    
    def format(self, d, format):
        """ @method
        指定の様式で表現する。
        Params:
            format(str):
        Returns:
            Str:
        """
        return d.strftime(format)

    def joined(self, d, sep=None):
        """ @method
        年、月、日を区切る。
        Params:
            sep?(str): 区切り文字
        Returns:
            Str:
        """
        sep = sep or ""
        return d.strftime(sep.join(("%Y","%m","%d")))

    
class TimeType:
    """ @type trait [Time]
    時刻
    ValueType:
        datetime.time
    """
    def constructor(self, s):
        """ @meta 
        Params:
            Str|Int:
        """
        if isinstance(s, int):
            if s > 86400:
                raise ValueError("秒数が一日を超えます")
            t = time.gmtime(s)
            h, m, c = t[3], t[4], t[5]
            return datetime.time(h, m, c)
        elif isinstance(s, (list, tuple)):
            if len(s) < 3:
                raise ValueError("{}: 要素の数が足りません".format(s))
            return datetime.time(s[0], s[1], s[2])

        klass, sep, tail = s.partition("/")
        klass = klass.lower()
        if sep:
            if klass == "iso":
                return datetime.time.fromisoformat(tail)
        
        # 12:50.01
        h, m, c = parse_time(s)
        return datetime.time(h, m, c)

    def stringify(self, t):
        """ @meta """
        return t.strftime("%H:%M.%S")

    #
    # 取得
    #
    def hour(self, d):
        """ @method
        時間（24）
        Returns:
            Int:
        """
        return d.hour

    def minute(self, d):
        """ @method
        分
        Returns:
            Int:
        """
        return d.minute

    def second(self, d):
        """ @method
        秒
        Returns:
            Int:
        """
        return d.second
        
    def microsecond(self, d):
        """ @method
        マイクロ秒
        Returns:
            Int:
        """
        return d.microsecond

    #
    #
    #
    def timezone(self, d):
        """ @method
        タイムゾーンがあれば名前を返す。
        Returns:
            Str:
        """
        return d.tzname()
        
    def utcoffset(self, d):
        """ @method
        タイムゾーンがあればUTC時刻からの差分を返す。
        Returns:
            Any:
        """
        return d.utcoffset()
        
    def dst(self, d):
        """ @method
        タイムゾーンがあればそのサマータイム情報を返す。
        Returns:
            Any:
        """
        return d.dst()

    #
    # さまざまな様式での日付時刻表現
    #
    def isoformat(self, d, timespec=None):
        """ @method
        ISO 8601 で定められた様式で表現する。
        Params:
            timespec?(str): 
        Returns:
            Str:
        """
        if timespec:
            return d.isoformat(timespec)
        else:
            return d.isoformat()

    def format(self, d, format):
        """ @method
        指定の様式で表現する。
        Params:
            format(str):
        Returns:
            Str:
        """
        return d.strftime(format)


def digits_split_by_nondigit(s, required=None):
    parts = [""]
    for ch in s:
        if ch.isdigit():
            parts[-1] += ch
        else:
            parts.append("")
    try:
        digits = [int(x) for x in parts if len(x)>0]
    except Exception as e:
        raise ValueError("日付の要素の数値への変換に失敗: {}".format(s)) from e
    if required is not None:
        if len(digits) < required:
            raise ValueError("日付の要素の数が足りません({}個必要): {}".format(required, s))
        digits = digits[0:required]
    return digits



class DateRepresent:
    """ @mixin
    MixinType:
        Date:machaon.types.dateandtime:
    """
    def from_joined(self, s):
        """ @method external
        数字以外の任意の文字で区切られた日付表現。
        Params:
            s(Str):
        """
        y, m, d = digits_split_by_nondigit(s, 3)
        return datetime.date(y, m, d)
    
    def from_joined_month(self, s, day=None):
        """ @method external
        年と月の区切られた組み合わせ。
        Params:
            s(Str):
            day?(Int):
        """
        y, m = digits_split_by_nondigit(s, 2)
        d = day if day is not None else 1
        return datetime.date(y, m, d)
    
    #
    #
    #
    def yyyymmdd(self, d):
        """ @method [date8]
        Returns:
            Str:
        """
        return d.strftime("%Y%m%d")
    
    def from_yyyymmdd(self, s):
        """ @method external [from_date8]
        YYYYMMDDな日付表現。
        Params:
            s(Str):
        """
        if len(s) != 8:
            raise ValueError(s)
        y = s[0:4]
        m = s[4:6]
        d = s[6:]
        return datetime.date(int(y), int(m), int(d))

    def mmdd(self, d):
        """ @method [date4]
        Returns:
            Str:
        """
        return d.strftime("%m%d")
    
    def from_mmdd(self, s, year=None):
        """ @method external [from_date4]
        MMDDな日付表現。
        Params:
            s(Str):
            year?(int):
        """
        if len(s) != 4:
            raise ValueError(s)
        if year is None:
            y = datetime.datetime.today().year
        else:
            y = year
        m = int(s[0:2])
        d = int(s[2:])
        return datetime.date(y, m, d)

    #
    # 
    #
    def from_this_year_month(self, v, day=None):
        """ @method external
        今年のある月の1日。
        Params:
            v(int):
            day?(int):
        """
        y = datetime.datetime.today().year
        if day is None:
            d = 1
        else:
            d = day
        return datetime.date(y, v, d)
    
    def from_this_month_day(self, v):
        """ @method external
        今月のある日。
        Params:
            v(int):
        """
        y = datetime.datetime.today().year
        m = datetime.datetime.today().month
        return datetime.date(y, m, v)

    #
    # 西暦の下二桁
    #
    def from_yearlow_month(self, s, day=None):
        """ @method external
        西暦の下二桁と月の区切られた組み合わせ。
        Params:
            s(str):
            day?(int):
        """
        yv, m = digits_split_by_nondigit(s, 2)        
        y = DateRepresent.complete_yearlow(yv)
        d = day if day is not None else 1
        return datetime.date(y, m, d)

    def from_yearlow_date(self, s):
        """ @method external
        西暦の下二桁と月日の区切られた組み合わせ。
        Params:
            s(str):
        """
        yv, m, d = digits_split_by_nondigit(s, 3) 
        y = DateRepresent.complete_yearlow(yv)
        return datetime.date(y, m, d)

    @staticmethod
    def complete_yearlow(y):
        if 0 <= y and y < 70: # 2000 ~ 2069
            y = 2000 + y
        elif 70 <= y and y < 100: # 1970 ~ 1999
            y = 1900 + y
        return y



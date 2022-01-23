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

# 
#
#
class DatetimeType():
    """ 日付と時刻 
    datetime.datetime
    """
    def constructor(self, _context, s=None):
        """ @meta 
        Params:
            None|Str|Int:
        """
        if s is None:
            return datetime.datetime.now()

        if isinstance(s, int):
            return datetime.datetime.fromordinal(s)

        klass, sep, tail = s.partition("/")
        klass = klass.lower()
        if sep:
            if klass == "posix":
                return datetime.datetime.fromtimestamp(float(tail))
            elif klass == "posix-utc":
                return datetime.datetime.utcfromtimestamp(float(tail))
            elif klass == "iso":
                return datetime.datetime.fromisoformat(s)
        
        # 2009/12/01/12:50.49
        parts = s.split("/")
        if len(parts) >= 3:
            y, m, d = parse_date(s)
            if len(parts) == 4:
                h, n, c = parse_time(parts[3])
                return datetime.datetime(y, m, d, h, n, c)
            else:
                return datetime.datetime(y, m, d)

        raise ValueError("不正な日付の形式です: " + s)

    def stringify(self, date):
        """ @meta """
        return date.strftime("%Y/%m/%d (%a) %H:%M.%S")

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

    def now(self, _d, tz=None):
        """ @method
        現在の時刻を返す。
        Params:
            tz(Timezone): 
        """ 
        return datetime.datetime.now(tz)
        
    def utcnow(self, _d):
        """ @method
        現在の時刻を返す。
        """ 
        return datetime.datetime.utcnow()
        
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
    """ 日付型
    datetime.date
    """
    def constructor(self, _context, s):
        """ @meta """
        if s is None:
            return datetime.datetime.now()

        if isinstance(s, int):
            return datetime.date.fromordinal(s)

        klass, sep, tail = s.partition("/")
        klass = klass.lower()
        if sep:
            if klass == "posix":
                return datetime.date.fromtimestamp(float(tail))
            elif klass == "iso":
                return datetime.date.fromisoformat(s)
        
        # 2009/12/01
        parts = s.split("/")
        if len(parts) >= 3:
            y, m, d = parse_date(s)
            return datetime.date(y, m, d)

        raise ValueError("不正な日付の形式です: " + s)

    def stringify(self, date):
        """ @meta """
        return date.strftime("%Y/%m/%d (%a) ")

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

    
class TimeType:
    """ 日付型
    datetime.date
    """
    def constructor(self, _context, s):
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

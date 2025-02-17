
from http import HTTPStatus
import json
import urllib.parse
import datetime

from machaon.core.symbol import full_qualified_name
from machaon.ui.server.wsgi import WSGIRequest
from machaon.types.meta import meta

def split_url_path(url):
    """ 前後の空の要素を取り除く """
    return [x for x in url.split("/") if x]


#
#
# APIサーバーの実装
#
#
class ApiSlot:
    """ Apiの定義 """
    def __init__(self, method, parts, fn, paramsig=None, blob=False):
        self.method = method
        self.parts = parts
        self.fn = fn
        self.paramsigs = {}
        self.isblob = blob

        for k, v in urllib.parse.parse_qsl(paramsig):
            p = ApiParam.parse(k, v)
            self.paramsigs[p.name] = p

    def cast(self, method, pathparts):
        """ マッチする場合、呼び出しオブジェクトを構築する """
        if self.method != method:
            return None
        
        if len(self.parts) != len(pathparts):
            return None
        
        params = []
        for l, r in zip(self.parts, pathparts):
            if l == "?":
                params.append(urllib.parse.unquote(r))
            elif l == "??":
                params.append(urllib.parse.unquote(urllib.parse.unquote(r)))
            elif l != r:
                return None
        
        return ApiCast(params)

    def build_args(self, request, cast):
        # クエリパラメータを構築する
        kwargs = {}
        for k, v in request.parse_query():
            sig = self.paramsigs.get(k)
            if sig:
                sig.store(kwargs, v)
            else:
                kwargs[k] = v

        return cast.params, kwargs

    def invoke(self, server, request, cast):
        """ APIを呼び出す """
        args, kwargs = self.build_args(request, cast)
        return self.fn(server, *args, **kwargs)

    def call(self, server, *args, **kwargs):
        """ ほかのAPIの中から呼び出す """
        return self.fn(server, *args, **kwargs)

    def is_blob_result(self):
        return self.isblob

    def get_entrypoint(self):
        return "/".join(self.parts)


class ApiOptionsSlot:
    def __init__(self, fn):
        self.fn = fn

    def cast(self, method, pathparts):
        if method == "OPTIONS":
            return ApiCast([])
        return None

    def invoke(self, server, request, cast):
        """ APIを呼び出す """
        return self.fn(server)



class ApiParam:
    """ apiのパラメータ型 """
    def __init__(self, name, valtype, isvariable=False, isdict=False):
        self.name = name
        self.valtype = valtype
        self.isvariable = isvariable
        self.isdict = isdict
    
    @classmethod
    def parse(cls, nameexpr, valexpr):
        isvariable = False
        isdict = False
        if valexpr:
            valtype = {"str":str, "int":int, "float":float, "bool":boolarg, "date":datearg}.get(valexpr)
            if valtype is None:
                raise ValueError(valexpr + 'は不明なビルトイン型です')
        else:
            valtype = str
        
        if nameexpr.startswith("*"):
            nameexpr = nameexpr[1:]
            isvariable = True
        
        return ApiParam(nameexpr, valtype, isvariable, isdict)    

    def store(self, kwargs, value):
        k = self.name
        v = self.valtype(value)
        if self.isvariable:
            if k not in kwargs:
                kwargs[k] = []
            kwargs[k].append(v)
        else:
            kwargs[k] = v

def boolarg(v):
    if v=="true" or v=="1":
        return True
    elif v=="false" or v=="0":
        return False
    else:
        raise ValueError(v)
    
def datearg(v):
    return meta.Date.from_joined(v)


class ApiCast:
    """ apiのエントリポイント """
    def __init__(self, params):
        self.params = params


class ApiResult:
    def __init__(self, bits, *headers):
        self.bits = bits or bytes()
        self.headers = []
        for ent in headers:
            if ent[1] is None:
                continue
            self.headers.append(ent)

    def get_header(self):
        return self.headers

    def create_result_header(self):    
        content_length = len(self.bits)
        header = [
            *self.headers,
            ('Content-Length', str(content_length)) # Content-Lengthが合っていないとブラウザでエラー
        ]
        return header


class ApiSlotRegister:
    def __init__(self):
        self.slots = []
        self._method = None
        self._common_paramsig = None

    def match_slot(self, method, paths):
        """ 
        適合するスロットを返す 
        先頭のもののみ
        """
        for slot in self.slots:
            cast = slot.cast(method, paths)
            if cast is not None:
                return slot, cast
        return None, None
             
    def __call__(self, route=None, paramsig=None, *, method=None, blob=False):
        """ 
        スロットを登録する 
        """
        method = self._method or "GET"
        self._method = None
        if self._common_paramsig:
            if paramsig:
                paramsig = paramsig + "&" + self._common_paramsig
            else:
                paramsig = self._common_paramsig
         
        def _deco(fn):
            if method == "OPTIONS":
                slot = ApiOptionsSlot(fn)
            elif route:
                parts = split_url_path(route)
                slot = ApiSlot(method, parts, fn, paramsig, blob=blob)
            else:
                raise ValueError("")
            self.slots.append(slot)
            return slot
        return _deco

    @property
    def get(self):
        self._method = "GET"
        return self
        
    @property
    def post(self):
        self._method = "POST"
        return self

    @property
    def put(self):
        self._method = "PUT"
        return self

    @property
    def delete(self):
        self._method = "DELETE"
        return self
    
    @property
    def options(self):
        self._method = "OPTIONS"
        return self

    def set_common_params(self, paramsig):
        self._common_paramsig = paramsig


class ApiServerApp:
    """ apiを実装する """
    errortrace = False

    def __init__(self):
        super().__init__()
        self.request: WSGIRequest = None

    """ スロット定義オブジェクト
    Params:
        route(str): apiのエントリポイント
        paramsig(str): クエリパラメータのシグニチャをクエリパラメータの形式で記述する
        content_type(str): ブロブを返す場合に指定する。
    """
    slot = ApiSlotRegister()

    def get_slots(self):
        return type(self).slot.slots
    
    def get_cors_header(self):
        return [
            ('Access-Control-Allow-Origin', '*'),  # 許可するアクセス
            ('Access-Control-Allow-Methods', '*'), # 許可するメソッド
            ('Access-Control-Allow-Headers', "X-Requested-With, Origin, X-Csrftoken, Content-Type, Accept"), # 許可するヘッダー
        ]

    def run(self, req):
        """ リクエストを処理する """
        self.request = req
        method = req.method
        paths = split_url_path(req.path) # 前後の空の要素を取り除く

        status = HTTPStatus.NOT_FOUND
        retval = None

        # apiを探して実行する
        slot, slotcast = self.slot.match_slot(method, paths)
        if slot is not None:
            if self.errortrace:
                try:
                    retval = slot.invoke(self, req, slotcast)   
                    status = HTTPStatus.OK
                except Exception as e:
                    from machaon.types.stacktrace import verbose_display_traceback
                    retval = {
                        "error": [full_qualified_name(type(e),True)] + [str(x) for x in e.args],
                        "stacktrace": verbose_display_traceback(e).splitlines()
                    }
                    status = HTTPStatus.INTERNAL_SERVER_ERROR     
            else:
                retval = slot.invoke(self, req, slotcast)   
                status = HTTPStatus.OK

        if retval is None:
            # OK
            req.response(status, self.get_cors_header())
            return 
        elif isinstance(retval, HTTPStatus):
            # HTTPStatus
            status = retval
            req.response(status, self.get_cors_header())
            return
        else:
            # データを返す
            if isinstance(retval, ApiResult):
                # ApiResult
                result = retval
            elif isinstance(retval, dict):
                # json
                bits = json.dumps(retval).encode("utf-8")
                result = ApiResult(bits, ('Content-type', 'application/json; charset=utf-8')) # utf-8のjson形式
            else:
                raise TypeError("[{}] Invalid api return value type: {}({}). Return type must be one of [ApiResult | HTTPStatus | dict].".format(slot, retval, type(retval).__name__))
            
            header = self.get_cors_header() + result.create_result_header()
            req.response(status, header)
            yield result.bits

    @classmethod
    def blob(cls, bits, *headers):
        """ APIの返り値で、バイト列を直接記述する """
        return ApiResult(bits, *headers)

    @property
    def app(self):
        return self.request.app if self.request else None
    
    def result(self, bits=None):
        return ApiResult(bits)

    #
    # 派生クラスで、ApiSlot.defineをメソッド定義に用いてスロットを定義する
    #



#
#
#
def serialize_json(x):
    if x is None or isinstance(x, (int, str, float, bool)):
        return x
    elif isinstance(x, datetime.datetime):
        return x.strftime("%Y/%m/%d %H:%M:%S")
    elif isinstance(x, datetime.date):
        return x.strftime("%Y/%m/%d")
    elif isinstance(x, (list, tuple)):
        return type(x)(serialize_json(v) for v in x)
    elif isinstance(x, dict):
        return {serialize_json(k):serialize_json(v) for k,v in x.items()}
    elif hasattr(x, "serialize"):
        return x.serialize()
    elif hasattr(x, "stringify"):
        return x.stringify()
    else:
        return repr(x)
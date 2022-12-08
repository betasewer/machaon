
from http import HTTPStatus
import json
import urllib.parse

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


class ApiParam:
    """ apiのパラメータ型 """
    def __init__(self, name, valtype, ismulti):
        self.name = name
        self.valtype = valtype
        self.ismulti = ismulti
    
    @classmethod
    def parse(cls, nameexpr, valexpr):
        if valexpr:
            valtype = {"str":str, "int":int, "float":float, "bool":boolarg}.get(valexpr)
            if valtype is None:
                raise ValueError(valexpr + 'は不明なビルトイン型です')
        else:
            valtype = str
        ismulti = False
        if nameexpr.startswith("*"):
            nameexpr = nameexpr[1:]
            ismulti = True
        return ApiParam(nameexpr, valtype, ismulti)    

    def store(self, kwargs, value):
        k = self.name
        v = self.valtype(value)
        if self.ismulti:
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

class ApiCast:
    """ apiのエントリポイント """
    def __init__(self, params):
        self.params = params


class ApiResult:
    def __init__(self, bits, *headers):
        self.bits = bits
        self.headers = []
        for ent in headers:
            if ent[1] is None:
                continue
            self.headers.append(ent)

    def create_header(self):    
        content_length = len(self.bits)
        header = [
            ('Access-Control-Allow-Origin', '*'),  # 許可するアクセス
            ('Access-Control-Allow-Methods', '*'), # 許可するメソッド
            ('Access-Control-Allow-Headers', "X-Requested-With, Origin, X-Csrftoken, Content-Type, Accept"), # 許可するヘッダー
            *self.headers,
            ('Content-Length', str(content_length)) # Content-Lengthが合っていないとブラウザでエラー
        ]
        return header



class ApiServerApp:
    """ apiを実装する """
    def __init__(self):
        super().__init__()
        self.request = None

    _slots = []

    @classmethod
    def slot(cls, route, paramsig=None, *, method=None, blob=False):
        """ スロット定義デコレータ 
        Params:
            route(str): apiのエントリポイント
            paramsig(str): クエリパラメータのシグニチャをクエリパラメータの形式で記述する
            content_type(str): ブロブを返す場合に指定する。
        """
        parts = split_url_path(route)
        method = method or "GET"
        def _deco(fn):
            slot = ApiSlot(method, parts, fn, paramsig, blob=blob)
            cls._slots.append(slot)
            return slot

        _deco.get = cls.get_slot
        _deco.post = cls.post_slot
        _deco.put = cls.put_slot
        _deco.delete = cls.delete_slot
        return _deco
    
    @classmethod
    def get_slot(cls, *args, **kwargs):
        return cls.slot(*args, method="GET", **kwargs)
    
    @classmethod
    def post_slot(cls, *args, **kwargs):
        return cls.slot(*args, method="POST", **kwargs)
        
    @classmethod
    def put_slot(cls, *args, **kwargs):
        return cls.slot(*args, method="PUT", **kwargs)
        
    @classmethod
    def delete_slot(cls, *args, **kwargs):
        return cls.slot(*args, method="DELETE", **kwargs)

    def get_slots(self):
        return type(self)._slots

    def run(self, req):
        """ リクエストを処理する """
        self.request = req
        method = req.method
        paths = split_url_path(req.path) # 前後の空の要素を取り除く

        # apiを探して実行する
        slot = None
        for slot in self.get_slots():
            cast = slot.cast(method, paths)
            if cast is not None:
                retval = slot.invoke(self, req, cast)
                break
        else:
            retval = HTTPStatus.NOT_FOUND

        # データを返す
        if isinstance(retval, HTTPStatus):
            # ステータスコード
            status = retval
            bits = req.status_message_html(retval).encode("utf-8")
            result = ApiResult(bits, ('Content-type', 'text/html; charset=utf-8')) # html
        elif isinstance(retval, ApiResult):
            # ApiResult
            status = HTTPStatus.OK
            result = retval
        else:
            # json
            status = HTTPStatus.OK
            bits = json.dumps(retval).encode("utf-8")
            result = ApiResult(bits, ('Content-type', 'application/json; charset=utf-8')) # utf-8のjson形式
        
        # ヘッダ
        header = result.create_header()
        req.response(status, header)
        yield result.bits

    @classmethod
    def blob(cls, bits, *headers):
        """ APIの返り値で、バイト列を直接記述する """
        return ApiResult(bits, *headers)

    #
    # 派生クラスで、ApiSlot.defineをメソッド定義に用いてスロットを定義する
    #




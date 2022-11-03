
from http import HTTPStatus
import json
import urllib.parse

from machaon.ui.webserver.wsgi import WSGIApp 

#
#
# APIサーバーの実装
#
#
class ApiSlot:
    """ Apiの定義 """
    def __init__(self, parts, fn, paramsig=None, blob=False):
        self.parts = parts
        self.fn = fn
        self.paramsigs = {}
        self.isblob = blob

        for k, v in urllib.parse.parse_qsl(paramsig):
            p = ApiParam.parse(k, v)
            self.paramsigs[p.name] = p

    def cast(self, pathparts):
        """ マッチする場合、呼び出しオブジェクトを構築する """
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


class ApiServerApp(WSGIApp):
    """ apiを実装する """
    def __init__(self):
        super().__init__()
        self._slots = []
        self._load_slots()
        self.request = None

    @classmethod
    def slot(cls, route, paramsig=None, *, blob=False):
        """ スロット定義デコレータ 
        Params:
            route(str): apiのエントリポイント
            paramsig(str): クエリパラメータのシグニチャをクエリパラメータの形式で記述する
            content_type(str): ブロブを返す場合に指定する。
        """
        parts = route.split("/")
        def _deco(fn):
            return ApiSlot(parts, fn, paramsig, blob=blob)
        return _deco

    @classmethod
    def blob(cls, bits, *headers):
        """ バイト列を記述して返す """
        return ApiResult(bits, *headers)

    def _load_slots(self):
        """ スロット定義を取り出す """
        for v in vars(type(self)).values():
            if isinstance(v, ApiSlot):
                self._slots.append(v)

    def run(self, req):
        """ リクエストを処理する """
        self.request = req
        paths = [x for x in req.path.split("/") if x] # 前後の空の要素を取り除く

        # apiを探して実行する
        slot = None
        for slot in self._slots:
            cast = slot.cast(paths)
            if cast is not None:
                result = slot.invoke(self, req, cast)
                break
        else:
            yield req.response_and_status_message("NOT_FOUND")
            return 

        # データを返す
        if isinstance(result, HTTPStatus):
            # ステータスコード
            yield req.response_and_status_message(result)
            return
        elif not isinstance(result, ApiResult):
            # json
            bits = json.dumps(result).encode("utf-8")
            result = ApiResult(bits, ('Content-type', 'application/json; charset=utf-8')) # utf-8のjson形式
        
        # ヘッダ
        header = result.create_header()
        req.response("OK", header)
        yield result.bits

    #
    # 派生クラスで、ApiSlot.defineをメソッド定義に用いてスロットを定義する
    #




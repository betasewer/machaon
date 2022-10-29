
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
    def __init__(self, parts, fn, paramsig=None):
        self.parts = parts
        self.fn = fn
        self.paramsigs = {}
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


class ApiParam:
    """ apiのパラメータ型 """
    def __init__(self, name, valtype, ismulti):
        self.name = name
        self.valtype = valtype
        self.ismulti = ismulti
    
    @classmethod
    def parse(cls, nameexpr, valexpr):
        if valexpr:
            valtype = {"int":int, "float":float}.get(valexpr)
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
        if k in kwargs and self.ismulti:
            if not isinstance(kwargs[k], list):
                kwargs[k] = [kwargs[k]]
            kwargs[k].append(v)
        else:
            kwargs[k] = v


class ApiCast:
    """ apiのエントリポイント """
    def __init__(self, params):
        self.params = params


class ApiServerApp(WSGIApp):
    """ apiを実装する """
    def __init__(self):
        super().__init__()
        self._slots = []
        self._load_slots()
        self.request = None

    @classmethod
    def slot(cls, route, paramsig=None):
        """ スロット定義デコレータ 
        Params:
            route(str): apiのエントリポイント
            paramsig(str): クエリパラメータのシグニチャをクエリパラメータの形式で記述する
        """
        parts = route.split("/")
        def _deco(fn):
            return ApiSlot(parts, fn, paramsig)
        return _deco

    def _load_slots(self):
        """ スロット定義を取り出す """
        for v in vars(type(self)).values():
            if isinstance(v, ApiSlot):
                self._slots.append(v)

    def invoke_slot(self, paths, req):
        # apiを探して実行する
        for slot in self._slots:
            cast = slot.cast(paths)
            if cast is not None:
                return slot.invoke(self, req, cast)
        return None

    def response_json(self, req, result):
        # jsonを返す
        jsonbits = json.dumps(result).encode("utf-8")
        content_length = len(jsonbits) # Content-Lengthを計算

        header = [
            ('Access-Control-Allow-Origin', '*'),   # 許可するアクセス
            ('Access-Control-Allow-Methods', '*'),  # 許可するメソッド
            ('Access-Control-Allow-Headers', "X-Requested-With, Origin, X-Csrftoken, Content-Type, Accept"), # 許可するヘッダー
            ('Content-type', 'application/json; charset=utf-8'), # utf-8のjson形式
            ('Content-Length', str(content_length)) # Content-Lengthが合っていないとブラウザでエラー
        ]
        req.response("OK", header)
        return jsonbits

    def run(self, req):
        self.request = req
        paths = [x for x in req.path.split("/") if x] # 前後の空の要素を取り除く

        # apiを探して実行する
        result = self.invoke_slot(paths, req)
        if result is None:
            yield req.response_and_status_message("NOT_FOUND")
            return 

        # jsonを返す
        yield self.response_json(req, result)

    #
    # 派生クラスで、ApiSlot.defineをメソッド定義に用いてスロットを定義する
    #




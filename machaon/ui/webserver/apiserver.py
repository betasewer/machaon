
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
    def __init__(self, parts, fn):
        self.parts = parts
        self.fn = fn

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

    def invoke(self, server, request, cast):
        """ APIを呼び出す """
        return self.fn(server, *cast.params, **request.query_dict())


class ApiCast:
    """ apiの呼び出しパラメータ """
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
    def slot(cls, route):
        """ スロット定義デコレータ """
        parts = route.split("/")
        def _deco(fn):
            return ApiSlot(parts, fn)
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




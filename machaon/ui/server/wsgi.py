


import urllib.parse
import wsgiref.util as wsgiutil
from http import HTTPStatus

#
#
# WSGIアプリケーション
#
#
class WSGIRequest:
    def __init__(self, app, env, start_response):
        self._env = env
        self._start_response = start_response
        self._app = app
        self._uri = wsgiutil.request_uri(self._env)
        self._uriparts = urllib.parse.urlsplit(self._uri, allow_fragments=False)

    def response(self, status_code_or_name, header):
        """ レスポンスを返す """
        if isinstance(status_code_or_name, str):
            status = getattr(HTTPStatus, status_code_or_name)
        elif isinstance(status_code_or_name, HTTPStatus):
            status = status_code_or_name
        else:
            raise TypeError(status_code_or_name)
        code = "{} {}".format(status.value, status.phrase)
        self._start_response(code, header)

    def status_message_html(self, status: HTTPStatus):
        return "<html><body><h2>{} {}</h2><p>{}.</p></body>".format(status.value, status.phrase, status.description)

    @property
    def app(self):
        return self._app

    #
    # envからの取得
    #
    @property
    def method(self):
        return self._env["REQUEST_METHOD"]

    @property
    def uri(self):
        return self._uri

    @property
    def scheme(self):
        return self._uriparts.scheme

    @property
    def netloc(self):
        return self._uriparts.netloc
    
    @property
    def path(self):
        return self._uriparts.path
    
    @property
    def query(self):
        return self._uriparts.query

    def parse_query(self):
        return urllib.parse.parse_qsl(self.query)

    @property
    def content_type(self):
        return self._env["CONTENT_TYPE"]

    @property
    def content_length(self):
        return self._env["CONTENT_LENGTH"]

    @property
    def input(self):
        return self._env["wsgi.input"]

    def read_input(self, *, urlencoding=None):
        clen = int(self.content_length)
        bits = self.input.read(clen)
        if urlencoding:
            return urllib.parse.unquote_plus(bits.decode("ascii"), encoding=urlencoding)
        return bits
    
    def read_urlencoded_values(self, *, encoding=None):
        bits = self.read_input()
        return urllib.parse.parse_qsl(bits.decode("ascii"), encoding=encoding)
    
    def read_json(self, *, encoding=None):
        bits = self.read_input()
        text = bits.decode(encoding or "utf-8")
        import json
        return json.loads(text)


    #
    # envの更新
    #
    def shift_path_info(self):
        wsgiutil.shift_path_info(self._env)

    def write_urlencoded_values(self, values):
        """ テスト用 キーと値のペアをURLエンコードしてリクエストに書き込む """
        from io import BytesIO
        q = urllib.parse.urlencode(values)
        bits = q.encode("ascii")
        self._env["wsgi.input"] = BytesIO(bits)
        self._env["CONTENT_LENGTH"] = len(bits)
    
    def write_json(self, di: dict):
        """ テスト用 辞書をリクエストに書き込む """
        from io import BytesIO
        import json
        t = json.dumps(di)
        bits = t.encode("utf-8")
        self._env["wsgi.input"] = BytesIO(bits)
        self._env["CONTENT_LENGTH"] = len(bits)


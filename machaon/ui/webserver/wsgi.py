


from datetime import datetime
import urllib.parse
import wsgiref.util as wsgiutil
import wsgiref.simple_server
from http import HTTPStatus
import threading

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

    def response(self, status_name, header):
        """ レスポンスを返す """
        status = getattr(HTTPStatus, status_name)
        code = "{} {}".format(status.value, status.phrase)
        self._start_response(code, header)

    def response_and_status_message(self, status_name):
        """ レスポンスを返し表示用メッセージを作成する簡易ヘルパー """
        self.response(status_name, [('Content-type', 'text/html; charset=utf-8')])
        status = getattr(HTTPStatus, status_name)
        message = "<html><body><h2>{} {}</h2><p>{}.</p></body>".format(status.value, status.phrase, status.description)
        return message.encode("utf-8")

    @property
    def app(self):
        return self._app

    #
    # envからの取得
    #
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

    def query_dict(self):
        return urllib.parse.parse_qs(self.query)
    
    #
    # envの更新
    #
    def shift_path_info(self):
        wsgiutil.shift_path_info(self._env)



class WSGIApp:
    """ アプリの基底クラス """
    def __init__(self):
        self.root = None
        self.spirit = None
        self.run_entry = None
        self.logger = None

    def run(self, request: WSGIRequest):
        raise NotImplementedError()

    #
    #
    #
    def _app(self, env, start_response):
        """ """
        request = WSGIRequest(self.spirit, env, start_response)
        results = list(self.run(request))
        return results

    def _logged_app(self, env, start_response):
        """ """
        request = WSGIRequest(self.spirit, env, start_response)
        results = self.logger.log(self.run(request), self.root.ui)
        return results
    
    def __call__(self, env, start_response):
        return self.run_entry(env, start_response)

    #
    #
    #
    def setup(self, **uiargs):
        """ ログを取得しない設定 """
        # machaonの初期化
        from machaon.app import AppRoot
        self.root = AppRoot()
        self.root.initialize(ui="batch", **uiargs)
        self.spirit = self.root.temp_spirit()
        # エントリ関数を設定
        self.run_entry = self._app

    def logging_setup(self, **uiargs):
        """ ログを取得する設定 """
        self.setup(**uiargs)
        # 言語とUIの初期化
        self.root.boot_core()
        self.root.boot_ui()
        # ロガー生成
        self.logger = WSGIAppLogger(self.root)
        self.spirit = self.logger.spirit()
        # エントリ関数を設定
        self.run_entry = self._logged_app

    def intrasetup(self, spirit):
        """ 実行中のmachaonを引き継ぐ """
        self.spirit = spirit
        self.root = spirit.root
        # エントリ関数を設定
        self.run_entry = self._app
        

class WSGIAppLogger:
    """ machaonでログをとる """
    def __init__(self, root):
        # 実行プロセス（ログ生成用）
        self.proc = root.create_process()
        self.context = root.create_root_context(self.proc)

    def spirit(self):
        return self.context.spirit

    def log(self, apprunner, ui):
        """
        アプリケーションを実行する
        一度の呼び出しごとにプロセスを使いまわす
        """
        ui.post_on_exec_process(self.proc, datetime.datetime.now())

        try:
            results = list(apprunner)
            resultobj = self.context.new_object(results)
            ui.post_on_success_process(self.proc, resultobj, self.spirit())
        except Exception as e:
            errorobj = self.context.new_invocation_error_object(e)
            ui.post_on_error_process(self.proc, errorobj)
        
        ui.post_on_end_process(self.proc)

        # メッセージを反映する
        ui.update_chamber_messages(5)
        return results
    


"""
wsgiapp = WSGIApp(appobj, method).setup()
"""

class TestServerThread:
    """ サーバースレッド """
    def __init__(self, port, appmain):
        self.port = port
        self.appmain = appmain
        self._thr = None

    def launch(self):
        self._thr = threading.Thread(target=self.start)
        self._thr.setDaemon(True)
        self._thr.start()

    def start(self):
        """ サーバーアプリケーションを実行する """
        with wsgiref.simple_server.make_server('', self.port, self.appmain) as httpd:
            print("Start API server: http://localhost:{}/ ...".format(self.port))
            httpd.serve_forever()


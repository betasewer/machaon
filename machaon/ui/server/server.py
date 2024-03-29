
from datetime import datetime
import wsgiref.simple_server
import threading

from machaon.ui.server.wsgi import WSGIRequest

#
#
#
class ServerBasic:
    def __init__(self):
        pass

    def run(self, env, start_response):
        raise NotImplementedError()

    def __call__(self, env, start_response):
        return self.run(env, start_response)

    def test_server(self, port):
        return TestServerThread(port, self)




class InternalServer(ServerBasic):
    """ 実行中のmachaonから開始するサーバーアプリ """
    def __init__(self, serverapp, spirit):
        super().__init__()
        self._server = serverapp
        self._spirit = spirit

    def run(self, env, start_response):
        """ """
        request = WSGIRequest(self._spirit, env, start_response)
        results = list(self._server.run(request))
        return results

class SingleServer(ServerBasic):
    """ machaonを介した単体のサーバーアプリ """
    def __init__(self, serverapp, **uiargs):
        super().__init__()
        self._server = serverapp
        # machaonの初期化
        from machaon.app import AppRoot
        self._root = AppRoot()
        self._root.initialize(ui="batch", **uiargs)
        self._spirit = self._root.temp_spirit()
        if hasattr(self._server, "init_app_root"):
            self._server.init_app_root(self._root)

    def use_core(self):
        self._root.boot_core(fundamentals=True)
        self._root.boot_ui()
    
    def run(self, env, start_response):
        """ """
        request = WSGIRequest(self._spirit, env, start_response)
        results = list(self._server.run(request))
        return results


class LoggedSingleServer(SingleServer):
    """ machaonのログを記録する単体のサーバーアプリ """
    def __init__(self, serverapp, **uiargs):
        super().__init__(serverapp, **uiargs)
        # 言語とUIの初期化
        self.use_core()
        # ロガー生成
        self._proc = self._root.create_process() # ログ生成用実行プロセス
        self._context = self._root.create_root_context(self._proc)
        self._spirit = self._context.get_spirit()
    
    def run(self, env, start_response):
        """ 
        ログを取りつつアプリを実行する
        一度の呼び出しごとにプロセスを使いまわす
        """
        request = WSGIRequest(self._spirit, env, start_response)
        
        ui = self._root.ui
        ui.post_on_exec_process(self._proc, datetime.datetime.now())

        try:
            results = list(self._server.run(request))
            resultobj = self._context.new_object(results)
            ui.post_on_success_process(self._proc, resultobj, self.spirit())
        except Exception as e:
            errorobj = self._context.new_invocation_error_object(e)
            ui.post_on_error_process(self._proc, errorobj)
        
        ui.post_on_end_process(self._proc)

        # メッセージを反映する
        ui.update_chamber_messages(5)
        return results


"""
wsgiapp = ServerApp(appobj) # wsgiappがエントリポイントとなる
"""

class TestServerThread:
    """ サーバースレッド """
    def __init__(self, port, appmain):
        self.port = port
        self.appmain = appmain
        self._thr = None

    def start(self):
        """ サーバーアプリケーションを実行する """
        with wsgiref.simple_server.make_server('', self.port, self.appmain) as httpd:
            print("Start server: http://localhost:{}/ ...".format(self.port))
            httpd.serve_forever()

    def startthread(self):
        self._thr = threading.Thread(target=self.start)
        self._thr.setDaemon(True)
        self._thr.start()

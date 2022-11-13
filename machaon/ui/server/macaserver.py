
from http import HTTPStatus
from machaon.process import ProcessSentence
from machaon.ui.server.api import ApiServerApp
from machaon.ui.server.server import InternalServer


slot = ApiServerApp.slot

class MacaServerApp(ApiServerApp):
    """ apiを実装する """
    def __init__(self, root):
        super().__init__()
        self._root = root
        self._ui = self._root.get_ui()

    @slot("/v1/hello")
    def hello(self):
        return HTTPStatus.OK

    @slot("/v1/message", method="POST")
    def eval_message(self):
        """ メッセージを評価する """
        message = self.request.read_input(urlencoding="utf-8")
        
        sentence = ProcessSentence(message)
        self._root.eval_object_message(sentence)

        return
    
    @slot("/v1/chamber")
    def get_message(self):
        chm = self._root.chambers().get_active()
        if chm is None:
            return []
        entries = []
        for msg in chm.handle_messages(None):
            entry = {
                "tag": msg.tag,
                "value" : msg.text,
                "args" : msg.args
            }
            entries.append(entry)
        return serialize_json(entries)


def serialize_json(x):
    if x is None or isinstance(x, (int, str, float, bool)):
        return x
    elif isinstance(x, (list,tuple)):
        return type(x)(serialize_json(v) for v in x)
    elif isinstance(x, dict):
        return {serialize_json(k):serialize_json(v) for k,v in x.items()}
    elif hasattr(x, "stringify"):
        return x.stringify()
    else:
        return repr(x)


def machaon_server(root):
    """ machaonを利用する単体のサーバーアプリ """
    return InternalServer(MacaServerApp(root), root.temp_spirit())


if __name__ == "__main__":
    from machaon.app import AppRoot
    root = AppRoot()
    svr = root.initialize_as_server()
    root.get_ui().wrap_width = 120
    root.add_package("xuthus","package:xuthus")
    root.add_package("protenor","package:protenor")
    root.add_package("bianor","package:bianor")
    root.add_package("morpho","package:morpho")
    root.add_package("ageha","package:ageha")
    root.run()
    svr.test_server(32100).start()


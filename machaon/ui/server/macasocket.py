

import asyncio
import json
import time
from websockets.sync.server import serve
from websockets.sync.client import connect


from machaon.app import AppRoot
from machaon.ui.basic import Launcher
from machaon.process import ProcessSentence
from machaon.ui.server.api import serialize_json

# eval [Request]
#    コマンドの実行
# 残り: メッセージ

# suspend [Request]
#    プロセスの中断

# history [Request]
#    入力履歴を取得する
#    

# put:XXXX
#     プロセスからのメッセージ
# Response:
#    [process-id]: {
#        tag: 
#        message:
#        [args]:
#    }[]
#    POLL

# progress:XXXX
#    プログレスバーの状態

# process:XXXX
#    [Int]: プロセスID

class MacaSocketServer(Launcher):
    """ apiを実装する """
    def __init__(self, url, port):
        super().__init__()
        self._url = url
        self._port = port
        self._ws = None

    def entrypoint(self, websock):
        self._ws = websock
        while True:
            time.sleep(0.2)

            # リクエストを処理する
            message = None
            try:
                message = websock.recv(timeout=0)
            except TimeoutError:
                pass

            if message is not None:
                code, sep, tail = message.partition(" ")
                if not sep:
                    continue
                self.request_handler(code, tail)

            # メッセージを取り出し、イベントを発する
            self.update_chamber_messages(None)
    
    def request_handler(self, code, remained):
        if code == "eval":
            message = remained
            self.launch_message(message)
        elif code == "history":
            delta = 1
            try:
                delta = int(remained)
            except Exception as e:
                pass
            self.shift_history(delta)

    def main(self):
        with serve(self.entrypoint, self._url, self._port) as server:
            server.serve_forever()  # run forever

    #
    #
    #
    def launch_message(self, message: str):
        sentence = ProcessSentence(message)
        pid = self.app.eval_object_message(sentence)
        return pid
    
    def get_process_update(self):
        chm = self.app.chambers().get_active()
        if chm is None:
            return []
        for msg in chm.handle_messages(None):
            entry = {
                "value" : msg.text,
                **msg.args
            }
            yield msg.tag, entry

    #
    # オーバーライド
    #
    def run_mainloop(self):
        self.main()

    def message_handler(self, msg, *, nested=False):
        # メッセージをレスポンスに変換する
        if msg.tag in ("eval-message", "eval-message-seq"):
            return super().message_handler(msg, nested=nested)
        elif msg.tag == "progress-display":
            command = msg.text
            key, iproc = msg.req_arguments("key", "process")
            view = self.update_progress_display_view(command, iproc, key, msg.args)
            ws_respond(self._ws, "progress:{}".format(command), iproc, {
                "key": view.key,
                "title": view.title,
                "total": view.total,
                "progress": view.get_progress_rate(),
                "marquee": view.is_marquee(),
                "lastbit": view.lastbit,
                "changed": view.changed
            })
        else:
            iproc = msg.args.pop("process", None)
            ws_respond(self._ws, "put:{}".format(msg.tag), iproc, {"value": msg.text, "args": msg.args})
        
    def add_chamber_menu(self, chamber):
        pass

    def update_chamber_menu(self, *, active=None, ceased=None):
        pass
    
    def remove_chamber_menu(self, chamber):
        pass

    def get_input_text(self, pop=False):
        raise NotImplementedError()
    
    def insert_input_text(self, text):
        ws_respond(self._ws, "input:insert", None, text)

    def replace_input_text(self, text):
        ws_respond(self._ws, "input:replace", None, text)
    
    def get_input_prompt(self):
        return "" # 入力プロンプトはなし

    #
    def on_enter(self):
        """ アプリ起動時 """
        pass

    def post_on_exec_process(self, process, exectime):
        """ プロセス実行開始時 """
        index = process.get_index()
        message = process.get_message()
        ws_respond(self._ws, "process:start", index, {"message": message, "time": exectime})
    
    def post_on_success_process(self, process, ret, spirit):
        """ プロセスの正常終了時 """
        if ret.is_pretty():
            spirit.instant_pprint(ret)
        ws_respond(self._ws, "process:success", process.get_index(), { 
            "typename": ret.get_typename(), 
            "value": ret.stringify(),
            "pretty": ret.is_pretty()
        })

    def post_on_interrupt_process(self, process):
        """ プロセス中断時 """
        ws_respond(self._ws, "process:interrupted", process.get_index())
    
    def post_on_error_process(self, process, excep):
        """ プロセスの異常終了時 """
        ws_respond(self._ws, "process:failed", process.get_index(), {
            "summary": excep.summarize()                  
        })

    def post_on_end_process(self, process):
        """ 正常であれ異常であれ、プロセスが終了した後に呼ばれる """
        ws_respond(self._ws, "process:end", process.get_index())

    def on_exit(self):
        """ アプリ終了時 """
        ws_respond(self._ws, "exit", None)
        self.destroy()

    def destroy(self):
        self._ws.close()


def ws_respond(websock, code, process_index, value=None):
    parts = []
    parts.append(code)

    if process_index is None:
        parts.append("*")
    else:
        parts.append("{}".format(process_index))

    if value is not None:
        if not isinstance(value, dict):
            raise TypeError("value must be dict")
        parts.append(json.dumps(serialize_json(value)))
    
    msg = " ".join(parts)
    websock.send(msg)

def parse_ws_message(message: str):
    code, sep, tail = message.partition(" ")
    iproc, sep, rest = tail.partition(" ")
    if rest:
        value = json.loads(rest)
    else:
        value = None
    return code, iproc, value



if __name__ == "__main__":
    # サーバー
    svr = MacaSocketServer("localhost", 8765)

    from machaon.app import AppRoot
    root = AppRoot()
    root.initialize(ui=svr)
    root.boot_core()
    root.boot_ui()
    root.typemodule.add_fundamentals() 

    import threading
    def server_main():
        root.ui.run_mainloop()
    thr = threading.Thread(target=server_main)
    thr.start()
    print("started WebSocket server: {}".format("localhost:8765"))

    # クライアント
    with connect("ws://localhost:8765") as websocket:
        websocket.send("eval @@test-progress")
        time.sleep(1)
        websocket.send("eval Str help")

        for message in websocket:
            if not message:
                continue
            code, iprocess, value = parse_ws_message(message)
            if code == "eval":
                print("プロセスが開始：{}".format(iprocess))
            elif code.startswith("put"):
                print("{} ID={}: {}".format(code, iprocess, value))
            elif code == "exit":
                break
            else:
                print("{} ID={}: {}".format(code, iprocess, value))

        print("end client")


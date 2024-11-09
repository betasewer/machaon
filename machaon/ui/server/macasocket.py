

import asyncio
import json
import time
from websockets.sync.server import serve
from websockets.sync.client import connect

from machaon.app import AppRoot
from machaon.ui.basic import Launcher
from machaon.process import ProcessSentence, Spirit, Process
from machaon.ui.server.api import serialize_json
from machaon.core.object import Object
from machaon.types.stacktrace import ErrorObject

#
# [Request]
#
# - eval
#     コマンドの実行
# 残り: メッセージ
# - suspend
#     プロセスの中断
# - sync
#     全プロセスを同期する
# - history
#     入力履歴を取得する
#    
# [Response]
#
# - put:XXXX
#     プロセスからのメッセージ
# contents:
#    [process-id]: {
#        tag: 
#        message:
#        [args]:
#    }[]
#    POLL
# - progress:XXXX
#    プログレスバーの状態
# - process:XXXX
#    プロセスの実行結果
#    [Int]: プロセスID
#

def parse_int(value: str, default=None):
    try:
        return int(value)
    except:
        return default

class MacaSocketServer(Launcher):
    """ apiを実装する """
    def __init__(self, url, port):
        super().__init__()
        self._url = url
        self._port = port
        self._ws = None
        self._windows = {}

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
    
    def request_handler(self, code: str, remained):
        if code.startswith("eval"):
            message = remained
            c, sep, tail = code.partition("-")
            if sep:
                parent = parse_int(tail)
                self.launch_message(message, parent)
            else:
                self.launch_message(message)
        elif code == "remove-process":
            pid = parse_int(remained)
            if pid is None:
                return
            self.remove_process(pid)
        elif code == "history":
            delta = parse_int(remained, 1)
            self.shift_history(delta)
        elif code == "sync":
            self.sync_messages()

    def main(self):
        with serve(self.entrypoint, self._url, self._port) as server:
            server.serve_forever()  # run forever

    #
    #
    #
    def launch_message(self, message: str, window_index: int = None):
        sentence = ProcessSentence(message)
        process_starter = self.app.eval_object_message(sentence, norun=True)
        if process_starter is None:
            return

        pid = process_starter.process.get_index()
        self.ws_on_new_process(UIProcessWindow(pid, message, window=window_index))

        process_starter()

    def sync_messages(self):
        from machaon.process import ProcessChamber
        chm: ProcessChamber = self.app.chambers().get_active()
        if chm is None:
            return 
        for proc in chm.get_processes():
            pid = proc.get_index()
            if pid not in self._windows:
                self._windows[pid] = UIProcessWindow(pid, proc.sentence)
            self.ws_on_new_process(self._windows[pid])

            self.post_on_exec_process(proc, None) # exectime

            for msg in proc.get_handled_messages():
                self.message_handler(msg, proc.get_index())

            if proc.is_finished():
                if proc.is_interrupted():
                    self.post_on_interrupt_process(proc)
                elif proc.is_failed():
                    cxt = proc.get_last_invocation_context()
                    if cxt is not None:
                        error = proc.get_result_error()
                        errobj = cxt.new_invocation_error_object(error) if error else None
                        self.post_on_error_process(proc, errobj, recall=True)
                else:
                    cxt = proc.get_last_invocation_context()
                    if cxt is not None:
                        result = proc.get_result_object()
                        self.post_on_success_process(proc, result, cxt.spirit, recall=True)

    def remove_process(self, process_id: int):
        # プロセスを削除する
        removed = self.chambers.get_active().drop_processes(lambda x:x.index == process_id)
        if len(removed) == 0:
            return
        self.app.objcol.delete(str(process_id))
        # UIデータを削除する
        if process_id in self._windows:
            del self._windows[process_id]
        # プロセス返り値を削除する
        self.app.create_root_context().remove_process_object(process_id)

    def ws_on_new_process(self, window: 'UIProcessWindow'):
        self._windows[window.process] = window
        # プロセスの開始を受け付けた旨を応答する
        args = {
            "message": window.message
        }
        if window.window is not None:
            args["window"] = window.window
        ws_respond(self._ws, "process:new", window.process, args)
    
    #
    # オーバーライド
    #
    def run_mainloop(self):
        self.main()

    def message_handler(self, msg, iproc=None, *, nested=False):
        # メッセージをレスポンスに変換する
        if msg.tag in ("eval-message", "eval-message-seq"):
            return super().message_handler(msg, nested=nested)
        
        iproc = iproc if iproc is not None else msg.req_arguments("process")[0]
        if msg.tag == "progress-display":
            command = msg.text
            key = msg.req_arguments("key")[0]
            view = self.update_progress_display_view(command, iproc, key, msg.args)
            ws_respond(self._ws, "progress:{}".format(command), iproc, {
                "key": view.key,
                "title": view.title,
                "total": view.total,
                "progress": view.get_progress_rate(),
                "marquee": view.is_marquee(),
            })
        elif msg.tag == "delete-message":
            lineno = msg.argument("line", -1)
            cnt = msg.argument("count", 1)
            # respond
        else:
            msg.args.pop("process", None) # processを落として帯域を節約
            msg.args.pop("context", None) # contextも落とす
            ws_respond(self._ws, "put", iproc, {"tag": msg.tag, "value": msg.text, "args": msg.args})

    def add_chamber_menu(self, chamber):
        pass

    def update_chamber_menu(self, *, active=None, ceased=None):
        pass
    
    def remove_chamber_menu(self, chamber):
        pass

    def get_input_text(self, pop=False):
        raise NotImplementedError()
    
    def insert_input_text(self, text):
        ws_respond(self._ws, "input:insert", None, {'text': text})

    def replace_input_text(self, text):
        ws_respond(self._ws, "input:replace", None, {'text': text})
    
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
    
    def post_on_success_process(self, process, ret, spirit, *, recall=False):
        """ プロセスの正常終了時 """
        if not recall:
            self.print_success_result(spirit, ret)
        ws_respond(self._ws, "process:success", process.get_index(), { 
            "typename": ret.get_typename(), 
            "value": ret.stringify(),
            "pretty": ret.is_pretty()
        })

    def post_on_interrupt_process(self, process):
        """ プロセス中断時 """
        ws_respond(self._ws, "process:interrupted", process.get_index())
    
    def post_on_error_process(self, process: Process, excep: Object[ErrorObject], *, recall=False):
        """ プロセスの異常終了時 """
        ws_respond(self._ws, "process:failed", process.get_index(), {
            "typename": excep.value.get_error_typename(), 
            "summary": excep.summarize()
        })
        if not recall:
            # エラー発生個所
            cxt = process.get_last_invocation_context()
            if cxt is not None:
                for line in cxt.display_error_part().splitlines():
                    process.post("message", line)
            # 例外メッセージと簡易スタックトレース
            for line in excep.value.display().splitlines():
                process.post("message", line)

    def post_on_end_process(self, process):
        """ 正常であれ異常であれ、プロセスが終了した後に呼ばれる """
        ws_respond(self._ws, "process:end", process.get_index())

    def on_exit(self):
        """ アプリ終了時 """
        ws_respond(self._ws, "exit", None)
        self.destroy()

    def destroy(self):
        self._ws.close()

    #
    #
    #
    def print_success_result(self, spirit: Spirit, ret: Object):
        t = ret.get_typename()
        context = spirit.process.get_last_invocation_context()
        if t == "Type":
            from machaon.types.fundamental import TypeType
            TypeType().help(ret.value, context, spirit)
        else:
            spirit.instant_pprint(ret, ref="result") # 常に詳細表示


def ws_respond(websock, code, process_index, value:dict=None):
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

#
#
#
class UIProcessWindow:
    def __init__(self, pid, message, *, window=None):
        self.process: int = pid
        self.message: str = message
        self.window: int = window


    



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
        websocket.send("eval 2 / 0 + 1")
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


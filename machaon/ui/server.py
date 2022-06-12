
from machaon.ui.basic import Launcher
from machaon.process import Spirit

import logging
import os
import datetime

#
#
class LoggingLauncher(Launcher):
    def __init__(self, args):
        super().__init__()
        self.shell = args["shell"]
        self._title = args["title"]
        self._logger = None
        self._loggersetup = {}
        if "log" in args:
            self._loggersetup["handler"] = args["log"]
        elif "logfile" in args:
            self._loggersetup["file_handler"] = args["logfile"]

    #
    # ログファイル設定
    #
    def init_screen(self):
        """ 初期化 """
        if "handler" in self._loggersetup:
            self.setup_logger(self._loggersetup["handler"])
        elif "file_handler" in self._loggersetup:
            self.setup_file_logger(self._loggersetup["file_handler"])
        # 
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d|%H:%M.%S")
        self.writelog("message", "[{}] 起動 [{}]".format(self._title, timestamp))

    def setup_logger(self, handler):
        self._logger = logging.getLogger("machaon batch {}".format(self._title))
        self._logger.setLevel(logging.INFO)
        self._logger.addHandler(handler)

    def setup_file_logger(self, dateset):
        if dateset == "daily":
            date = datetime.datetime.today().strftime("%Y%m%d")
        elif dateset == "monthly":
            date = datetime.datetime.today().strftime("%Y%m")
        else:
            raise ValueError(dateset)
        logpath = os.path.join(self.app.get_log_dir(), "{}{}.txt".format(self._title, date))
        self.setup_logger(logging.FileHandler(logpath, encoding="utf-8"))
    
    def get_logger(self):
        return self._logger

    def writelog(self, tag, text, *, nobreak=False, **kwargs):
        if self._logger is None:
            return
        # nobreakは無視される
        if tag == "error":
            self._logger.log(logging.ERROR, text)
        elif tag == "warn":
            self._logger.log(logging.WARN, text)
        else:
            self._logger.log(logging.INFO, text)

    def writelog_setview(self, rows, columns, dataid, context):
        self._logger.log(logging.INFO, "\t".join(columns))
        for _index, row in rows:
            self._logger.log(logging.INFO, "\t".join(row))

    #
    # オーバーライド
    #
    def insert_screen_text(self, *args, **kwargs):
        self.writelog(*args, **kwargs)
        return self.shell.insert_screen_text(*args, **kwargs)
    
    def delete_screen_text(self, *args, **kwargs):
        return self.shell.delete_screen_text(*args, **kwargs)

    def replace_screen_text(self, *args, **kwargs):
        return self.shell.replace_screen_text(*args, **kwargs)
    
    def save_screen_text(self):
        return self.shell.save_screen_text()
    
    def drop_screen_text(self, *args, **kwargs):
        return self.shell.replace_screen_text(*args, **kwargs)

    def insert_screen_setview(self, *args, **kwargs):
        self.writelog_setview(*args, **kwargs)
        return self.shell.insert_screen_setview(*args, **kwargs)

    def add_chamber_menu(self, chamber):
        pass

    def update_chamber_menu(self, *, active=None, ceased=None):
        pass
    
    def remove_chamber_menu(self, chamber):
        pass
        
    def get_input_text(self, pop=False):
        raise NotImplementedError()
    
    def get_input_prompt(self):
        return "" # 入力プロンプトはなし

    #
    def post_on_exec_process(self, process, exectime):
        """ プロセス実行開始時 """
        index = process.get_index()
        message = process.get_message()
        process.post("input", "P{:03} | {} [{}]".format(index, message, exectime.strftime("%Y-%m-%d|%H:%M.%S")))
    
    def post_on_success_process(self, process, ret, spirit):
        """ プロセスの正常終了時 """
        ret.pprint(spirit) # 結果は常に詳細表示にする
        process.post("message", " -> {} [{}]".format(ret.summarize(), ret.get_typename()))

    def post_on_interrupt_process(self, process):
        """ プロセス中断時 """
        process.post("message-em", "中断しました")
    
    def post_on_error_process(self, process, excep):
        """ プロセスの異常終了時 """
        index = process.get_index()
        process.post("input", " process[{}] error ".format(index), nobreak=True)
        #
        process.post("error", "{}".format(excep.summarize()))
        spi = Spirit(self.app, process)
        excep.value.traceback(0).showall(spi)

    def post_on_end_process(self, process):
        """ 正常であれ異常であれ、プロセスが終了した後に呼ばれる """
        pass # 何も表示しない

    def on_exit(self):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d|%H:%M.%S")
        self.writelog("message", "[{}] 終了 [{}]".format(self._title, timestamp))


class BatchLauncher(LoggingLauncher):
    is_async = False

    def __init__(self, args):
        super().__init__(args)

    def message_handler(self, msg, *, nested=False):
        messages = []
        if msg.tag == "eval-message-seq":
            messages, _chamber = msg.req_arguments("messages", "chamber")
        elif msg.tag == "eval-message":
            message = msg.req_arguments("message")
            messages.append(message)
        else:
            return super().message_handler(msg, nested=nested)

        if messages:
            for message in messages:
                # メッセージを実行する
                self.app.eval_object_message(message) 
                # プロセスにたまったメッセージを処理する（再帰呼び出し）
                self.update_chamber_messages(None)
    
    def run_mainloop(self):
        # スタートアップメッセージを処理して終了する
        self.update_chamber_messages(None)
        self.app.exit()


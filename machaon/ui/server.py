
from requests import head
from machaon.ui.basic import Launcher
from machaon.process import Spirit, ProcessSentence

import logging
import os
import datetime

#
#
class LoggingLauncher(Launcher):
    """
    """
    def __init__(self, args):
        super().__init__()
        self.shell = args["shell"]
        self._title = args["title"]
        self._logger = None
        self._loggersetup = {k:args.get(k) for k in ("loghandler", "logfileperiod", "logfile", "logdir")}
        # handler : logging.Handler
        # fileperiod : str = daily, monthly

    #
    # ログファイル設定
    #
    def init_screen(self):
        """ 初期化 """
        if self._loggersetup["loghandler"]:
            # ハンドラを直接指定
            self.setup_logger(self._loggersetup["loghandler"])
        else:
            logpath = self.get_logfile_path()
            if logpath is not None:
                # ログファイルハンドラを指定
                self.setup_file_logger(logpath)
            else:
                # ヌルハンドラを指定
                self.setup_logger(logging.NullHandler())
        
        self.on_enter()

    def setup_logger(self, handler):
        self._logger = logging.getLogger("machaon batch {}".format(self._title))
        self._logger.setLevel(logging.INFO)
        self._logger.addHandler(handler)

    def setup_file_logger(self, logpath):
        f = logging.FileHandler(logpath, encoding="utf-8")
        
        # カスタムログレコードの生成を設定する
        super_factory = logging.getLogRecordFactory()
        def record_factory(name, level, fn, lno, msg, args, exc_info, func=None, sinfo=None, **kwargs):
            record = super_factory(name, level, fn, lno, msg, args, exc_info, func=None, sinfo=None, **kwargs)
            if level == logging.INFO:
                levelsign = ""
            elif level == logging.ERROR:
                levelsign = "失敗 "
            elif level == logging.WARN:
                levelsign = "注意 "
            elif level == logging.CRITICAL:
                levelsign = "破綻 "
            else:
                levelsign = "調査 "
            record.levelsign = levelsign
            return record
        logging.setLogRecordFactory(record_factory)
        f.setFormatter(logging.Formatter("{asctime} - {levelsign}{message}", style="{"))

        self.setup_logger(f)
    
    def get_logger(self):
        return self._logger

    def get_logfile_path(self):
        filename = None

        period = self._loggersetup["logfileperiod"]
        if period is not None:
            if period == "daily":
                date = datetime.datetime.today().strftime("%Y%m%d")
            elif period == "monthly":
                date = datetime.datetime.today().strftime("%Y%m")
            else:
                raise ValueError(period+": invalid file logging period name")
            filename = "{}{}.txt".format(self._title, date)

        if filename is None and self._loggersetup["logfile"]:
            filename = self._loggersetup["logfile"]

        if filename is None:
            return None
            
        if self._loggersetup["logdir"]:
            logdir = self._loggersetup["logdir"]
        else:
            logdir = self.app.get_log_dir()
        
        return os.path.join(logdir, filename)

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
        """ 表はリスト形式でレイアウトする """
        if not columns:
            return
        maxcolwidth = max([len(x) for x in columns])
        for index, row in rows:
            self._logger.log(logging.INFO, "[{}]".format(index))
            for col, val in zip(columns, row):
                self._logger.log(logging.INFO, "{} : {}".format(col.ljust(maxcolwidth), val))

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

    def insert_screen_progress_display(self, command, view):
        self.shell.insert_screen_progress_display(command, view)

        if command == "start":
            if view.title:
                header = "{}: ".format(view.title)
            else:
                header = ""

            if view.is_marquee():
                l = "* {}処理中...".format(header)
            else:
                l = "* {}処理中({})... ".format(header, view.total)
            self.writelog("message", l)

        elif command == "end":
            if view.is_marquee():
                l = "* 処理完了({})".format(view.progress)
            else:
                l = "* 処理完了"
            self.writelog("message", l)
        
            
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
    def on_enter(self):
        """ アプリ起動時 """
        header = "##アプリ起動 [{}]".format(self._title)
        self.writelog("message", header)

    def post_on_exec_process(self, process, exectime):
        """ プロセス実行開始時 """
        index = process.get_index()
        message = process.get_message()
        process.post("input", "#プロセス起動 {:03} | {}".format(index, message)) # exectime.strftime("%Y-%m-%d|%H:%M.%S")
    
    def post_on_success_process(self, process, ret, spirit):
        """ プロセスの正常終了時 """
        process.post("message", " -> [{}]".format(ret.get_typename()))
        ret.pprint(spirit) # 結果は常に詳細表示にする

    def post_on_interrupt_process(self, process):
        """ プロセス中断時 """
        process.post("message-em", " ->* 中断しました")
    
    def post_on_error_process(self, process, excep):
        """ プロセスの異常終了時 """
        process.post("error", " ->* エラーが発生しました ")
        #
        process.post("error", excep.summarize())
        spi = Spirit(self.app, process)
        process.post("error", "スタックトレース：")
        for line in excep.value.traceback(0).display(spi).splitlines():
            process.post("error", "    " + line)

    def post_on_end_process(self, process):
        """ 正常であれ異常であれ、プロセスが終了した後に呼ばれる """
        pass # 何も表示しない

    def on_exit(self):
        """ アプリ終了時 """
        self.writelog("message", "##アプリ終了 [{}]".format(self._title))



#
#
#
class BatchLauncher(LoggingLauncher):
    """
    対話的でないアプリケーション。
    起動後ただちにコマンドを実行し、終了する。
    """
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
                self.app.eval_object_message(ProcessSentence(message, auto=True, autoleading=True)) 
                # プロセスにたまったメッセージを処理する（再帰呼び出し）
                self.update_chamber_messages(None)
    
    def run_mainloop(self):
        # スタートアップメッセージを処理して終了する
        self.update_chamber_messages(None)
        self.app.exit()

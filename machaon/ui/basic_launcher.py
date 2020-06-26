#!/usr/bin/env python3
# coding: utf-8

import os
import datetime
import traceback
from typing import Tuple, Sequence, List

from machaon.cui import fixsplit, composit_text
from machaon.process import ProcessMessage

#
meta_command_sigil = "/"

#
#
#
class Launcher():
    wrap_width = 0xFFFFFF

    def __init__(self, title="", geometry=None):
        self.app = None
        self.screen_title = title or "Machaon Terminal"
        self.screen_geo = geometry or (900,400)
        self.theme = None
        
    def init_with_app(self, app):
        self.app = app
        self.init_screen()
    
    def init_screen(self):
        pass

    #
    #
    #
    def message_handler(self, msg):
        """ メッセージを処理する """
        if msg.is_embeded():
            for msg in msg.expand():
                self.message_handler(msg)
        else:
            tag = msg.tag
            if tag == "delete-message":
                cnt = msg.argument("count")
                lno = msg.argument("line")
                self.delete_screen_message(lno, cnt)
            elif tag == "dataview":
                datas = self.app.get_active_chamber().get_bound_data(running=True)
                if datas is None:
                    msg.tag = "message"
                    msg.text = "データが作成されていません" + "\n"
                    self.insert_screen_message(msg)
                elif datas.nothing():
                    msg.tag = "message"
                    msg.text = "結果は0件です" + "\n"
                    self.insert_screen_message(msg)
                else:
                    viewer = self.dataviewer(datas.get_viewtype())
                    self.insert_screen_dataview(msg, viewer, datas)
            elif tag == "canvas":
                self.insert_screen_canvas(msg)
            else:
                # 適宜改行を入れる
                if msg.argument("wrap", True):
                    msg.text = composit_text(msg.get_text(), type(self).wrap_width)

                # ログウィンドウにメッセージを出力
                self.insert_screen_message(msg)
    
    #
    def handle_chamber_message(self, chamber):
        for msg in chamber.handle_message():
            self.message_handler(msg)
        return True

    #
    # メッセージウィンドウの操作
    #
    def insert_screen_message(self, msg):
        pass

    def delete_screen_message(self, lineno, count):
        pass

    def replace_screen_message(self, msgs):
        pass

    #
    # プロセスの情報を更新するために監視
    #
    def watch_active_process(self):
        pass

    def watch_running_process(self, states):
        pass
        
    # 
    def dataviewer(self, viewtype):
        return None

    def insert_screen_dataview(self, msg, viewer, data):
        pass
    
    #
    def insert_screen_appendix(self, values, title=""):
        pass
    
    #
    def insert_screen_canvas(self, canvas):
        pass
    
    # ログ保存用にテキストのみを取得する
    def get_screen_texts(self):
        pass
    
    #
    # 入力欄の操作
    #    
    # コマンドを実行する
    def invoke_command(self, command):
        # 終了コマンド
        if command == "exit":
            self.app.exit()
            return
        
        if not command:
            return

        # 特殊コマンド
        if command[0] == meta_command_sigil:
            self.invoke_meta_command(command[1:])
            return
    
        chamber = self.app.run_process(command) # 実行

        self.update_active_chamber(chamber, updatemenu=False)
        self.add_chamber_menu(chamber)

        # この時点でプロセスが終了している場合もあり、更新させるために手動で状態を追加しておく
        states = self.app.get_chambers_state()
        states["running"].append(chamber.get_index())
        self.watch_running_process(states)
    
    #
    def invoke_meta_command(self, command):
        commandhead, commandtail = fixsplit(command, maxsplit=1)
        if not commandhead:
            msg = None

        elif commandhead[0].isdigit():
            # データのインデックスによる即時選択
            procindex, itemindex = parse_procindex(commandhead)
            try:
                index = int(itemindex)
            except ValueError as e:
                msg = str(e)
            else:
                msg = self.meta_command_select_dataview(index, procindex)
                if commandtail:
                    msg = self.meta_command_show_dataview_item(None, procindex, commandtail, toinput=True)

        elif commandhead.endswith("."):
            # コマンド接頭辞の設定
            prefix = commandhead[1:].strip()
            msg = self.meta_command_set_prefix(prefix)

        elif commandhead.startswith("put"):
            # データビューの選択アイテムの値を画面に展開する
            procindex, itemname = parse_procindex(commandhead[len("put"):])
            msg = self.meta_command_show_dataview_item(itemname, procindex, "", toinput=False)
        
        elif commandhead.startswith("="):
            # データビューの選択アイテムの値をコマンド欄に展開する
            procindex, itemname = parse_procindex(commandhead[1:])
            msg = self.meta_command_show_dataview_item(itemname, procindex, commandtail, toinput=True)
        
        elif commandhead.startswith("pred"):
            # データビューのカラムの一覧を現在のプロセスペインの末尾に表示する
            procindex, keyword = parse_procindex(command[len("pred"):])
            msg = self.meta_command_show_predicates(keyword, procindex)
        
        elif commandhead.startswith("arghelp"):
            # 引数またはアクティブなコマンドのヘルプを末尾に表示する
            procindex, _ = parse_procindex(commandhead[len("arghelp"):])
            msg = self.meta_command_show_help(commandtail, procindex)
        
        elif commandhead.startswith("a"):
            # アクティブなコマンドの引数をコマンド欄に展開する
            procindex, _ = parse_procindex(commandhead[len("a"):])
            argname, restcommand = fixsplit(commandtail, maxsplit=1)
            msg = self.meta_command_reinput_process_arg(argname, procindex, restcommand)

        elif command.startswith("what"):
            # 文字列を解析し、コマンドとして可能な解釈をすべて示す
            cmdstr = command[len("what"):].strip()
            msg = self.meta_command_show_syntax(cmdstr)

        elif command.startswith("invoke"):
            # 呼び出し引数と結果を詳細に表示する
            procindex, _ = parse_procindex(command[len("invoke"):])
            msg = self.meta_command_show_invocation(procindex)
        
        elif command.startswith("savelog"):
            msg = self.meta_command_savelog(command[len("savelog"):].strip())
            
        elif command.startswith("!"):
            # Pythonの式を評価する
            libnames, expr = parse_procindex(command[1:])
            msg = self.meta_command_eval_py(expr, libnames.split())
        
        elif command.startswith("help"):
            values = [
                ("(integer...)", "インデックスでアイテムを選択し入力欄に展開"),
                ("(string...).", "コマンド接頭辞の設定"),
                (">", "現在の選択アイテムを入力欄に展開"),
                ("put", "現在の選択アイテムを画面に展開"),
                ("pred", "データビューの述語の一覧を表示"),
                ("a", "プロセスの実引数を入力欄に展開"),
                ("invoke", "プロセスの実引数と実行結果を表示"),
                ("arghelp", "プロセスの引数ヘルプを表示"),
                ("savelog", "プロセスのログを保存する"),
                ("what", "コマンドの可能な解釈を全て表示"),
                ("!", "Pythonの式を評価して結果を表示"),
                ("help", "このヘルプを表示"),
            ]
            values = [(meta_command_sigil+x,y) for (x,y) in values]
            self.insert_screen_appendix(values, title="メタコマンドの一覧")
            msg = None
        
        else:
            msg = "メタコマンド'{}'を解釈できません".format(command)
        
        if msg:
            self.insert_screen_appendix(msg, "")

    # 入力を取得
    def get_input(self, spirit, instr):
        instr += " >>> "
        spirit.message(instr, nobreak=True)
        inputtext = spirit.wait_input()
        spirit.custom_message("input", inputtext)
        return inputtext
    
    # コマンド欄を実行する
    def execute_command_input(self):
        command = self.pop_input_text()
        cha = self.app.get_active_chamber()
        if cha is not None and cha.is_waiting_input():
            cha.finish_input(command)
        else:
            self.invoke_command(command)

    # コマンド欄を復元する
    def rollback_command_input(self):
        cha = self.app.get_active_chamber()
        if cha is None:
            return
        curline = self.pop_input_text(nopop=True)
        prevline = cha.get_command()
        if curline == prevline:
            return False
        self.replace_input_text(prevline)
        return True
    
    def insert_input_text(self, text):
        """ 入力文字列をカーソル位置に挿入する """
        pass
    
    def replace_input_text(self, text): 
        """ 入力文字列を代入する """
        pass
        
    def pop_input_text(self, nopop=False):
        """ 入力文字列を取り出しクリアする """
        return ""

    #
    #
    #
    def activate_new_chamber(self):
        chamber = self.app.get_active_chamber()
        self.update_active_chamber(chamber, updatemenu=False)
        self.add_chamber_menu(chamber)

        # この時点でプロセスが終了している場合もあり、更新させるために手動で状態を追加しておく
        states = self.app.get_chambers_state()
        states["running"].append(chamber.get_index())
        self.watch_running_process(states)

    def shift_active_chamber(self, delta):
        index = self.app.get_active_chamber_index()
        if index is None:
            return
        newindex = index - delta
        if newindex<0:
            # 先頭を超えた場合は変化なし
            return
        chm = self.app.select_chamber(newindex, activate=True)
        if chm is None:
            return
        self.update_active_chamber(chm)

    def update_active_chamber(self, chamber, updatemenu=True):
        msgs = chamber.get_message()
        self.replace_screen_message(msgs) # メッセージが膨大な場合、ここで時間がかかることも。別スレッドにするか？
        self.watch_active_process()
        if updatemenu:
            self.update_chamber_menu(active=chamber.get_index())

    def add_chamber_menu(self, chamber):
        pass

    def update_chamber_menu(self, **kwargs):
        pass

    #
    # 
    #
    # ダイアログからファイルパスを入力
    def input_filepath(self, *filters:Tuple[str, str]):
        filepath = self.openfilename_dialog(filters = filters, initialdir = self.app.get_current_dir())
        if filepath:
            self.insert_input_text("{}".format(filepath))
    
    # カレントディレクトリの変更
    def change_cd_dialog(self):
        dirpath = self.opendirname_dialog(initialdir = self.app.get_current_dir())
        if dirpath:
            return self.invoke_command("cd -- {}".format(dirpath))

    def openfilename_dialog(self, **options):
        raise NotImplementedError()

    def opendirname_dialog(self, **options):
        raise NotImplementedError()

    #
    #
    #
    def select_dataview_item(self, index):
        raise NotImplementedError()
    
    #
    # ハンドラ
    #
    def put_input_command(self, spirit, command):
        tim = datetime.datetime.now().strftime("%Y-%m-%d|%H:%M.%S")
        spirit.message_em("[{}] >>> ".format(tim), nobreak=True)
        spirit.custom_message("input", command)
    
    def on_exec_process(self, spirit, process):
        """ プロセス実行時 """
        #self.put_input_command(spirit, process.get_full_command())
    
    def on_interrupt_process(self, spirit, process):
        """ プロセス中断時 """
        spirit.message_em("中断しました")
    
    def on_error_process(self, spirit, process, excep, timing):
        """ プロセスのエラーによる終了時 """
        if timing == "argparse":
            tim = "引数の解析中に"
        elif timing == "executing":
            tim = "プロセス実行の前後に"
        elif timing == "execute":
            tim = "プロセス内で"
        else:
            tim = "不明な時空間'{}'にて".format(timing)
        spirit.error("{}エラーが発生し、失敗しました。".format(tim))
        
        details = traceback.format_exception(type(excep), excep, excep.__traceback__)
        spirit.error(details[-1])
        spirit.message_em("スタックトレース：")
        spirit.message("".join(details[1:-1]))

    def on_exit_process(self, spirit, process, invocation):
        """ プロセスの正常終了時 """
        if invocation is not None:
            spirit.message_em("実行終了\n")
        
            # 引数エラーを報告
            for label, missings, unuseds in invocation.arg_errors():
                if missings:
                    spirit.warn("[{}] 以下の引数は与えられませんでした：".format(label))
                    for name in missings:
                        spirit.warn("  {}".format(name))
                if unuseds:
                    spirit.warn("[{}] 以下の引数は使用されませんでした：".format(label))
                    for name in unuseds:
                        spirit.warn("  {}".format(name))
    
    def on_bad_command(self, spirit, process, command, error):
        """ 不明なコマンド """
        #self.put_input_command(spirit, command)
        if process is None:
            spirit.error("'{}'は不明なコマンドです".format(command))
            if self.app.search_command("help"):
                spirit.message("'help'でコマンド一覧を表示できます")
        else:
            spirit.error("{}: コマンド引数が間違っています:".format(process.get_prog()))
            spirit.error(error)
            for line in process.get_help():
                spirit.message(line)
    
    def on_exit(self):
        """ アプリ終了時 """
        self.destroy()

    #
    #
    # 
    def run_mainloop(self):
        pass
    
    def destroy(self):
        pass
    
    #
    #
    #
    def get_theme(self):
        return self.theme
    
    def set_theme(self, theme):
        self.theme = theme
    

    #
    #
    #
    def meta_command_select_dataview(self, index, procindex):
        if procindex:
            chm = self.app.select_chamber(procindex, activate=True)
            if chm: 
                self.update_active_chamber(chm, updatemenu=True)
        try:
            self.select_dataview_item(index)
        except IndexError:
            return "その番号のデータは存在しません"
    
    def meta_command_set_prefix(self, prefix):
        self.app.set_command_prefix(prefix)
        return "コマンド接頭辞を設定しました ==> '{}'".format(prefix)

    def meta_command_show_dataview_item(self, predicate, procindex, restcommand, toinput):
        item = None
        chm = self.app.select_chamber(procindex)
        if chm:
            data = chm.get_bound_data()
            if data:
                item = data.selection_item()
                
        if item:
            if not predicate:
                pred = data.ref.get_link_pred()
            else:
                pred = data.ref.find_pred(predicate)
            
            if pred:
                if toinput:
                    value = str(pred.make_operator_lhs(item))
                    if restcommand:
                        value = value + " " + restcommand
                    self.replace_input_text(value)
                else:
                    spirit = chm.get_bound_spirit()
                    spirit.message("<{}>".format(pred.get_description()))
                    pred.do_print(item, spirit)
                    self.handle_chamber_message(chm)
                    self.insert_screen_appendix((), "")
            else:
                return "選択アイテムに'{}'という述語はありません".format(predicate)
        else:
            return "何も選択されていません"
    
    def meta_command_show_predicates(self, keyword, procindex):  
        chm = self.app.select_chamber(procindex)
        if chm:
            data = chm.get_bound_data()
            
        if data:
            lines = []
            for pred, keys in data.get_all_predicates():
                if keyword and not any(x.startswith(keyword) for x in keys):
                    continue
                lines.append((", ".join(keys), pred.get_description()))

            if lines:                    
                self.insert_screen_appendix(lines, title="述語一覧")
            else:
                return "該当する述語がありません"
        else:
            return "対象となるデータがありません"
        
    def meta_command_reinput_process_arg(self, argname, procindex, restcommand):
        chm = self.app.select_chamber(procindex)
        if chm:
            proc = chm.get_process()
            value, _context = proc.get_parsed_command().reproduce_arg(argname)
            if value is None:
                return "該当する引数がありません"
            if restcommand:
                value = value + " " + restcommand
            self.replace_input_text(value)
        else:
            return "対象となるデータがありません"
    
    def meta_command_show_help(self, cmd, procindex):
        if cmd:
            result = self.app.search_command(cmd)
            if not result:
                return "該当するコマンドがありません"
            target = result[0].load_target()
        else:
            chm = self.app.select_chamber(procindex)
            if chm:
                target = chm.get_process().get_target()
            else:
                return "プロセスがありません"

        if target:
            hlp = target.get_help()
            self.insert_screen_appendix("\n".join(hlp), title="コマンド <{}> のヘルプ".format(target.get_prog()))
    
    def meta_command_show_syntax(self, cmdstr):
        entries = self.app.parse_possible_commands(cmdstr)
        if entries:
            lines = "\n".join(["{}. {}".format(i+1,x.command_string()) for (i,x) in enumerate(entries)])
        else:
            lines = "有効なコマンドではありません"
        self.insert_screen_appendix(lines, title="コマンド <{}> の解釈".format(cmdstr))

    def meta_command_show_invocation(self, procindex):
        chm = self.app.select_chamber(procindex)
        if chm:
            lines = []
            def addline(level, line):
                lines.append("  "*(level-1) + line)

            addline(1, "<コマンド>")
            tg = chm.get_process().get_target()
            typ, qualname, modname = tg.get_inspection()
            addline(1, "{}: {}".format(typ, qualname))
            addline(2, "{}で定義".format(modname))
            addline(1, "")

            labels = tg.get_valid_labels()

            addline(1, "<引数>")
            cmd = chm.get_process().get_parsed_command()

            for label in labels:
                addline(1, "[{}]".format(label))
                for argname, value in cmd.get_values(label).items():
                    addline(2, "{} = {}".format(argname, value))
            
            addline(1, "")

            addline(1, "<実行>")
            inv = chm.get_process().get_last_invocation()

            for label in labels:
                for i, entry in enumerate(inv.get_entries_of(label)):
                    addline(1, "[{}][{}](".format(label, i))

                    sig = []
                    sig.extend(["{}".format(v) for v in entry.args])
                    sig.extend(["{}={}".format(k,v) for (k,v) in entry.kwargs.items()])
                    for a in sig:
                        addline(2, "{},".format(a))
                    addline(1, ")")

                    if entry.exception:
                        addline(1, "例外発生で中断:")
                        for l in traceback.format_exception_only(type(entry.exception), entry.exception):
                            addline(2, l)
                    else:                    
                        addline(2, "-> {}".format(entry.result))
            
            self.insert_screen_appendix("\n".join(lines), title="実行結果の調査")
        else:
            return "対象となるプロセスがありません"
    
    def meta_command_savelog(self, path):
        texts = self.get_screen_texts()
        if not texts:
            return "ログの保存が実装されていません"

        if not path:
            path = "log.txt"
        p = os.path.join(self.app.get_current_dir(), path)
        try:
            with open(p, "w", encoding="utf-8") as fo:
                for line in texts.splitlines():
                    fo.write(line+"\n")
            return "保存 --> {}".format(p)
        except Exception as e:
            return "エラー：{}".format(e)
            
    def meta_command_eval_py(self, expression, libnames):
        if not expression:
            return ""

        # モジュールのロード
        glo = {}
        import math
        glo["math"] = math # 数学モジュールはいつもロードする
        if libnames:
            import importlib
            for libname in libnames: # module::member>name == from module import member as name
                membername = None
                if ">" in libname:
                    libname, membername = libname.split(">")
                if "::" in libname:
                    modname, varname = libname.split("::")
                    mod = importlib.import_module(modname)
                    if membername is None:
                        membername = varname
                    glo[membername] = getattr(mod, varname)
                else:
                    if membername is None:
                        membername = libname
                    glo[membername] = importlib.import_module(libname)

        try:
            val = eval(expression, glo, {})
        except Exception as e:
            v = str(e)
        else:
            v = str(val)

        self.insert_screen_appendix(v, title=expression.strip())

#
def parse_procindex(expr):
    argname = expr
    procindex = ""
    if expr and expr[0] == "[":
        end = expr.find("]")
        if end > -1:
            procindex = expr[1:end]
            argname = expr[end+1:]
    return procindex, argname.strip()

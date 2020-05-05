#!/usr/bin/env python3
# coding: utf-8

import os
import datetime
import traceback
from typing import Tuple, Sequence, List

from machaon.cui import fixsplit
from machaon.process import ProcessMessage

#
#
#
class Launcher():
    def __init__(self, title="", geometry=(900,400)):
        self.app = None
        self.screen_title = title
        self.screen_geo = geometry
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
            else:
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
        if command[0] == ":":
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
        if command.isdigit():
            # データのインデックスによる即時選択
            index = int(command)
            msg = self.meta_command_select_dataview(index)

        elif command.endswith("."):
            # コマンド接頭辞の設定
            prefix = command[1:].strip()
            msg = self.meta_command_set_prefix(prefix)

        elif command.startswith(">"):
            # データビューの選択アイテムの値をコマンド欄に展開する
            head, restcommand = fixsplit(command[1:], sep=" ", maxsplit=1)
            procindex, itemname = parse_procindex(head)
            msg = self.meta_command_show_dataview_item(itemname, procindex, restcommand, toinput=True)
        
        elif command.startswith("="):
            # データビューの選択アイテムの値を画面に展開する
            procindex, itemname = parse_procindex(command[1:])
            msg = self.meta_command_show_dataview_item(itemname, procindex, "", toinput=False)
        
        elif command.startswith("pred"):
            # データビューのカラムの一覧を現在のプロセスペインの末尾に表示する
            procindex, keyword = parse_procindex(command[len("pred"):])
            msg = self.meta_command_show_predicates(keyword, procindex)
        
        elif command.startswith("@"):
            # アクティブなコマンドの引数をコマンド欄に展開する
            head, restcommand = fixsplit(command[1:], sep=" ", maxsplit=1)
            procindex, argname = parse_procindex(head)
            msg = self.meta_command_reinput_process_arg(argname, procindex, restcommand)

        elif command.startswith("?"):
            # 引数またはアクティブなコマンドのヘルプを末尾に表示する
            procindex, cmd = parse_procindex(command[1:])
            msg = self.meta_command_show_help(cmd, procindex)
        
        elif command.startswith("invocation"):
            # 呼び出し引数と結果を詳細に表示する
            procindex, _ = parse_procindex(command[len("invocation"):])
            msg = self.meta_command_show_invocation(procindex)
        
        else:
            msg = "不明なメタコマンドです"
        
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

    def shift_active_chamber(self, d):
        index = self.app.get_active_chamber_index()
        if index is None:
            return
        newindex = index - d
        if newindex<0:
            # 先頭を超えた場合は変化なし
            return
        if not self.app.set_active_chamber_index(newindex):
            return
        self.update_active_chamber(self.app.get_active_chamber())
        
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
    def meta_command_select_dataview(self, index):
        try:
            self.select_dataview_item(index)
        except IndexError:
            return "その番号のデータは存在しません"
    
    def meta_command_set_prefix(self, prefix):
        self.app.set_command_prefix(prefix)
        return "コマンド接頭辞を設定しました"

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
            target = chm.get_process().get_target()

        if target:
            hlp = target.get_help()
            self.insert_screen_appendix("\n".join(hlp), title="コマンド <{}> のヘルプ".format(target.get_prog()))
    
    def meta_command_show_invocation(self, procindex):
        chm = self.app.select_chamber(procindex)
        if chm:
            cmd = chm.get_process().get_parsed_command()
            inv = chm.get_process().get_last_invocation()

        else:
            return "対象となるプロセスがありません"

#
def parse_procindex(expr):
    argname = expr
    procindex = None
    if expr and expr[0] == "[":
        end = expr.find("]")
        if end > -1:
            procindex = expr[1:end]
            argname = expr[end+1:]
    return procindex, argname.strip()

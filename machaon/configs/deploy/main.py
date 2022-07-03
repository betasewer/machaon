'''
machaon 起動スクリプト
'''
from machaon.app import AppRoot
import os

# machaonフォルダの場所を指定する
basic_dir = os.path.join(os.path.dirname(__file__), "machaon")
root = AppRoot()

'''
** 初期設定 **
root.initialize(
    ui = "UIタイプ",
    basic_dir = "machaonフォルダの場所"
)
UIタイプ:
    tk    tkinterを使用 (win/osx)
    shell ターミナル（win/osx/generic）
    batch バッチ実行（all）
'''
root.initialize(
    ui="shell", 
    basic_dir=basic_dir 
)

'''
** パッケージの定義 **
root.add_package(
    "[スコープ名]",
    "[タイプ]:[ソース]"
)
タイプ / ソース：
    github        github.comのリポジトリURL:開始パッケージ名
    bitbucket     bitbucket.orgのリポジトリURL:開始パッケージ名
    package       pythonのパッケージ名
    module        pythonのモジュール名
    file          pythonのモジュールファイルへのフルパス
    package-arc   pythonのパッケージが入ったzip:開始パッケージへの相対パス
'''

root.run()

'''
machaon 起動スクリプト

** 初期設定 **
root.initialize(
    ui = "UIタイプ",
    basic_dir = "machaonフォルダの場所"
)
UIタイプ:
    tk    tkinterを使用 (win/osx)


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
from machaon.app import AppRoot
import os

# machaonフォルダの場所を指定する
basic_dir = os.path.join(os.path.dirname(__file__), "machaon")
root = AppRoot()

root.initialize(
    ui="tk", 
    basic_dir=basic_dir 
)

root.add_package(
    "machaon.shell",
    "module:machaon.types.shell"
)


root.run()

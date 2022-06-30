from machaon.platforms.common import exists_external_module, fallback_generic

if not exists_external_module("objc", "AppKit"):
    print("ドラッグ・ドロップ機能には、objc, AppKitモジュールが必要です")
    Exports = fallback_generic("dnd")
else:
    from ._dnd import TkDND
    class Exports:
        @staticmethod
        def tkDND():
            return TkDND()




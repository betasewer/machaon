import tkinter.ttk as ttk

import machaon.platforms

#
# 色の設定
#
class ShellTheme():    
    def __init__(self, config={}):
        self.config=config
    
    def extend(self, config):
        self.config.update(config)
        return self
    
    def setval(self, key, value):
        self.config[key] = value

    def getval(self, key, fallback=None):
        c = self.config.get(key)
        if c is None and fallback is not None:
            c = fallback
        if c is None:
            c = dark_classic_theme().config[key]
        return c
    
    def getfont(self, key):
        fontname = self.getval("font", machaon.platforms.current.preferred_fontname)
        fontsize = self.getval(key+"size", machaon.platforms.current.preferred_fontsize)
        if isinstance(fontsize, str) and not fontsize.isdigit():
            return None
        return (fontname, int(fontsize))

#
def dark_classic_theme():
    return ShellTheme({
        "color.message" : "#CCCCCC",
        "color.background" : "#000000",
        "color.insertmarker" : "#CCCCCC",
        "color.message_em" : "#FFFFFF",
        "color.warning" : "#FF00FF",
        "color.error" : "#FF0000",
        "color.hyperlink" : "#00FFFF",
        "color.userinput" : "#00FF00",
        "color.label" : "#FFFFFF",
        "color.highlight" : "#000080",
        "ttktheme" : "clam",
    })
    
def dark_blue_theme():
    return dark_classic_theme().extend({
        "color.message_em" : "#00FFFF",
        "color.warning" : "#D9FF00",
        "color.error" : "#FF0080",
        "color.hyperlink" : "#00FFFF",
        "color.userinput" : "#00A0FF",
        "color.highlight" : "#0038A1", 
    })

def grey_green_theme():
    return dark_classic_theme().extend({
        "color.background" : "#EFEFEF",
        "color.insertmarker" : "#000000",
        "color.message" : "#000000",
        "color.message_em" : "#008000",
        "color.warning" : "#FF8000",
        "color.error" : "#FF0000",
        "color.hyperlink" : "#0000FF",
        "color.userinput" : "#00B070",
        "color.label" : "#000000",
        "color.highlight" : "#FFD0D0",
    })

def papilio_machaon_theme():
    return grey_green_theme().extend({
        "color.background" : "#88FF88",
        "color.message_em" : "#FFA500",
        "color.message" : "#000000",
        "color.highlight" : "#FFA500",
    })

themebook = {
    "classic" : dark_classic_theme,
    "darkblue" : dark_blue_theme,
    "greygreen" : grey_green_theme,
    "papilio.machaon" : papilio_machaon_theme
}


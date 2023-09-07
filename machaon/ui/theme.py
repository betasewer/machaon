
import machaon.platforms

#
# 色の設定
#
class ShellTheme():    
    """ @type
    シェルに設定するカラーテーマ。
    """
    def __init__(self, name, config=None):
        self._name = name
        self.config = config or {}
    
    def extend(self, name, config):
        th = ShellTheme(name, {})
        th.config.update(self.config)
        th.config.update(config)
        return th
    
    def setval(self, key, value):
        self.config[key] = value

    def getval(self, key, fallback=None):
        """ @method [option]
        オプション
        Params:
            key(Str):
        Returns:
            Any:
        """
        c = self.config.get(key)
        if c is None and fallback is not None:
            c = fallback
        if c is None:
            c = dark_classic_theme().config[key]
        return c
    
    def getfont(self, key):
        fontname = self.getfontname()
        fontsize = self.getval(key+"size", machaon.platforms.ui().preferred_fontsize)
        if isinstance(fontsize, str) and not fontsize.isdigit():
            return None
        if fontname is None or fontsize is None:
            return None
        return (fontname, int(fontsize))
    
    def getfontname(self):
        """ @method
        フォント名
        Returns:
            Str:
        """
        return self.getval("font", machaon.platforms.ui().preferred_fontname)

    #
    def name(self):
        """ @method
        テーマ名
        Returns:
            Str:
        """
        return self._name

    def options(self):
        """ @method
        テーマ設定値
        Returns:
            Str:
        """
        return self._theme

    #
    def apply(self, app):
        """ @method spirit
        このカラーテーマをUIに適用する。
        """
        app.root.get_ui().apply_theme(self)


#
def dark_classic_theme():
    return ShellTheme("classic", {
        "color.message" : "#CCCCCC",
        "color.background" : "#242428",
        "color.insertmarker" : "#CCCCCC",
        "color.message-em" : "#FFFFFF",
        "color.warning" : "#FF00FF",
        "color.error" : "#FF0000",
        "color.hyperlink" : "#00FFFF",
        "color.userinput" : "#00FF00",
        "color.label" : "#FFFFFF",
        "color.highlight" : "#242480",
        "color.sectionbackground" : "#000008",
        "color.black" : "#000008",
        "color.grey" : "#CCCCCC",
        "color.red" : "#FF0000",
        "color.blue" : "#0000FF",
        "color.green" : "#00FF00",
        "color.cyan" : "#00FFFF",
        "color.yellow" : "#FFFF00",
        "color.magenta" : "#FF00FF",
        "ttktheme" : "clam",
        "commandfontsize" : None,
        "logfontsize" : None,
    })

def light_terminal_theme():
    return ShellTheme("light", {
        "color.message" : "#303030",
        "color.background" : "#F0F0F0",
        "color.insertmarker" : "#000000",
        "color.message-em" : "#8D0C0C",
        "color.warning" : "#991070",
        "color.error" : "#8D0C0C",
        "color.hyperlink" : "#3C96A6",
        "color.userinput" : "#6AAE08",
        "color.label" : "#000000",
        "color.highlight" : "#CCE8FF",
        "color.sectionbackground" : "#F0F0F0",
        "color.black" : "#000000",
        "color.grey" : "#6E386E",
        "color.red" : "#8D0C0C",
        "color.blue" : "#17b2ff",
        "color.green" : "#6AAE08",
        "color.cyan" : "#3C96A6",
        "color.yellow" : "#991070",
        "color.magenta" : "#991070",
        "ttktheme" : "clam",
        "commandfontsize" : None,
        "logfontsize" : None,
    })
    
def white_terminal_theme():
    return light_terminal_theme().extend("white-light", {
        "color.framebackground" : "#FFFFFF"
    })

    
def dark_blue_theme():
    return dark_classic_theme().extend("dark-blue", {
        "color.message-em" : "#00FFFF",
        "color.warning" : "#D9FF00",
        "color.error" : "#FF0080",
        "color.hyperlink" : "#00FFFF",
        "color.userinput" : "#00A0FF",
        "color.highlight" : "#0038A1", 
    })

def grey_green_theme():
    return dark_classic_theme().extend("grey-green", {
        "color.background" : "#E8FFE8",
        "color.insertmarker" : "#000000",
        "color.message" : "#000000",
        "color.message-em" : "#008000",
        "color.warning" : "#FF8000",
        "color.error" : "#FF0000",
        "color.hyperlink" : "#0000FF",
        "color.userinput" : "#00B070",
        "color.label" : "#000000",
        "color.highlight" : "#FFD0D0",
        "color.sectionbackground" : "#EFEFEF",
    })


def papilio_machaon_theme():
    return grey_green_theme().extend("papilio-machaon", {
        "color.background" : "#88FF88",
        "color.message-em" : "#FFA500",
        "color.message" : "#000000",
        "color.highlight" : "#FFA500",
        "color.sectionbackground" : "#B0FFB0",
        "color.inactivesectionbackground" : "#EFEFEF",
    })


theme_constructors = {
    "classic" : dark_classic_theme,
    "light" : light_terminal_theme,
    "dark-blue" : dark_blue_theme,
    "grey-green" : grey_green_theme,
    "papilio-machaon" : papilio_machaon_theme
}


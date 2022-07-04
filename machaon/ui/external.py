import os
import configparser
import subprocess
from machaon.platforms import shellpath

class ExternalAppEntry:
    def __init__(self, section):
        self.section = section

    def get(self, name, default=None):
        return self.section.get(name, default)   

    def has(self, name):
        return name in self.section 

    def execute(self, args):
        path = self.get("path")
        subprocess.Popen([path, *args], shell=False)


class ExternalApps:
    def __init__(self):
        self._extapps = None

    def load_applist(self, root):
        if self._extapps is None:
            p = root.get_external_applist()
            if os.path.isfile(p):
                cfg = configparser.ConfigParser()
                cfg.read(p)
                self._extapps = cfg
        return self._extapps
    
    def get_external_app(self, root, appname):
        applist = self.load_applist(root)
        if applist and applist.has_section(appname):
            return ExternalAppEntry(applist[appname])
        return None

    #
    #
    #
    def open_by_text_editor(self, root, filepath, line=None, column=None):
        """ テキストエディタ """
        editor = self.get_external_app(root, "text_editor")
        if editor is not None:
            args = []
            args.append(filepath)

            if line is not None and editor.has("line"):
                lineopt = editor.get("line").format(line)
                args.append(lineopt)
            
            if column is not None and editor.has("column"):
                charopt = editor.get("column").format(column)
                args.append(charopt)
        
            editor.execute(args)
        else:
            shellpath().open_by_system_text_editor(filepath, line, column)
    
import shutil
from machaon.types.shell import Path
from machaon.types.file import TextFile

from protenor.store.config import ConfigDef, ObjectConfig

siteConfig = ConfigDef({
    "*" : {
        "site_location" : None,
        "server_address": None,
        "server_directory": None,
    },
})

def writefile(p, configs):            
    TextFile(p, encoding="utf-8").write_text(configs.strip())


class ServerSettings:
    """ @type
    
    """
    def __init__(self, name=None, apiserver=None, apiserverdir=None, location=None):
        self.name = name
        self.site = None
        self.location = location
        self.serveraddress = apiserver
        self.serverdirectory = apiserverdir

    def load(self, root):
        """ コンフィグファイルから設定を読み込む """
        if self.name is None:
            raise ValueError("name")
        cfg = ObjectConfig(siteConfig)
        cfg.loadvalue(root.get_local_config("bianor", "site.cfg"))        
        
        if not cfg.has_section(self.name):
            raise ValueError("'{}'はsite.cfgの中に存在しません".format(self.name))
        self.location = cfg.get(self.name + "/site_location")
        self.serveraddress = cfg.get(self.name + "/server_address")
        self.serverdirectory = cfg.get(self.name + "/server_directory")
        
        if self.name == "v1":
            self.site = "v1"
        elif self.name == "v2":
            self.site = "v2/dist"
        else:
            raise ValueError("無効なサイト名：{}".format(self.name))

    def deploy(self, app):
        """ @task
        指定の場所にサイトのファイルを生成して配置する
        """
        if self.site is None:
            self.load(app.get_root())
        if self.site is None or self.location is None:
            raise ValueError("サイト名またはIPアドレスが不明です")

        # サイトのファイルをコピーする
        thisdir = Path(__file__).dir()
        src = thisdir / self.site
        if not src.exists():
            raise ValueError("サイトのソースディレクトリ'{}'が存在しません".format(src))
        dest = Path(self.location)
        if dest.exists():
            dest.rmtree()  # 元ディレクトリを削除する
        shutil.copytree(src, dest)

        # 設定スクリプトを書き込む
        if self.serveraddress is not None:
            apiserver = self.serveraddress
            if "://" not in apiserver:
                apiserver = "http://" + apiserver
            apiserver = apiserver.rstrip("/")
            writefile(dest / "config.js", """
            var API_SERVER_URL = '{}';
            """.format(apiserver))

        # サーバー起動の設定ファイルとスクリプトを書き込む
        if self.serverdirectory is not None:
            cfgdir = Path(self.serverdirectory).makedirs() # 元ディレクトリは削除しない 
            writefile(cfgdir / "start.sh",
            "#!/bin/sh" "\n"
            "/opt/bin/uwsgi {}/uwsgi.ini".format(cfgdir)
            )
            writefile(cfgdir / "reload.sh",
            "#!/bin/sh" "\n"
            "/opt/bin/uwsgi --reload {}/uwsgi.pid".format(cfgdir)
            )
            writefile(cfgdir / "stop.sh",
            "#!/bin/sh" "\n"
            "/opt/bin/uwsgi --stop {}/uwsgi.pid".format(cfgdir)
            )
            uwsgi = cfgdir / "uwsgi.ini"
            if not uwsgi.exists():
                configs = TextFile(thisdir / "uwsgi.ini", encoding="utf-8").text()
                head, sep, address = apiserver.partition("://")
                if not sep:
                    address = head
                configs = configs.format(address=address, dir=cfgdir.get())
                writefile(uwsgi, configs)
        
    def constructor(self, name):
        """ @meta
        Params:
            name(str):
        """
        return ServerSettings(name=name)

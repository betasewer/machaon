
from typing import Mapping, TYPE_CHECKING
import shutil

from machaon.types.shell import Path
from machaon.types.file import TextFile
from machaon.package.package import PackageFilePath

if TYPE_CHECKING:
    from machaon.app import AppRoot
    from machaon.process import Spirit


#
#
#
class ComponentName:
    """ コンポーネント名 """
    def __init__(self, name: str, config: str):
        self.name = name
        self.configname = config
    
    def resolve_config_filepathes(self, d: Path):
        return resolve_config_filepathes(d, self.configname)

    @classmethod
    def parse(cls, s: str, *, here=None):
        name, sep, file = s.partition(":")
        if not sep:
            if here is None:
                raise ComponentNameError("'{}': コンポーネントセット名を指定してください".format(s))
            return cls(name, here)
        else:
            return cls(name, file)
        
    def stringify(self):
        if self.configname is None:
            return self.name
        else:
            return "{}:{}".format(self.name, self.configname)
        

#
class ComponentSet:
    def __init__(self, name: str, compos: list['Component']):
        self.name = name
        self.grp: list[Component] = [*compos]

    def add(self, compo: 'Component'):
        self.grp.append(compo)

    def get(self, name: str):
        for c in self.grp:
            if c.name.name == name:
                return c
        else:
            raise ComponentNameError(ComponentName(name, self.name).stringify())

    def getall(self):
        return self.grp


class ComponentNameError(Exception):
    pass


class ComponentConfigError(Exception):
    pass


def writefile(p, configs: str):            
    TextFile(p, encoding="utf-8").write_text(configs.strip())

def readfile(p: Path) -> str:
    return TextFile(p, encoding="utf-8").text()


PREFIX_DELIMITER = ":"

class Component:
    def __init__(self, name, config):
        self.name: ComponentName = name
        self.config: Mapping[str, str] = config

    def this_component_set(self, app: 'AppRoot'):
        return app.server_components().load(self.name.configname)

    def value(self, key):
        if key not in self.config:
            raise ComponentConfigError("フィールド'{}'は必須です".format(key))
        return self.config[key]
    
    def prefixed_values(self, prefix: str):
        keys = [k for k in self.config.keys() if k.startswith(prefix + PREFIX_DELIMITER)]
        if prefix in self.config:
            keys.append(prefix)
        if not keys:
            raise ComponentConfigError("フィールド'{}'は必須です".format(prefix))
        values = [(x.partition(PREFIX_DELIMITER)[2], self.config[x]) for x in keys]
        return values
    
    def get_this_port(self):
        return self.value("port")
    
    def get_this_url(self):
        protocol = "http"
        return "{}://127.0.0.1:{}".format(protocol, self.get_this_port())
    
    def url_value(self, app: 'AppRoot', value: str):
        if value.startswith(("http://", "https://")):
            return value
        else:
            return self.this_component_set(app).get(value).get_this_url()
        
    def load_package_file(self, app: 'AppRoot', uri:str) -> Path:
        """ パッケージのファイルを取得する """
        p = PackageFilePath.parse(uri)
        pkgm = app.package_manager()
        pkg = pkgm.get(p.package)
        if not pkgm.is_installed(pkg):
            raise ComponentConfigError("'{}': パッケージ'{}'のインストールが必要です".format(self.name.stringify(), pkg.name))
        pkgdir = pkgm.get_installed_location(pkg)
        return pkgdir / p.path

    #
    def deploy(self, app: 'Spirit', *, force=False):
        raise NotImplementedError()


class SiteComponent(Component):
    def get_files(self, app: 'AppRoot') -> Path:
        return self.load_package_file(app, self.value("files"))
    
    def get_servers(self, app: 'AppRoot'):
        servers = {}
        for subkey, value in self.prefixed_values("server"):
            server_name = "{}_SERVER".format(subkey.upper()) if subkey else "SERVER"
            url = self.url_value(app, value)
            servers[server_name] = {
                "url": url
            }
        return servers

    def deploy(self, spi: 'Spirit', *, force=False):
        app = spi.get_root()

        # サイトのファイルをコピーする
        spi.post("message", "サイトのファイルをコピー")
        src = self.get_files(app)
        if not src.exists():
            raise ValueError("サイトのソースディレクトリ'{}'が存在しません".format(src))
        
        dest = Path(self.value("dest"))
        if dest.exists():
            dest.rmtree()  # 元ディレクトリを削除する

        shutil.copytree(src, dest)

        # 設定情報スクリプトを作る
        lines = []
        for server_name, server in self.get_servers(app).items():
            line = "var {}_URL = '{}'".format(server_name, server["url"].rstrip("/"))
            lines.append(line)
        if lines:
            spi.post("message", "サーバー設定ファイルを書き込み")
            writefile(dest / "config.js", "\n".join(lines))


class UwsgiComponent(Component):
    def deploy(self, spi: 'Spirit', *, force=False):
        app = spi.get_root()
        # スクリプトをコピーする
        spi.post("message", "操作スクリプトを生成")
        dest = Path(self.value("dest"))
        if force:
            dest.rmtree()  # 元ディレクトリを削除する
        dest.makedirs() 

        uwsgi = self.value("uwsgi")
        writefile(dest / "start.sh",
            "#!/bin/sh" "\n"
            "{} {}/uwsgi.ini".format(uwsgi, dest)
        )
        writefile(dest / "reload.sh",
            "#!/bin/sh" "\n"
            "{} --reload {}/uwsgi.pid".format(uwsgi, dest)
        )
        writefile(dest / "stop.sh",
            "#!/bin/sh" "\n"
            "{} --stop {}/uwsgi.pid".format(uwsgi, dest)
        )

        # 設定ファイルを書き込む
        spi.post("message", "設定ファイルを生成")
        uwsgi_cfg = dest / "uwsgi.ini"
        if force or not uwsgi_cfg.exists():
            configs = readfile(self.load_package_file(app, self.value("config")))
            address = self.get_this_url()
            configs = configs.format(address=address, dir=dest.get(), logdir=self.value("log_dest"))
            writefile(uwsgi_cfg, configs)





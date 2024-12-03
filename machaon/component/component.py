
from typing import Mapping, TYPE_CHECKING
import shutil

from machaon.types.shell import Path
from machaon.types.file import TextFile
from machaon.package.package import PackageFilePath
from machaon.core.importer import module_loader

from machaon.component.file import FSTransaction, readfile, readtemplate

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


#
#
#
PREFIX_DELIMITER = ":"

class Component:
    def __init__(self, name, config):
        self.name: ComponentName = name
        self.config: Mapping[str, str] = config

    def this_component_set(self, app: 'AppRoot'):
        return app.server_components().load(self.name.configname)

    def value(self, key, default=...):
        if key not in self.config:
            if default is ...:
                raise ComponentConfigError("フィールド'{}'は必須です".format(key))
            else:
                return default
        return self.config[key]
    
    def prefixed_values(self, prefix: str):
        keys = [k for k in self.config.keys() if k.startswith(prefix + PREFIX_DELIMITER)]
        if prefix in self.config:
            keys.append(prefix)
        if not keys:
            raise ComponentConfigError("フィールド'{}'は必須です".format(prefix))
        values = [(x.partition(PREFIX_DELIMITER)[2], self.config[x]) for x in keys]
        return values
    
    def package_file(self, key, default=...):
        return PackageFilePath.parse(self.value(key, default))
    
    #
    def get_this_port(self):
        return self.value("port")
    
    def get_this_url(self, *, protocol=True):
        addr = self.value("url", "http://127.0.0.1").rstrip("/")
        addr = "{}:{}".format(addr, self.get_this_port())
        if protocol:
            return addr
        else:
            _, sep, rest = addr.partition("://")
            return rest
    
    def url_value(self, app: 'AppRoot', value: str):
        if value.startswith(("http://", "https://")):
            return value
        else:
            return self.this_component_set(app).get(value).get_this_url()
        
    def load_package_item(self, app: 'AppRoot', path: PackageFilePath):
        pkgm = app.package_manager()
        pkgit = pkgm.get_item(path, fallback=True)
        if pkgit is None:
            raise ComponentConfigError("'{}': パッケージ'{}'の定義がありません".format(self.name.stringify(), path.package))
        if not pkgm.is_installed(pkgit.package):
            raise ComponentConfigError("'{}': パッケージ'{}'のインストールが必要です".format(self.name.stringify(), path.package))
        return pkgit
    
    def load_package_item_path(self, app: 'AppRoot', path: PackageFilePath):
        item = self.load_package_item(app, path)
        return app.package_manager().get_item_path(item)

    #
    def deploy(self, app: 'Spirit', *, force=False) -> FSTransaction:
        raise NotImplementedError()


class SiteComponent(Component):
    def get_files(self, app: 'AppRoot') -> Path:
        return self.load_package_item_path(app, self.package_file("files"))
    
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
        fs = FSTransaction()

        # サイトのファイルをコピーする
        spi.post("message", "サイトのファイルをコピー")
        src = self.get_files(app)
        if not src.exists():
            raise ValueError("サイトのソースディレクトリ'{}'が存在しません".format(src))
        
        dest_required = self.value("dest_required", None)
        if dest_required is not None:
            dest_required = Path(dest_required)
            if not dest_required.isdir():
                raise ValueError("コピー先パスの必須部分'{}'が存在しません。手動で作成してください".format(dest_required))
        
        dest = Path(self.value("dest"))
        fs.treecopy_to(dest).dest_required(dest_required).copy(src)

        # 設定情報スクリプトを作る
        lines = []
        tr = fs.filewrite_to(dest)
        for server_name, server in self.get_servers(app).items():
            line = "var {}_URL = '{}'".format(server_name, server["url"].rstrip("/"))
            lines.append(line)
        if lines:
            spi.post("message", "サーバー設定ファイルを書き込み")
            tr.write("config.js", "\n".join(lines))

        return fs


class UwsgiComponent(Component):
    def deploy(self, spi: 'Spirit', *, force=False):
        app = spi.get_root()
        fs = FSTransaction()

        # 操作スクリプトを生成する
        spi.post("message", "操作スクリプトを生成")
        dest = Path(self.value("dest"))
        tr = fs.filewrite_to(dest)
        if force:
            tr.clean(True) # 元ディレクトリを削除する

        uwsgi = self.value("uwsgi")
        tr.write("start.sh", # 常に上書きする
            "#!/bin/sh" "\n"
            "{} {}/uwsgi.ini".format(uwsgi, dest)
        )
        tr.write("reload.sh",
            "#!/bin/sh" "\n"
            "{} --reload {}/uwsgi.pid".format(uwsgi, dest)
        )
        tr.write("stop.sh",
            "#!/bin/sh" "\n"
            "{} --stop {}/uwsgi.pid".format(uwsgi, dest)
        )

        filesdir = self.load_package_item(app, self.package_file("files"))

        # エントリポイントを書き込む
        spi.post("message", "Pythonのエントリポイントを生成")
        pyentry = self.value("entrypoint", "entrypoint.py") 
        if force or not tr.fileexists(pyentry): # 上書きしない
            # 参照モジュールを検証する
            entrymodule = module_loader(filesdir.join("entrypoint.py").as_module_name())
            if not entrymodule.exists():
                raise ComponentConfigError("'{}': モジュール'{}'は存在しません".format(self.name.stringify(), entrymodule.get_name()))
            if entrymodule.load_attr("wsgi", fallback=True) is None:
                spi.post("warn", "'{}': モジュール'{}'にエントリポイント{}()が確認できませんでした".format(self.name.stringify(), entrymodule.get_name(), "wsgi"))
            # スクリプトを生成する
            pyentrycode = readtemplate("wsgi_entrypoint").format(
                entrymodule=entrymodule.get_name(),
                dir=app.get_basic_dir().get(), # 同じmachaon環境を参照する
                title=self.value("title", "{}_server".format(self.name.stringify()))
            )
            tr.write(pyentry, pyentrycode)

        # 設定ファイルを書き込む
        spi.post("message", "uwsgi設定ファイルを生成")
        if force or not tr.fileexists("uwsgi.ini"): # 上書きしない
            src_uwsgi_cfg = app.package_manager().get_item_path(filesdir.join("uwsgi.ini"))
            if not src_uwsgi_cfg.isfile():
                raise ComponentConfigError("'{}': {}は存在しません".format(self.name.stringify(), src_uwsgi_cfg))
            configs = readfile(src_uwsgi_cfg)
            address = self.get_this_url(protocol=False)
            configs = configs.format(address=address, dir=dest.get(), logdir=self.value("log_dest"), wsgifile=pyentry)
            tr.write("uwsgi.ini", configs)

        # ログディレクトリを作成する
        fs.pathensure(Path(self.value("log_dest"))) #.clean(force)

        return fs





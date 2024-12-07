
import configparser
from typing import Mapping, TYPE_CHECKING
import shutil

from machaon.types.shell import Path
from machaon.types.file import TextFile

if TYPE_CHECKING:
    from machaon.app import AppRoot

from machaon.component.component import (
    Component, ComponentName, 
    ComponentNameError, ComponentConfigError,
    ComponentSet
)


#
def resolve_config_filepathes(d: Path, name: str):
    if name.startswith("/"):
        return [Path(name[len("/"):])]
    else:
        return [d / x for x in (
            name + ".ini", 
            name + ".components", 
            name + ".components.ini", 
        )]


class ComponentManager:
    def __init__(self, directory: Path):
        self.d = directory
        self.compos: Mapping[str, ComponentSet] = {}

    def _load_config(self, path: Path, configs: configparser.ConfigParser):
        """ ファイルを読み込む """
        if not path.isfile():
            raise FileNotFoundError(path)
        # ファイルを読み込む
        with TextFile(path, encoding="utf-8").read_stream() as fi:
            configs.read_file(fi.stream)

    def _make_component(self, cname: ComponentName, cfg: Mapping[str, str]):
        compo_type = cfg.get("type", fallback=None)
        if compo_type is None:
            if "uwsgi" in cfg:
                compo_type = "uwsgi"
        if compo_type is None:
            raise ComponentConfigError("'{}': 'type'フィールドは必須です".format(cname.stringify()))

        if compo_type == "site":
            from machaon.component.component import SiteComponent
            return SiteComponent(cname, cfg)
        elif compo_type == "uwsgi":
            from machaon.component.component import UwsgiComponent
            return UwsgiComponent(cname, cfg)
        else:
            raise ComponentConfigError("'type'フィールドの値'{}'は不明な値です".format(compo_type))

    def load(self, setname: str):
        """ ファイルに定義されたコンポーネントセットを読み込む """
        if setname in self.compos:
            return self.compos[setname]
        
        cfg = configparser.ConfigParser()
        for p in resolve_config_filepathes(self.d, setname):
            if not p.isfile():
                continue
            self._load_config(p, cfg)
            break
        else:
            raise ComponentNameError("コンポーネントセット'{}'の定義ファイルが見つかりません".format(setname))
        
        cs = ComponentSet(setname, [])
        for k, v in cfg.items():
            if k == cfg.default_section:
                continue
            cname = ComponentName(k, setname)
            c = self._make_component(cname, v)
            cs.add(c)

        self.compos[setname] = cs
        return cs
    
    def load_component(self, cname: ComponentName):
        """ コンポーネント一つを読み込む """
        cset = self.load(cname.configname)
        return cset.get(cname.name)

        
        
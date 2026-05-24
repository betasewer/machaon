from typing import Mapping, Any, Optional
import configparser
import os

from ..core.error import ErrorSet
from ..types.shell import Path
from ..types.configproto import ConfigProto, ValueProto, VALUE_PATH_SEP


class ConfigClass:
    def __init__(self, name, definition=None):
        self._name = name
        self._defs: dict[str, dict[str, Any]] = definition or {}
        self._primal_proto = ConfigProto.build_from_class(self)

    @property
    def name(self):
        return self._name

    def get_defs(self):
        return self._defs
    
    def new_proto(self):
        """ プロトタイプをコピーして初期化する """
        return self._primal_proto.clone()
    
    def new(self, v=None):
        """ 設定オブジェクトを作成する """
        cfg = configparser.ConfigParser()
        if v is None:
            proto = self.new_proto()
            proto.set_default_values_to(cfg) # デフォルト値をセットする
        else:
            cfg.read_dict(v)
            proto = self.new_proto()
            proto.validate(cfg, set_default=True)
        return Config(cfg, proto)

    def load_file(self, path: 'Path'):
        """ ファイルから設定内容を読みだす """
        cfg = configparser.ConfigParser()
        with open(path, "r", encoding="utf-8") as fi:
            cfg.read_file(fi)
        proto = self.new_proto()
        proto.validate(cfg, set_default=True)
        return Config(cfg, proto)

    def write_file(self, cfg: 'Config', path: 'Path'):
        """ 設定内容をファイルに書きだす """
        if not cfg.is_loaded():
            raise ValueError("設定内容がロードされていません")
        vcfg = cfg.config
        cfg.get_proto().validate(vcfg, set_default=True) # 書きだす前に、値のチェックを行う
        with open(path, "w", encoding="utf-8") as fo:
            vcfg.write(fo)


def split_section_and_key(section_and_key: str, key: str|None = None):
    if key is None:
        section, sep, valkey = section_and_key.partition(VALUE_PATH_SEP)
        if not sep:
            raise ValueError(section_and_key)
    else:
        section, valkey = section_and_key, key
    return section, valkey


#
#
#
class Config:
    def __init__(self, cfg:configparser.ConfigParser, proto: ConfigProto):
        self._cfg = cfg
        self._proto: ConfigProto = proto

    def get_proto(self):
        return self._proto

    def get_value_proto(self, section_key: str, value_key: str):
        return self._proto.get(section_key, value_key)
    
    def is_loaded(self):
        return self._cfg is not None
    
    def write_file(self, path: 'Path'):
        self._proto.klass.write_file(self, path)
    
    @property
    def config(self):
        return self._cfg

    def has(self, section):
        return self._cfg.has_section(section)
    
    def get_value(self, section_and_key: str, key: str|None = None):
        """ 値を取り出す """
        # キーを分割する
        section, valkey = split_section_and_key(section_and_key, key)
        # 値を取り出す
        return self._proto.get_value_of(self._cfg, section, valkey)
    
    def set_value(self, section_and_key: str, value: Any, *, key: str|None = None):
        """ 値をセットする """
        # キーを分割する
        section, valkey = split_section_and_key(section_and_key, key)
        # 値をセットする
        valproto = self._proto.select_value_proto(section, valkey) # プロトタイプが無ければ、ここで作成される
        if valproto is None:
            raise ValueError("このキーには値の定義がありません：{}{}{}".format(section, VALUE_PATH_SEP, valkey))
        valproto.set_value_to(self._cfg, value)

    def section(self, section_name):
        """ 
        セクションにアクセスするプロクシオブジェクトを取り出す 
        定義されていないセクションに対してはエラーを発生させる
        """
        if not self._proto.is_defined_section(section_name):
            raise ValueError("このセクションは定義されていません：{}".format(section_name))
        return ConfigSection(self, section_name)
    
    def keys(self):
        """ セクション名のリストを取得する """
        return self._proto.section_names()
    
    def values(self):
        """ セクションオブジェクトのリストを取得する """
        for section_name in self._proto.section_names():
            if section_name in self._cfg:
                yield self.section(section_name)

    def items(self):
        """ セクション名とセクションオブジェクトのペアのリストを取得する """
        for section_name in self._proto.section_names():
            if section_name in self._cfg:
                yield section_name, self.section(section_name)

    def sections(self, category: str|None=None):
        """ 指定されたカテゴリのセクションオブジェクトを取得する """
        for section_name in self._proto.section_names(category=category):
            if section_name in self._cfg:
                yield self.section(section_name)

    def category_values(self, category: str):
        """ 指定されたカテゴリのセクションと値を取得する """
        for section_name, protos in self._proto.values_of_category(category):
            if section_name in self._cfg:
                values: dict[str, Any] = {}
                for proto in protos:
                    values[proto.value_key] = proto.get_value_of(self._cfg)
                yield self.section(section_name), values

    def remove(self, section_name):
        """ セクションを削除する """
        # セクションの値を削除する
        self._cfg.remove_section(section_name)

        # セクションが可変セクションとして定義されているなら、定義も削除する
        sect = ConfigSection(self, section_name)
        if not sect.is_variable:
            return
        for valkey in self.keys_of_section(section_name):
            self._proto.remove(section_name, valkey)

    def keys_of_section(self, section_name):
        """ セクション内のキーのリストを取得する """
        for v in self._proto.values_of_section(section_name): # プロトタイプを調べる
            yield v.value_key

    def __len__(self):
        return len(self._cfg)
    
    def __contains__(self, item):
        return item in self._cfg
    
    def __getitem__(self, key):
        return self.section(key)


class ConfigSection:
    def __init__(self, cfg: Config, key: str):
        self._key = key
        self._cfg = cfg

    def get_proto(self, name):
        """ 値のプロトタイプを取り出す """
        return self._cfg.get_value_proto(self._key, name)
    
    @property
    def key(self):
        return self._key
    
    @property
    def category(self):
        proto = next(self._cfg.get_proto().values_of_section(self._key), None)
        return proto.category if proto is not None else None
    
    @property
    def name(self):
        proto = next(self._cfg.get_proto().values_of_section(self._key), None)
        if proto is not None and proto.subname is not None:
            return proto.subname
        return self._key
    
    @property
    def is_variable(self):
        return self.category is not None

    def get(self, key: str):
        return self._cfg.get_value(self._key, key)
    
    def set(self, key: str, value: Any):
        self._cfg.set_value(self._key, value, key=key)
    
    def keys(self):
        return self._cfg.keys_of_section(self._key)
    
    def values(self):
        for key in self.keys():
            yield self._cfg.get_value(self._key, key)
    
    def items(self):
        for key in self.keys():
            yield key, self._cfg.get_value(self._key, key)

    def __len__(self):
        return len(list(self.keys()))
    
    def __contains__(self, key):
        return key in self.keys()
    
    def __getitem__(self, key):
        return self.get(key)


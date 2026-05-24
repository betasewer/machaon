"""
プロトタイプ
"""
from typing import TYPE_CHECKING, Iterable, Any
import configparser
import datetime

if TYPE_CHECKING:
    from ..types.config import ConfigClass

from ..core.error import ErrorSet

def _parse_member_name(k: str):
    """
    メンバ名の表示を分析する
    """
    required = True if "*" not in k else False # ワイルドカードがあれば、必須ではない
    if k.endswith("?"):
        k = k[:-1]
        required = False
    return k, required    

VALUE_PATH_SEP = "/"
DEFAULT_STR = ""

class ValueProto:
    def __init__(self,
        section_key: str,
        value_key: str,
        type: str,
        default: Any,
        category: str|None,
        subname: str|None,
        required: bool
        ):
        self.section_key = section_key
        self.value_key = value_key
        self.type = type
        self.default = default
        self.category = category
        self.subname = subname
        self.required = required

    @property
    def fullpath(self):
        return VALUE_PATH_SEP.join([self.section_key, self.value_key])

    @classmethod
    def build_from_class(cls, section_key: str, value_key: str, defv: Any, required=False):        
        defvtype = defv
        if defvtype is None or defvtype is str:
            t = "s"
            dft = ""
        elif defvtype is bool:
            t = "b"
            dft = False
        elif defvtype is int:
            t = "i"
            dft = 0
        elif defvtype is float:
            t = "f"
            dft = 0.0
        elif defvtype is datetime.date:
            t = "d"
            dft = None
        elif defvtype is datetime.datetime:
            t = "t"
            dft = None
        else:
            raise ValueError(defvtype)
        
        proto = cls(
            section_key, 
            value_key,
            type=t, 
            default=dft,
            required=required,
            category=None,
            subname=None
        )
        return proto
    
    def check_value_exists(self, cfg: configparser.ConfigParser):
        """ 値が存在するかどうか """
        return cfg.has_option(self.section_key, self.value_key)
    
    def get_raw_value_of(self, cfg: configparser.ConfigParser):
        """ コンフィグオブジェクトから値を取り出す。型変換は行わない """
        return cfg.get(self.section_key, self.value_key, fallback=DEFAULT_STR)
    
    def get_value_of(self, cfg: configparser.ConfigParser):
        """ コンフィグオブジェクトから値を取り出す。型変換も行う """
        v = self.get_raw_value_of(cfg)
        if v == DEFAULT_STR: # 空文字列は、デフォルト値に変換する
            return self.default
        if self.type == "s":
            return v
        elif self.type == "b":
            v = v.lower()
            if v not in configparser.ConfigParser.BOOLEAN_STATES:
                raise ValueError(v)
            return configparser.ConfigParser.BOOLEAN_STATES[v]
        elif self.type == "i":
            iv = int(v)
            return iv
        elif self.type == "f":
            fv = float(v)
            return fv
        elif self.type == "d":
            d = datetime.date.fromisoformat(v)
            return d
        elif self.type == "t":            
            dt = datetime.datetime.fromisoformat(v)
            return dt
        else:
            raise ValueError(self.type)
        
    def set_value_to(self, cfg: configparser.ConfigParser, value: Any):
        """ コンフィグオブジェクトに値をセットする """
        # すべての値を文字列化する
        if value is None:
            s = DEFAULT_STR # Noneは空文字列にする
        elif self.type == "s":
            s = value
        elif self.type == "b":
            if not isinstance(value, bool):
                raise ValueError("{}/{}: ブール値が必要です".format(self.section_key, self.value_key))
            s = "true" if value else "false"
        elif self.type == "i":
            if not isinstance(value, int):
                raise ValueError("{}/{}: 整数値が必要です".format(self.section_key, self.value_key))
            s = str(value)
        elif self.type == "f":
            if not isinstance(value, (int, float)):
                raise ValueError("{}/{}: 浮動小数点数値が必要です".format(self.section_key, self.value_key))
            s = str(value)
        elif self.type == "d":
            if not isinstance(value, datetime.date):
                raise ValueError("{}/{}: 日付型の値が必要です".format(self.section_key, self.value_key))
            s = value.isoformat()
        elif self.type == "t":
            if not isinstance(value, datetime.datetime):
                raise ValueError("{}/{}: 日付時刻型の値が必要です".format(self.section_key, self.value_key))
            s = value.isoformat()
        else:
            raise ValueError(self.type)
        
        if self.section_key not in cfg:
            cfg.add_section(self.section_key)
        cfg.set(self.section_key, self.value_key, s)

    def set_default_value_to(self, cfg: configparser.ConfigParser):
        """ デフォルト値をコンフィグオブジェクトにセットする """
        self.set_value_to(cfg, self.default)
        
    def spawn(self, section_key: str, category: str|None, subname: str|None, value_key: str):
        """ 新たなプロトタイプインスタンスを生成する """
        return ValueProto(
            section_key=section_key,
            value_key=value_key,
            type=self.type,
            default=self.default,
            category=category,
            subname=subname,
            required=self.required
        )

    def validate(self, cfg: configparser.ConfigParser, errors: ErrorSet):
        """ 値の型を検査する。 """
        if self.type == "s":
            return
        
        # 値が型変換できるか実演する
        try:
            self.get_value_of(cfg)
        except ValueError:
            typedesc = {
                "b": "ブール値",
                "i": "整数値",
                "f": "浮動小数点数値",
                "d": "日付型の値",
                "t": "日付時刻型の値"
            }[self.type]
            errors.addv("'{}/{}'の値'{}'は{}として不正です".format(
                self.section_key, 
                self.value_key, 
                self.get_raw_value_of(cfg), 
                typedesc
            ))


class ProtoMemberSet:
    def __init__(self, 
            name_matcher: 'CategoryMembers | AnyMembers',
            required: bool
        ):
        self.name_matcher = name_matcher
        self.required = required
        self.values: list[ValueProto] = []

    def add(self, proto: ValueProto):
        self.values.append(proto)

    def match_name(self, section_name: str):
        """ セクション名にマッチするかどうか """
        return self.name_matcher.match(section_name) is not None

    def spawn_proto(self, section_name: str, value_key: str):
        """ プロトタイプのインスタンスを一つ生成する """
        res = self.name_matcher.match(section_name)
        if res is None:
            return None
        section_key, category, subname = res
        protox = next((x for x in self.values if x.value_key == value_key), None)
        if protox is None:
            return None
        return protox.spawn(section_key, category, subname, value_key)

    def spawn_proto_all(self, section_name: str) -> list[ValueProto]:
        """ 定義されたプロトタイプのインスタンスをすべて生成する """
        res = self.name_matcher.match(section_name)
        if res is None:
            return []
        protos = []
        section_key, category, subname = res
        for proto in self.values:
            proto = proto.spawn(section_key, category, subname, proto.value_key)
            protos.append(proto)
        return protos
    
    def set_default_values_to(self, cfg: configparser.ConfigParser):
        """ デフォルト値をコンフィグオブジェクトにセットする """
        for proto in self.values:
            proto.set_default_value_to(cfg)


class ConfigProto:
    def __init__(self, klass):
        self.klass: 'ConfigClass' = klass
        self._values: dict[str, ValueProto] = {}
        self._memberset: dict[str, ProtoMemberSet] = {}

    def get(self, fullpath_or_section_key: str, value_key: str|None = None):
        """ パスに対応する値のプロトタイプを返す """
        if value_key is not None:
            fullpath = VALUE_PATH_SEP.join([fullpath_or_section_key, value_key])
        else:
            fullpath = fullpath_or_section_key
        return self._values.get(fullpath, None)
 
    @classmethod
    def build_from_class(cls, klass: 'ConfigClass'):
        """ コンフィグ定義クラスからプロトタイプを作成する """
        root = cls(klass)
        for defsectname, defsec in klass.get_defs().items():
            defsectname, required = _parse_member_name(defsectname)
            memberset = parse_wildcard_name(defsectname)
            if memberset is not None:
                # 動的な属性の集合
                protoset = root._memberset[defsectname] = ProtoMemberSet(memberset, required=required)
                for defkey, defval in defsec.items():
                    defkey, required = _parse_member_name(defkey)
                    # 値のプロトタイプを作成して保存する
                    proto = ValueProto.build_from_class(defsectname, defkey, defval, required=required)
                    protoset.add(proto)
            else:
                # 静的な属性定義
                for defkey, defval in defsec.items():
                    defkey, required = _parse_member_name(defkey)
                    # 値のプロトタイプを作成して保存する
                    proto = ValueProto.build_from_class(defsectname, defkey, defval, required=required)
                    root._values[proto.fullpath] = proto
        return root
    
    def clone(self):
        """ プロトタイプをコピーして初期化する """
        newproto = ConfigProto(self.klass)
        newproto._values = self._values.copy()
        newproto._memberset = self._memberset # クラス定義時に決定するので、使いまわせる
        return newproto
    
    def validate(self, cfg: configparser.ConfigParser, *, set_default=False):
        """ コンフィグインスタンスを検証する """
        errors = ErrorSet("設定[{}]の内容に誤りがあります".format(self.klass.name))
        self.validate_values(cfg, errors, set_default=set_default)
        if errors.failed():
            raise errors.error()

    def validate_values(self, cfg: configparser.ConfigParser, errors: ErrorSet, *, set_default=False):
        """ ルートセクションを検証する """
        checked_sections = set()

        # 定義済みの値について検査する
        for valproto in self._values.values():
            if not valproto.check_value_exists(cfg):
                if valproto.required:
                    if set_default:
                        valproto.set_default_value_to(cfg)
                    else:
                        errors.addv("必須の値'{}'が定義されていません".format(valproto.fullpath))
            else:
                valproto.validate(cfg, errors)
            # 検査済みの値を削除する
            checked_sections.add(valproto.section_key)
        
        # 動的な属性を検査し、プロトタイプを追加する
        if len(self._memberset) == 0:
            return
        for defsectname, memberset in self._memberset.items():
            matched_count = 0
            for section_name in cfg.sections():
                if not memberset.match_name(section_name):
                    continue
                # パターンにマッチするセクション
                matched_count += 1
                if section_name in checked_sections:
                    continue
                # プロトタイプのインスタンスを生成する
                protos = memberset.spawn_proto_all(section_name)
                if not protos:
                    continue
                for proto in protos:
                    if proto.fullpath not in self._values:
                        self._values[proto.fullpath] = proto # 定義済みになる
                    proto.validate(cfg, errors) # 値の検査を行う
                checked_sections.add(section_name)

            if matched_count == 0 and memberset.required:
                if set_default:
                    memberset.set_default_values_to(cfg)
                else:
                    errors.addv("必須のセクション'{}'が一つも定義されていません".format(defsectname))

        # 余分なセクションがあれば、エラーにする
        unchecked_sections = set(cfg.sections()) - checked_sections
        if unchecked_sections:
            errors.addv("不明なセクションが定義されています：{}".format(", ".join(unchecked_sections)))

    def get_value_of(self, cfg: configparser.ConfigParser, section_key: str, value_key: str):
        """ コンフィグオブジェクトから値を取り出す """
        # プロトタイプを探す
        valproto = self.select_value_proto(section_key, value_key)
        if valproto is not None:
            return valproto.get_value_of(cfg)
        # 見つからなければ、値をそのまま返す
        return cfg.get(section_key, value_key, fallback=None)

    def select_value_proto(self, section_key: str, value_key: str):
        """ 追加前のセクションのプロトタイプを構築する """
        fullpath = VALUE_PATH_SEP.join([section_key, value_key])
        if fullpath in self._values:
            return self._values[fullpath]
        for memset in self._memberset.values():
            proto = memset.spawn_proto(section_key, value_key)
            if proto is not None:
                self._values[fullpath] = proto
                return proto
        return None
    
    def is_defined_section(self, section_key: str):
        """ セクションが定義されているかを確認する """
        for v in self._values.values():
            if v.section_key == section_key:
                return True
        for memset in self._memberset.values():
            if memset.match_name(section_key):
                return True
        return False

    def section_names(self, category: str|None=None):
        """ 定義されている値のフルパスのリストを取得する """
        names: set[str] = set()
        for v in self._values.values():
            if category is None or v.category == category:
                if v.section_key not in names:
                    yield v.section_key
                    names.add(v.section_key)
    
    def values_of_section(self, section_key: str):
        """ セクションに合致する値のプロトタイプを取得する """
        for v in self._values.values():
            if v.section_key == section_key:
                yield v 

    def values_of_category(self, category: str):
        """ カテゴリに合致する値のプロトタイプを取得する """
        entries: dict[str, list[ValueProto]] = {}
        for v in self._values.values():
            if v.category == category:
                if v.section_key not in entries:
                    entries[v.section_key] = []
                entries[v.section_key].append(v)
        for section_key, protos in entries.items():
            yield section_key, protos
            
    def set_default_values_to(self, cfg: configparser.ConfigParser):
        """ 全てのデフォルト値をセットする """
        for valueproto in self._values.values():
            valueproto.set_default_value_to(cfg)

    def remove(self, section_key: str, value_key: str):
        """ 値を削除する """
        fullpath = VALUE_PATH_SEP.join([section_key, value_key])
        if fullpath in self._values:
            del self._values[fullpath]


#
# ワイルドカード付きのセクション名・キー名にマッチする
#
MemberName = tuple[str, str|None, str] # (key, category, name)


class CategoryMembers:
    """ 接頭辞が一致するセクション名にマッチする """
    def __init__(self, prefix: str):
        self.prefix = prefix

    def match(self, name: str) -> MemberName | None:
        if not name.startswith(self.prefix):
            return None
        category = self.prefix.rstrip(".")
        item = name[len(self.prefix):].strip()
        return name, category, item

class AnyMembers:
    """ 下にあるすべてのセクションにマッチする """
    def match(self, name: str) -> MemberName | None:
        return name, None, name
    

def parse_wildcard_name(key: str):
    """ ワイルドカード付きのセクション名を解析する """
    if "*" not in key:
        return None
    head, _sep, tail = key.partition("*")
    emptyhead = len(head.strip()) == 0
    emptytail = len(tail.strip()) == 0
    if not emptyhead and emptytail:
        return CategoryMembers(head)
    elif emptyhead and emptytail:
        return AnyMembers()
    else:
        raise ValueError("ワイルドカード付きのセクション名'{}'は、接頭部が必要です".format(key))  


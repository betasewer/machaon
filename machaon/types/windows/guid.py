
import configparser
from ctypes import (
    Structure, wintypes
)
from uuid import UUID

#
# windows types
#
class GUID(Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8)
    ] 

    @classmethod
    def from_string(cls, uuidstr):
        v = cls()
        uuid = UUID(uuidstr)
        v.Data1, v.Data2, v.Data3, v.Data4[0], v.Data4[1], rest = uuid.fields
        for i in range(2, 8):
            v.Data4[i] = rest >> (8-i-1)*8 & 0xff
        return v


def parse_guid(name, guid_db_path=None):
    """
    文字列をGUIDオブジェクトに変換する
    """
    if name.startswith("{"):
        return GUID.from_string(name)
    else:
        # GUIDデータベースを名前で検索する
        if guid_db_path is None:
            raise ValueError("GUIDデータベースがありません")
        secname, sep, valname = name.partition(".")
        if not sep:
            raise ValueError("セクション名を指定してください")
        values = configparser.ConfigParser()
        values.read(guid_db_path)
        value = values.get(secname, valname)
        if value is None:
            raise ValueError("GUIDが見つかりません")
        return GUID.from_string(value)


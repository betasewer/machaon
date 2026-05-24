import urllib.request
import base64
import os
import configparser

from machaon.core.error import ErrorSet
from machaon.types.shell import Path

class Credential:
    def __init__(self, hostname, username, auth_type, keys, repo=None):
        self.hostname = hostname
        self.username = username
        self.auth_type = auth_type
        self.keys = keys
        self.repo = repo

    def user(self):
        return "{}@{}".format(self.username, self.hostname)
    
    def rebind_repository(self, repo, keys):
        """ 認証情報をリポジトリに再バインドする """
        newkeys = {}
        newkeys.update(self.keys)
        newkeys.update(keys)
        return Credential(self.hostname, self.username, self.auth_type, newkeys, repo)
    
    def _load_text(self, path):
        if not os.path.isfile(path):
            raise ValueError("認証鍵ファイルが存在しません：{}".format(path))
        with open(path, "r", encoding="utf-8") as fi:
            return fi.read().strip()
    
    def build_request_basic_auth(self, url, **kwargs):   
        """ ベーシック認証のリクエストを作成する """
        authuser = self.keys["authuser"] or self.username
        password = self._load_text(self.keys["key"])
        headers = kwargs.get("headers", {})
        authcode = base64.b64encode("{}:{}".format(authuser, password).encode("utf-8"))
        headers["authorization"] = "Basic {}".format(authcode.decode("ascii"))
        kwargs["headers"] = headers
        req = urllib.request.Request(url=url, **kwargs)
        return req
    
    def build_request_bearer_token(self, url, **kwargs):
        """ ベアラートークン認証のリクエストを作成する """
        token = self._load_text(self.keys["key"])
        headers = kwargs.get("headers", {})
        headers["authorization"] = "Bearer {}".format(token)
        kwargs["headers"] = headers
        req = urllib.request.Request(url=url, **kwargs)
        return req


#
#
#
class CredentialDir:
    def __init__(self, basic_dir: Path):
        self._pairs: dict[str, Credential] = {} # hostname -> Credential
        self._dir = basic_dir

    def add_authentication(self, hostname, username, auth, keys):
        """ 認証情報をメモリに保存する """
        key = hostname
        keyvals = {}
        for k, v in keys.items():
            # keyで始まる値は相対パスとみなして、絶対パスに変換する
            if k.startswith("key") and not os.path.isabs(v):
                keyvals[k] = self._dir / v
            else:
                keyvals[k] = v
        self._pairs[key] = Credential(hostname, username, auth, keyvals)

    def search(self, hostname: str) -> Credential|None:      
        """ 文字列で検索 """
        key = hostname
        if key in self._pairs:
            return self._pairs[key]
        return None







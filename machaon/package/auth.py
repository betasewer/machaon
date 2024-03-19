import urllib.request
import base64
import os
import configparser

from machaon.core.error import ErrorSet

class Credential:
    def __init__(self, hostname, username):
        self.hostname = hostname
        self.username = username

    def user(self):
        return "{}@{}".format(self.username, self.hostname)
    
    def build_request(self, rep, url, **kwargs):  
        raise NotImplementedError()


class BasicAuth(Credential):
    """
    ベーシック認証
    """
    def __init__(self, hostname, username, password):
        super().__init__(hostname, username)
        self.password = password
    
    def build_request(self, rep, url, **kwargs):    
        headers = kwargs.get("headers", {})
        authcode = base64.b64encode("{}:{}".format(rep.username, self.password).encode("utf-8"))
        headers["authorization"] = "Basic {}".format(authcode.decode("ascii"))
        kwargs["headers"] = headers
        req = urllib.request.Request(url=url, **kwargs)
        return req
    
#
#
#
class CredentialDir:
    def __init__(self, d):
        self._d = d
    
    def file(self, *paths):
        return self._d.join(*paths)

    def search(self, target):      
        """ 文字列で検索 """
        user, sep, hostname = target.partition("@")
        if not sep:
            raise ValueError("'ユーザー名@ホスト名'の形式で指定してください")
        username, sep, repositoryname = user.partition("/")
        hostname, username, repositoryname = [x.strip() for x in (hostname, username, repositoryname)]
        keys = [target]
        if repositoryname:
            keys.append("{}@{}".format(username, hostname))
        return self._search(keys, hostname, username)

    def search_from_repository(self, repository):
        """ リポジトリオブジェクトから検索 """
        hostname = repository.hostname
        username = repository.username
        repositoryname = repository.name
        return self._search([
            "{}/{}@{}".format(username, repositoryname, hostname),
            "{}@{}".format(username, hostname)
        ], hostname, username)
    
    def _search(self, keys, hostname, username):
        """ 
        パスワードをディレクトリから検索し、認証オブジェクトを作成する
        Params:
            keys(Sequence[str]): 検索するエントリ名の候補
        """
        if not self._d.isdir():
            self._d.makedirs() # ディレクトリを作成しておく
            raise ValueError("認証情報iniファイルをmachaon/credentialに配置してください")
        
        password = None
        typename = None
        errs = ErrorSet("認証情報ディレクトリの読み込み")
        for f in self._d.listdirfile():
            if not f.hasext(".ini"):
                continue
            c = configparser.ConfigParser()
            try:
                c.read(f)
            except Exception as e:
                errs.add(e, value=f)
            # レポジトリ指定のキーと指定なしのキーで検索する
            hitkey = next((x for x in keys if c.has_option(x, "password")), None)
            if hitkey:
                password = c.get(hitkey, "password")
                typename = c.get(hitkey, "type", fallback=None)
                break
        
        if password is None:
            errs.throw_if_failed("認証情報が見つかりませんでした　認証情報ファイルのロードエラー") # ファイルエラーが起きていれば
            raise ValueError("認証情報が見つかりませんでした")
        
        # 認証オブジェクト
        if typename == "basic":
            return BasicAuth(hostname, username, password)
        else:
            raise ValueError("type='{}': サポートされていない認証形式です".format(typename))






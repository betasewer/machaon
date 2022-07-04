import urllib.request
import base64
import os
import configparser

class Credential():
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


def create_credential(root, target=None, *, repository=None):  
    # username@hostname
    # username/repositoryname@hostname
    keys = []
    if target:
        # 文字列で指定
        user, sep, hostname = target.partition("@")
        if not sep:
            raise ValueError("'ユーザー名@ホスト名'の形式で指定してください")
        username, sep, repositoryname = user.partition("/")
        hostname, username, repositoryname = [x.strip() for x in (hostname, username, repositoryname)]
        keys.append(target)
        if repositoryname:
            keys.append("{}@{}".format(username, hostname))
    elif repository:
        hostname = repository.hostname
        username = repository.username
        repositoryname = repository.name
        keys.append("{}/{}@{}".format(username, repositoryname, hostname))
        keys.append("{}@{}".format(username, hostname))

    # パスワードをディレクトリから開いて読みだす
    d = root.get_credential_dir()
    if not os.path.isdir(d):
        os.makedirs(d) # ディレクトリを作成しておく
        raise ValueError("認証情報iniファイルをmachaon/credentialに配置してください")
    
    password = None
    typename = None
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            c = configparser.ConfigParser()
            try:
                c.read(p)
            except:
                continue
            # レポジトリ指定のキーと指定なしのキーで検索する
            hitkey = next((x for x in keys if c.has_option(x, "password")), None)
            if hitkey:
                password = c.get(hitkey, "password")
                typename = c.get(hitkey, "type", fallback=None)
                break
    
    if password is None:
        raise ValueError("認証情報が見つかりませんでした")
    
    # 認証オブジェクト
    if typename == "basic":
        return BasicAuth(hostname, username, password)
    else:
        raise ValueError("type='{}': サポートされていない認証形式です".format(typename))


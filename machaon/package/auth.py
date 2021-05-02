import urllib.request
import base64
import os
import configparser

class Credential():
    def __init__(self, hostname, username):
        self.hostname = hostname
        self.username = username
    
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


def create_credential(root, target, typename):  
    # ホスト名とユーザー名
    username, sep, hostname = target.partition("@")
    if not sep:
        raise ValueError("'ユーザー名@ホスト名'の形式で指定してください")
    hostname = hostname.strip()
    username = username.strip()

    # パスワードをディレクトリから開いて読みだす
    password = None
    d = root.get_credential_dir()
    if not os.path.isdir(d):
        os.makedirs(d) # ディレクトリを作成しておく
        raise ValueError("認証情報iniファイルsをmachaon/credentialに配置してください")
    
    for name in os.listdir(d):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            c = configparser.ConfigParser()
            try:
                c.read(p)
            except:
                continue
            if c.has_option(target, "password"):
                password = c[target]["password"]
                break
    
    if password is None:
        raise ValueError("認証情報が見つかりませんでした")

    # 認証オブジェクト
    if typename == "basic":
        cred = BasicAuth(hostname, username, password)
    else:
        raise ValueError("'{}': サポートされていない認証形式です".format(typename))

    return cred


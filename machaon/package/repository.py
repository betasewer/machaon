from typing import TYPE_CHECKING

import os
import zipfile
import urllib.request
import urllib.error
import json
from machaon.package.archive import BasicArchive

if TYPE_CHECKING:
    from machaon.package.auth import Credential, CredentialDir

#
class RepositoryURLError(Exception):
    def get_basic(self) -> Exception:
        return super().args[0]


REPO_DELIM_HOST = "/"
REPO_DELIM_USER = "/"
REPO_DELIM_BRANCH = ":"
REPO_DELIM_SUBPATH = "//"

#
#
#
class RepositoryArchive(BasicArchive):
    download_chunk_size = 20 * 1024 # 20kb
    download_timeout = 15 # 秒

    hostname = "<unspecified>"
    
    def __init__(self, 
            source: str, *, 
            username: str|None = None, 
            subpath: str|None = None, 
            branch: str|None = None, 
            arcfilename: str|None = None, 
            cred: 'Credential|None' = None,
        ):
        """
        Params:
            source: リポジトリのソース情報（リポジトリ名、ブランチ名を含む）
                形式：repository-name:branch
            username: ユーザー名（sourceに含まれるユーザー名よりも優先される）
            subpath: [optional] リポジトリ内のサブディレクトリを示すパス（sourceに含まれるサブパスよりも優先される）
            branch: [optional] ブランチ名（sourceに含まれるブランチ名よりも優先される）
            arcfilename: [optional] ダウンロードするアーカイブのファイル名（指定しない場合は[リポジトリ名].zip）
            private: [optional] プライベートリポジトリかどうか
        """
        super().__init__()
        
        if REPO_DELIM_SUBPATH in source:
            n_subpath, _sep, source = source.rpartition(REPO_DELIM_SUBPATH)
        else:
            n_subpath = None

        if REPO_DELIM_USER in source:
            n_username, _sep, source = source.partition(REPO_DELIM_USER)
        else:
            n_username = None

        if REPO_DELIM_BRANCH in source:
            n_repo, _sep, n_branch = source.partition(REPO_DELIM_BRANCH)
        else:
            n_repo = source
            n_branch = None

        name = n_repo
        if username is None:
            username = n_username
        if branch is None:
            branch = n_branch or "main"
        if subpath is None:
            subpath = n_subpath
        
        if not name:
            raise ValueError("Specify repository name: " + name)
        if not username:
            raise ValueError("Specify username: " + name)

        self.name = name
        self.username = username
        self.branch = branch
        self.subpath = subpath
        self.arcfilename = arcfilename or name + ".zip"
        self.cred = cred
    
    def get_arcfilepath(self, workdir):
        return os.path.join(workdir, self.arcfilename)

    def get_name(self) -> str:
        return self.name
    
    def get_source(self) -> str:
        # ホスト名を含む完全なソース文字列を生成する
        terms = [
            type(self).hostname,
            REPO_DELIM_HOST,
            self.username,
            REPO_DELIM_USER,
            self.name,
            REPO_DELIM_BRANCH,
            self.branch
        ]
        if self.subpath is not None and self.subpath != "":
            terms.extend([
                REPO_DELIM_SUBPATH, 
                self.subpath
            ])
        return "".join(terms)

    def get_repository_url(self, commit):
        """ 指定のコミットのリポジトリURLを取得する """
        raise NotImplementedError()
    
    #
    # ダウンロード
    #
    def get_download_url(self, commit) -> str:
        """ 指定のコミットのダウンロードURLを取得する """
        raise NotImplementedError()
    
    def download_iter(self, outfilename, commit=None):
        """ ダウンロードを進めるイテレータ：ダウンロードしたサイズを返す """
        url = self.get_download_url(commit)
        
        datas = []
        with self.open_url(url, method="GET") as response:
            bits = None
            while True:
                bits = response.read(type(self).download_chunk_size)
                if not bits:
                    break
                datas.append(bits)
                yield len(bits)
        
        with open(outfilename, "wb") as fo:
            for bits in datas:
                fo.write(bits)

    def query_download_size(self, commit=None):
        """ ダウンロードするアーカイブのサイズを取得：不定の時はNone """
        url = self.get_download_url(commit)
        try: 
            with self.open_url(url, method="HEAD") as response:
                leng = response.headers.get("content-length", None)
                if leng is None:
                    return None
                return int(leng)
        except RepositoryURLError:
            pass
        return None
    
    def build_auth_request(self, cred: 'Credential', url, **kwargs):
        """ 認証情報を使ってリクエストを作成する """
        raise NotImplementedError()

    def query_latest_commit(self):
        """ 最新のコミットのハッシュを取得する """
        raise NotImplementedError()
 
    def query_json(self, url, *, encoding="utf-8"):
        with self.open_url(url, method="GET") as response:
            blob = response.read()
        return json.loads(bytes(blob).decode(encoding))

    def open_url(self, url, **kwargs):
        if self.cred is not None:
            req = self.build_auth_request(self.cred, url, **kwargs)
        else:
            req = urllib.request.Request(url=url, **kwargs)
        try:
            return urllib.request.urlopen(req, timeout=type(self).download_timeout)
        except urllib.error.URLError as e:
            raise RepositoryURLError(e)
    

#
#
#
class GithubRepArchive(RepositoryArchive):
    hostname = "github"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def get_repository_url(self, commit):
        return "https://github.com/{}/{}/".format(self.username, self.name)
    
    def get_download_url(self, commit):
        if commit is not None:
            return "https://api.github.com/repos/{}/{}/zipball/{}".format(self.username, self.name, commit)
        else:
            return "https://api.github.com/repos/{}/{}/zipball/{}".format(self.username, self.name, self.branch)

    def query_latest_commit(self):
        url = "https://api.github.com/repos/{}/{}/git/ref/heads/{}".format(self.username, self.name, self.branch)
        js = self.query_json(url)
        sha = js["object"]["sha"]
        return sha
    
    def build_auth_request(self, cred: 'Credential', url, **kwargs):
        # personal access tokenを使うBearer認証
        return cred.build_request_bearer_token(url, **kwargs)

#
#
#
class BitbucketRepArchive(RepositoryArchive):
    hostname = "bitbucket"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def get_repository_url(self, commit):
        return "https://bitbucket.org/{}/{}/".format(self.username, self.name)
    
    def get_download_url(self, commit):
        if commit is not None:
            return "https://bitbucket.org/{}/{}/get/{}.zip".format(self.username, self.name, commit)
        else:
            return "https://bitbucket.org/{}/{}/get/{}.zip".format(self.username, self.name, self.branch)
    
    def query_latest_commit(self):
        url = "https://api.bitbucket.org/2.0/repositories/{}/{}/commits/{}".format(self.username, self.name, self.branch)
        js = self.query_json(url)
        hash_ = js["values"][0]["hash"]
        return hash_

    def build_auth_request(self, cred: 'Credential', url, **kwargs):
        # APIトークンを使うBasic認証
        return cred.build_request_basic_auth(url, **kwargs)




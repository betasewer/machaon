import os
import zipfile
import urllib.request
import urllib.error
import json
from machaon.package.archive import BasicArchive

#
class RepositoryURLError(Exception):
    def get_basic(self):
        return super().args[0]



#
#
#
class RepositoryArchive(BasicArchive):
    download_chunk_size = 20 * 1024 # 20kb
    download_timeout = 15 # 秒

    hostname = "<unspecified>"
    
    def __init__(self, name, *, username=None, branch=None, arcfilename=None):
        super().__init__()

        rest = name
        n_username = None
        n_branch = None
        if "/" in rest:
            n_username, sep, rest = rest.partition("/")
        if ":" in rest:
            rest, sep, n_branch = rest.partition(":")        

        if username is None:
            username = n_username
        if branch is None:
            branch = n_branch or "master"
        name = rest
        
        if not name:
            raise ValueError("Specify repository name: " + name)
        if not username:
            raise ValueError("Specify username: " + name)

        self.name = name
        self.username = username
        self.branch = branch
        self.arcfilename = arcfilename or name + ".zip"
    
    def get_arcfilepath(self, workdir):
        return os.path.join(workdir, self.arcfilename)

    def get_name(self) -> str:
        return self.name
    
    def get_source(self) -> str:
        return "{}:{}/{}:{}".format(type(self).hostname, self.username, self.name, self.branch)

    def get_repository_url(self, commit):
        raise NotImplementedError()
    
    #
    # ダウンロード
    #
    def get_download_url(self, commit=None) -> str:
        raise NotImplementedError()
    
    def download_iter(self, outfilename, commit=None, cred=None):
        """ ダウンロードを進めるイテレータ：ダウンロードしたサイズを返す """
        url = self.get_download_url(commit)
        
        datas = []
        with self.open_url(url, method="GET", cred=cred) as response:
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

    def query_download_size(self, commit=None, cred=None):
        """ ダウンロードするアーカイブのサイズを取得：不定の時はNone """
        url = self.get_download_url(commit)
        try: 
            with self.open_url(url, method="HEAD", cred=cred) as response:
                leng = response.headers.get("content-length", None)
                if leng is None:
                    return None
                return int(leng)
        except urllib.error.URLError:
            pass
        return None

    def query_hash(self):
        raise NotImplementedError()
 
    def query_json(self, url, *, encoding="utf-8", cred=None):
        with self.open_url(url, method="GET", cred=cred) as response:
            blob = response.read()
        return json.loads(bytes(blob).decode(encoding))
        
    def open_url(self, url, *, cred=None, **kwargs):
        if cred is not None:
            req = cred.build_request(self, url, **kwargs)
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
    hostname = "github.com"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def get_repository_url(self):
        return "https://github.com/{}/{}/".format(self.username, self.name)
    
    def get_download_url(self, commit):
        if commit is not None:
            return "https://github.com/{}/{}/archive/{}.zip".format(self.username, self.name, commit)
        else:
            return "https://github.com/{}/{}/archive/refs/heads/{}.zip".format(self.username, self.name, self.branch)

    def query_hash(self):
        url = "https://api.github.com/repos/{}/{}/git/ref/heads/{}".format(self.username, self.name, self.branch)
        js = self.query_json(url)
        sha = js["object"]["sha"]
        return sha
    
#
#
#
class BitbucketRepArchive(RepositoryArchive):
    hostname = "bitbucket.org"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def get_repository_url(self):
        return "https://bitbucket.org/{}/{}/".format(self.username, self.name)
    
    def get_download_url(self, commit):
        if commit is not None:
            return "https://bitbucket.org/{}/{}/get/{}.zip".format(self.username, self.name, commit)
        else:
            return "https://bitbucket.org/{}/{}/get/{}.zip".format(self.username, self.name, self.branch)
    
    def query_hash(self):
        url = "https://api.bitbucket.org/2.0/repositories/{}/{}/commits/{}".format(self.username, self.name, self.branch)
        js = self.query_json(url)
        hash_ = js["values"][0]["hash"]
        return hash_

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
    is_remote = True
    is_archive = True

    download_chunk_size = 20 * 1024 # 20kb
    download_timeout = 15 # 秒

    hostname = "<unspecified>"
    
    def __init__(self, name, username=None, arcfilename=None, credential=None):
        super().__init__()

        if username is None:
            if "/" not in name:
                raise ValueError("Specify username")
            username, name = name.split("/")

        self.name = name
        self.username = username
        self.credential = credential
        self.arcfilename = arcfilename or name + ".zip"
    
    def get_arcfilepath(self, workdir):
        return os.path.join(workdir, self.arcfilename)

    def get_source(self) -> str:
        return "remote:{}/{}/{}".format(type(self).hostname, self.username, self.name)
        
    def get_repository_url(self):
        raise NotImplementedError()
    
    def get_default_module(self):
        return self.name

    #
    # ダウンロード
    #
    def get_download_url(self) -> str:
        raise NotImplementedError()
    
    def download_iter(self, outfilename):
        """ ダウンロードを進めるイテレータ：ダウンロードしたサイズを返す """
        url = self.get_download_url()
        
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

    def query_download_size(self):
        """ ダウンロードするアーカイブのサイズを取得：不定の時はNone """
        url = self.get_download_url()
        try: 
            with self.open_url(url, method="HEAD") as response:
                leng = response.headers.get("content-length", None)
                if leng is None:
                    return None
                return int(leng)
        except urllib.error.URLError:
            pass
        return None
    
    def query_hash(self):
        raise NotImplementedError()
 
    #
    def query_json(self, url, encoding="utf-8"):
        with self.open_url(url) as response:
            blob = response.read()
        return json.loads(bytes(blob).decode(encoding))
        
    def open_url(self, url, **kwargs):
        if self.credential:
            req = self.credential.build_request(self, url, **kwargs)
        else:
            req = urllib.request.Request(url=url, **kwargs)
        try:
            return urllib.request.urlopen(req, timeout=type(self).download_timeout)
        except urllib.error.URLError as e:
            raise RepositoryURLError(e)
    
    #
    def add_credential(self, hostname, username, cred):
        if type(self).hostname == hostname and self.username == username:
            self.credential = cred
            return True
        return False

#
#
#
class GithubRepArchive(RepositoryArchive):
    hostname = "github.com"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def get_repository_url(self):
        return "https://github.com/{}/{}/".format(self.username, self.name)
    
    def get_download_url(self):
        return "https://api.github.com/repos/{}/{}/zipball/master".format(self.username, self.name)

    def query_hash(self):
        url = "https://api.github.com/repos/{}/{}/git/ref/heads/master".format(self.username, self.name)
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
    
    def get_download_url(self):
        return "https://bitbucket.org/{}/{}/get/master.zip".format(self.username, self.name)
    
    def query_hash(self):
        url = "https://api.bitbucket.org/2.0/repositories/{}/{}/commits/master".format(self.username, self.name)
        js = self.query_json(url)
        hash_ = js["values"][0]["hash"]
        return hash_

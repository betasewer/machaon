import os
import zipfile
import urllib.request
import urllib.error
import json

#
class ArchiveNotOpenedError(Exception):
    pass

class RepositoryURLError(Exception):
    def get_basic(self):
        return super().args[0]

#
#
#
class rep_archive:
    download_chunk_size = 20 * 1024 # 20kb
    download_timeout = 15 # 秒
    root_level = 1
    
    def __init__(self, name, username=None, filename=None, credential=None):
        if username is None:
            if "/" not in name:
                raise ValueError("Specify username")
            username, name = name.split("/")

        self.name = name
        self.username = username
        self.filename = filename or name+".zip"
        self.credential = credential
        
        self._arc = None
        self._arcroot = None
    
    def get_host(self) -> str:
        raise NotImplementedError()
    
    def get_id(self) -> str:
        return "{}/{}".format(self.username, self.name)
        
    def get_repository_url(self):
        raise NotImplementedError()
    
        
    #
    # アーカイブを操作する
    #
    def open_archive(self, directory):
        if self._arc is None:
            p = os.path.join(directory, self.filename)
            self._arc = self.open_archive_reader(p)
            self._retrieve_root()
        return self
    
    def close_archive(self):
        if self._arc is not None:
            self._arc.close()
            self._arc = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, et, ev, tb):
        self.close_archive()
    
    def open_archive_reader(self, p):
        """ オーバーライドしてgzip等に対応 """
        return zipfile.ZipFile(p, "r")
        
    @classmethod
    def splitroot(cls, p):
        if cls.root_level > 0:
            spl = p.split("/", maxsplit=cls.root_level)
            if len(spl) < cls.root_level:
                raise ValueError("")
            return "/".join(spl[:cls.root_level]), spl[cls.root_level]
        else:
            return "", p
    
    def _retrieve_root(self):
        """ arcrootを取得する """
        if type(self).root_level > 0:
            for firstzpath in self._arc.namelist():
                break
            self._arcroot, _ = type(self).splitroot(firstzpath)
        else:
            self._arcroot = ""
    
    # basedirを除いた名前リストを作成
    def memberlist(self):
        if self._arc is None:
            raise ArchiveNotOpenedError()
        for zpath in self._arc.namelist():
            _root, name = type(self).splitroot(zpath)
            yield name
    
    def get_member_root(self):
        if self._arcroot is None:
            raise ArchiveNotOpenedError("root path remains unknown")
        return self._arcroot
    
    def get_member_path(self, path):
        if self._arcroot is None:
            raise ArchiveNotOpenedError("Archive has not opened yet and root path remains unknown")
        return self._arcroot + "/" + path
    
    #
    # ダウンロード
    #
    def get_download_url(self) -> str:
        raise NotImplementedError()
    
    def download_iter(self, directory):
        """ ダウンロードを進めるイテレータ：ダウンロードしたサイズを返す """
        url = self.get_download_url()
        out = os.path.join(directory, self.filename)
        
        datas = []
        with self.open_url(url, method="GET") as response:
            bits = None
            while True:
                bits = response.read(type(self).download_chunk_size)
                if not bits:
                    break
                datas.append(bits)
                yield len(bits)
        
        with open(out, "wb") as fo:
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
    # 展開
    #
    def extract(self, path):
        if self._arc is None:
            raise ArchiveNotOpenedError()
        self._arc.extractall(path)

#
#
#
class github_rep(rep_archive):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def get_host(self):
        return "github.com"
    
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
class bitbucket_rep(rep_archive):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def get_host(self):
        return "bitbucket.org"
        
    def get_repository_url(self):
        return "https://bitbucket.org/{}/{}/".format(self.username, self.name)
    
    def get_download_url(self):
        return "https://bitbucket.org/{}/{}/get/master.zip".format(self.username, self.name)
    
    def query_hash(self):
        url = "https://api.bitbucket.org/2.0/repositories/{}/{}/commits/master".format(self.username, self.name)
        js = self.query_json(url)
        hash_ = js["values"][0]["hash"]
        return hash_

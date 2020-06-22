import os
import shutil
import zipfile

#
class ArchiveNotOpenedError(Exception):
    pass

#
# アーカイブファイル
#
class basic_archive():
    is_remote = False
    is_archive = True

    root_level = 1

    def __init__(self):
        self._arc = None
        self._arcroot = None
    
    #
    # アーカイブを操作する
    #
    def open_archive(self, arcfilepath):
        if self._arc is None:
            self._arc = self.open_archive_reader(arcfilepath)
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
    # 展開
    #
    def extract(self, arcfilepath, outdir):
        with self.open_archive(arcfilepath):
            self._arc.extractall(outdir)
        return os.path.join(outdir, self.get_member_root())

#
#
#
class local_archive(basic_archive):
    def __init__(self, filepath, *, name):
        super().__init__()
        self.filepath = filepath
        self.name = name
    
    def get_arcfilepath(self, _workdir):
        return self.filepath
        
    def get_source(self) -> str:
        return "local-archive:{}/{}".format(self.name, self.filepath)

    def query_hash(self):
        return None

#
#
#
class local_file():
    is_remote = False
    is_archive = False

    def __init__(self, filepath, *, name):
        self.filepath = filepath
        self.name = name

    def get_source(self) -> str:
        return "local-file:{}/{}".format(self.name, self.filepath)
    
    #
    # パスを取得
    #
    def get_local_path(self):
        return self.filepath
    
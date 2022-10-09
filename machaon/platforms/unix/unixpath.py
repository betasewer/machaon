

def getpwuid(uid):
    import pwd
    return pwd.getpwuid(uid)
    
def getgrgid(gid):
    import grp
    return grp.getgrgid(gid)


class UnixPath:
    def owner(self, f):
        """ @method
        ファイルを所持するユーザーおよびグループを示す文字列
        Returns:
            Str:
        """
        return "{}:{}".format(getpwuid(f.stat.st_uid)[0], getgrgid(f.stat.st_gid)[0])
    
    def owner_user(self, f):
        """ @method
        ファイルを所持するユーザーのID
        Returns:
            Str:
        """
        return f.stat.st_uid

    def owner_group(self, f):
        """ @method
        ファイルを所持するユーザーグループのID
        Returns:
            Str:
        """
        return f.stat.st_gid
    
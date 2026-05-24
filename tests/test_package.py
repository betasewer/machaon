import pytest
import sys
import os
import configparser
from machaon.types.shell import Path
from machaon.core.milestones import milestone

from machaon.package.package import Package, PackageManager
#from machaon.package.repository import bitbucket_rep
#from machaon.package.auth import basic_auth
#from machaon.package.archive import local_archive
#from machaon.engine import NotYetInstalledCommandSet
#from machaon.process import TempSpirit
#from machaon.commands.package import package_install, command_package

def temp_packages(tmpdir, defname, pkgdef):
    basic_dir = (Path(tmpdir) / "packages").makedirs()

    pkgconfig = basic_dir / "{}.packages".format(defname)
    cfg = configparser.ConfigParser()
    cfg.read_dict(pkgdef)
    with open(pkgconfig, "w", encoding="utf-8") as fo:
        cfg.write(fo)

    pkgm = PackageManager(basic_dir)
    pkgm.init()
    pkgm.load_packages(basic_dir)
    return pkgm


def test_defined_package_basic(tmpdir):
    pkgm = temp_packages(tmpdir, "test", {
        "host.betasewer": {
            "site": "github",
            "username": "betasewer",
        },
        "package.ageha": {
            "repository": "betasewer/ageha:master"
        }
    })

    pkg: Package = pkgm.get("ageha")
    assert pkg
    assert pkg.name == "ageha"
    assert pkg.listname == "test"
    assert pkg.is_remote_source()
    assert pkg.is_modules()
    assert pkg.source_signature == "github/betasewer/ageha:master"
    assert not pkg.is_fetched()
    assert pkg.query_update_status() == "notfound"

    from machaon.package.repository import GithubRepArchive
    assert isinstance(pkg.get_source(), GithubRepArchive)
    assert pkg.get_source().get_download_url(None) == "https://api.github.com/repos/{}/{}/zipball/{}".format("betasewer", "ageha", "master")

    last = None
    for last in pkgm.fetch(pkg, latest=True):
        pass
    assert milestone.match_type(last, PackageManager.FINISHED) and last.success

    assert pkg.is_fetched()
    assert pkg.query_update_status() == "latest"


def test_defined_package_resource(tmpdir):
    pkgm = temp_packages(tmpdir, "test", {
        "host.betasewer": {
            "site": "github",
            "username": "betasewer",
        },
        "package.ageha-source": {
            "repository": "betasewer/ageha:master",
            "resource": True
        }
    })

    pkg: Package = pkgm.get("ageha-source")
    assert pkg
    assert pkg.is_remote_source()
    assert pkg.is_resource()
    assert pkg.source_signature == "github/betasewer/ageha:master"
    assert not pkg.is_fetched()
    assert pkg.query_update_status() == "notfound"

    last = None
    for last in pkgm.fetch(pkg, latest=True):
        pass
    assert milestone.match_type(last, PackageManager.FINISHED) and last.success

    assert pkg.is_fetched()
    assert pkg.query_update_status() == "latest"

    location = pkg.get_fetched_location(pkgm)
    assert location is not None
    assert location.isdir()


def test_defined_package_update(tmpdir):
    # パッケージを新規導入する
    pkgm = temp_packages(tmpdir, "test", {
        "host.betasewer": {
            "site": "github",
            "username": "betasewer",
        },
        "package.ageha": {
            "repository": "betasewer/ageha:master+9dd7f3c2ba9d3d4cf544baa3b4a89a70255c2acc"
        }
    })

    pkg: Package = pkgm.get("ageha")
    assert pkg
    assert pkg.source_signature == "github/betasewer/ageha:master"
    assert pkg.get_target_commit() == "9dd7f3c2ba9d3d4cf544baa3b4a89a70255c2acc"

    # 初回の新規インストール (定義されたコミットをフェッチ)
    last = None
    for last in pkgm.fetch(pkg, latest=True):
        pass
    assert milestone.match_type(last, PackageManager.FINISHED) and last.success

    assert pkg.is_fetched()
    assert pkg.get_fetched_commit() == "9dd7f3c2ba9d3d4cf544baa3b4a89a70255c2acc"
    assert pkg.query_update_status() == "old"

    # 更新する (最新のコミットをフェッチ)
    last = None
    for last in pkgm.fetch(pkg, latest=False):
        pass
    assert milestone.match_type(last, PackageManager.FINISHED) and last.success

    assert pkg.is_fetched()
    nowhash = pkg.get_fetched_commit()
    assert nowhash and len(nowhash) > 0
    assert nowhash != "9dd7f3c2ba9d3d4cf544baa3b4a89a70255c2acc"
    assert pkg.query_update_status() == "latest"


@pytest.mark.skip
def test_no_dep_package(tmpdir):
    pkgm = temp_packages(tmpdir, "test", {
        "docxx": {
            "repository": "github:betasewer/python-docx-xtended",
            "module": "docxx"
        }
    })
    approot.add_package_option("docxx:test", no_dependency=True)
    
    approot.boot_core()

    pkgm = approot.package_manager()
    pkg: Package = pkgm.get("docxx:test")
    assert pkg
    
    spi = approot.temp_spirit(doprint=True)
    AppPackageType().display_update(pkg, spi, forceupdate=True)




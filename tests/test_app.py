from machaon.app import AppRoot, deploy_directory
from machaon.process import Spirit
from machaon.types.shell import Path


def test_deploy(tmpdir):
    deploydir = tmpdir.mkdir("deploy")
    deploy_directory(Path(deploydir))

    assert deploydir.join("machaon").check()
    assert deploydir.join("machaon", "store").check()
    assert deploydir.join("machaon", "packages").check()
    assert deploydir.join("machaon", "credential").check()
    assert deploydir.join("machaon", "credential", "credential.ini").check()
    assert deploydir.join("machaon", "local").check()
    assert deploydir.join("machaon", "apps.ini").check()
    assert deploydir.join("main.py").check()

import pytest
from lib.rules import findings_for_workload


def test_detecta_privileged_unpinned_docker_sock_e_porta_exposta():
    wl = {"name": "web", "image": "nginx", "tag": "latest", "digest": None,
          "privileged": True, "user": "root",
          "mounts": [{"type": "bind", "source": "/var/run/docker.sock", "target": "/x"}],
          "ports": [{"port": "80/tcp", "host_ip": "0.0.0.0", "host_port": "8080"}]}
    ids = {f["rule_id"] for f in findings_for_workload(wl, scope="cluster-wide")}
    assert {"SEC_PRIVILEGED", "SEC_IMAGE_UNPINNED", "SEC_DOCKER_SOCK",
            "SEC_USER_ROOT", "SEC_PORT_EXPOSED"} <= ids


def test_finding_tem_campos_completos_e_scope():
    wl = {"name": "web", "image": "nginx", "tag": "latest", "digest": None,
          "privileged": False, "user": "1000", "mounts": [], "ports": []}
    f = [x for x in findings_for_workload(wl, scope="node-1") if x["rule_id"] == "SEC_IMAGE_UNPINNED"][0]
    assert f["severity"] in {"high", "med", "low"}
    assert f["evidence"] and f["fix"] and f["scope"] == "node-1"


@pytest.mark.parametrize("user", [None, "0", "0:0", "root", "ROOT"])
def test_root_em_todas_as_formas(user):
    wl = {"name": "x", "image": "app", "tag": "1.0", "digest": "sha256:d",
          "privileged": False, "user": user, "mounts": [], "ports": []}
    ids = {f["rule_id"] for f in findings_for_workload(wl, scope="s")}
    assert "SEC_USER_ROOT" in ids


def test_docker_sock_e_subpaths_sensiveis():
    for src in ("/run/docker.sock", "/etc/passwd", "/root/.ssh", "/"):
        wl = {"name": "x", "image": "app", "tag": "1.0", "digest": "sha256:d",
              "privileged": False, "user": "1000",
              "mounts": [{"type": "bind", "source": src, "target": "/m"}], "ports": []}
        ids = {f["rule_id"] for f in findings_for_workload(wl, scope="s")}
        assert "SEC_DOCKER_SOCK" in ids, src
    # subpath parecido mas NÃO sensível não dispara
    wl = {"name": "x", "image": "app", "tag": "1.0", "digest": "sha256:d",
          "privileged": False, "user": "1000",
          "mounts": [{"type": "bind", "source": "/etcd-data", "target": "/m"}], "ports": []}
    assert not any(f["rule_id"] == "SEC_DOCKER_SOCK" for f in findings_for_workload(wl, scope="s"))


def test_workload_limpo_sem_findings():
    wl = {"name": "ok", "image": "app", "tag": "1.2.3", "digest": "sha256:deadbeef",
          "privileged": False, "user": "1000", "mounts": [], "ports": []}
    assert findings_for_workload(wl, scope="cluster-wide") == []

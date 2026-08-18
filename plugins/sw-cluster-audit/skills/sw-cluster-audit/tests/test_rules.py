import pytest
from lib.rules import findings_for_workload, findings_operational


# ---------------------------------------------------------------- segurança
def test_detecta_privileged_unpinned_docker_sock_e_porta_exposta():
    wl = {"name": "web", "image": "nginx", "tag": "latest", "digest": None,
          "privileged": True, "user": "root",
          "mounts": [{"type": "bind", "source": "/var/run/docker.sock", "target": "/x"}],
          "ports": [{"port": "80/tcp", "host_ip": "0.0.0.0", "host_port": "8080"}]}
    ids = {f["rule_id"] for f in findings_for_workload(wl, scope="cluster-wide")}
    assert {"SEC_PRIVILEGED", "SEC_IMAGE_UNPINNED", "SEC_DOCKER_SOCK",
            "SEC_USER_ROOT", "SEC_PORT_EXPOSED"} <= ids


@pytest.mark.parametrize("image,name", [
    ("gcr.io/cadvisor/cadvisor", "monitoring_cadvisor"),
    ("grafana/promtail", "loki_promtail"),
    ("traefik", "traefik_traefik"),          # Traefik precisa do socket p/ service discovery
    ("portainer/agent", "portainer_agent"),
])
def test_docker_sock_esperado_em_ferramenta_nao_vira_critico(image, name):
    wl = {"name": name, "image": image, "tag": "1.0", "digest": "sha256:d",
          "privileged": False, "user": "1000",
          "mounts": [{"type": "bind", "source": "/var/run/docker.sock", "target": "/x"}], "ports": []}
    fs = [f for f in findings_for_workload(wl, scope="s") if "DOCKER_SOCK" in f["rule_id"]]
    assert fs[0]["rule_id"] == "SEC_DOCKER_SOCK_EXPECTED"
    assert fs[0]["severity"] == "low" and fs[0]["expected"] is True


def test_docker_sock_em_app_comum_continua_critico():
    wl = {"name": "loja_backend", "image": "myorg/loja-api", "tag": "1.0", "digest": "sha256:d",
          "privileged": False, "user": "1000",
          "mounts": [{"type": "bind", "source": "/var/run/docker.sock", "target": "/x"}], "ports": []}
    fs = [f for f in findings_for_workload(wl, scope="s") if "DOCKER_SOCK" in f["rule_id"]]
    assert fs[0]["rule_id"] == "SEC_DOCKER_SOCK" and fs[0]["severity"] == "high"


@pytest.mark.parametrize("user", [None, "0", "0:0", "root", "ROOT"])
def test_root_em_todas_as_formas(user):
    wl = {"name": "x", "image": "app", "tag": "1.0", "digest": "sha256:d",
          "privileged": False, "user": user, "mounts": [], "ports": []}
    assert "SEC_USER_ROOT" in {f["rule_id"] for f in findings_for_workload(wl, scope="s")}


def test_workload_limpo_sem_findings():
    wl = {"name": "ok", "image": "app", "tag": "1.2.3", "digest": "sha256:deadbeef",
          "privileged": False, "user": "1000", "mounts": [], "ports": []}
    assert findings_for_workload(wl, scope="cluster-wide") == []


# ---------------------------------------------------------------- operação
def test_servico_parado_e_med_nao_critico():
    r = {"nodes": [], "services": [{"name": "api", "replicas": "0/2"}]}
    f = findings_operational(r)[0]
    assert f["rule_id"] == "OPS_SERVICE_STOPPED" and f["severity"] == "med"


@pytest.mark.parametrize("name", ["ai2contract-api_flyway", "chatwoot_chatwoot-migrate",
                                  "helper_system_system-prune", "app_backup"])
def test_job_de_execucao_unica_em_zero_e_esperado(name):
    r = {"nodes": [], "services": [{"name": name, "replicas": "0/1"}]}
    f = findings_operational(r)[0]
    assert f["rule_id"] == "OPS_JOB_COMPLETED" and f["expected"] is True and f["severity"] == "low"


def test_replicas_degradadas():
    r = {"nodes": [], "services": [{"name": "api", "replicas": "1/3"}]}
    f = findings_operational(r)[0]
    assert f["rule_id"] == "OPS_REPLICAS_DEGRADED" and f["severity"] == "med"


def test_no_fora_do_ar_e_em_drain():
    r = {"nodes": [{"hostname": "n1", "state": "Down", "availability": "Active"},
                   {"hostname": "n2", "state": "Ready", "availability": "Drain"}], "services": []}
    ids = {f["rule_id"] for f in findings_operational(r)}
    assert ids == {"OPS_NODE_DOWN", "OPS_NODE_DRAIN"}


def test_cluster_convergido_sem_findings_operacionais():
    r = {"nodes": [{"hostname": "n1", "state": "Ready", "availability": "Active"}],
         "services": [{"name": "api", "replicas": "3/3"}, {"name": "w", "replicas": "1/1"}]}
    assert findings_operational(r) == []

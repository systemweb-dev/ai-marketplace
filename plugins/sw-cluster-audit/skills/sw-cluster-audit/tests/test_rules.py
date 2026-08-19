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


def test_cluster_convergido_sem_findings_graves():
    """Convergido = nenhum achado high/med. Dicas de higiene (low) podem existir."""
    r = {"nodes": [{"hostname": "n1", "state": "Ready", "availability": "Active"}],
         "services": [{"name": "api", "replicas": "3/3"}, {"name": "w", "replicas": "1/1"}]}
    fs = findings_operational(r)
    assert [f for f in fs if f["severity"] in ("high", "med")] == []


def test_sem_limites_e_sem_healthcheck_sao_dicas_low():
    r = {"nodes": [], "services": [{"name": "api", "replicas": "1/1", "has_healthcheck": False,
                                    "limits": {"nano_cpus": None, "mem_bytes": None}}]}
    fs = {f["rule_id"]: f for f in findings_operational(r)}
    assert fs["OPS_NO_LIMITS"]["severity"] == "low"
    assert fs["OPS_NO_HEALTHCHECK"]["severity"] == "low"
    assert "docker service update --limit-cpu" in fs["OPS_NO_LIMITS"]["fix"]


def test_task_falhando_e_reportada():
    r = {"nodes": [], "services": [{"name": "api", "replicas": "1/1", "tasks_failed": 2,
                                    "failed_reason": "OOMKilled",
                                    "limits": {"nano_cpus": 1}, "has_healthcheck": True}]}
    f = [x for x in findings_operational(r) if x["rule_id"] == "OPS_TASK_FAILING"][0]
    assert f["severity"] == "med" and "OOMKilled" in f["evidence"]


# ---------------------------------------------------------------- falhas de acesso
def test_certificado_expirado_vira_achado_critico():
    from lib.rules import findings_from_errors
    errs = [{"cmd": "docker info", "reason": 'tls: failed to verify certificate: x509: '
             'certificate has expired or is not yet valid: current time ... is after ...'}]
    f = findings_from_errors(errs, "prod")[0]
    assert f["rule_id"] == "OPS_TLS_EXPIRED" and f["severity"] == "high"
    assert "renovar os certificados" in f["fix"]


def test_daemon_inacessivel():
    from lib.rules import findings_from_errors
    f = findings_from_errors([{"cmd": "docker info", "reason": "connection refused"}], "prod")[0]
    assert f["rule_id"] == "OPS_DAEMON_UNREACHABLE" and f["severity"] == "high"


def test_erro_generico_nao_vira_achado():
    from lib.rules import findings_from_errors
    assert findings_from_errors([{"cmd": "docker info", "reason": "algo estranho"}], "prod") == []


def test_certificado_perto_de_expirar_avisa_antes():
    from lib.rules import findings_from_cert
    f = findings_from_cert({"status": "expiring", "days_left": 12,
                            "not_after": "2026-09-01T00:00:00+00:00"}, "prod")[0]
    assert f["rule_id"] == "OPS_TLS_EXPIRING" and f["severity"] == "med" and "12 dia" in f["evidence"]


def test_certificado_ok_ou_ausente_nao_gera_achado():
    from lib.rules import findings_from_cert
    assert findings_from_cert({"status": "ok", "days_left": 300, "not_after": "x"}, "p") == []
    assert findings_from_cert(None, "p") == []          # context ssh:// não tem certificado


def test_job_detectado_pelo_estado_complete_independente_do_nome():
    """Sinal infalível: o Swarm marca replicated-job concluído como Complete."""
    r = {"nodes": [], "services": [
        {"name": "systemweb-payments-api_worker", "replicas": "0/1", "completed_job": True}]}
    f = findings_operational(r)[0]
    assert f["rule_id"] == "OPS_JOB_COMPLETED" and f["expected"] is True


def test_servico_parado_sem_complete_continua_sendo_verificar():
    r = {"nodes": [], "services": [
        {"name": "loja_frontend", "replicas": "0/2", "completed_job": False}]}
    assert findings_operational(r)[0]["rule_id"] == "OPS_SERVICE_STOPPED"


def test_versoes_de_engine_divergentes_viram_achado():
    r = {"nodes": [{"hostname": "a", "state": "Ready", "engine": "28.3.3"},
                   {"hostname": "b", "state": "Ready", "engine": "29.5.0"}], "services": []}
    f = [x for x in findings_operational(r) if x["rule_id"] == "OPS_ENGINE_DRIFT"][0]
    assert f["severity"] == "low" and "28.3.3" in f["evidence"] and "29.5.0" in f["evidence"]


def test_engine_uniforme_nao_gera_achado():
    r = {"nodes": [{"hostname": "a", "state": "Ready", "engine": "28.3.3"},
                   {"hostname": "b", "state": "Ready", "engine": "28.3.3"}], "services": []}
    assert not any(x["rule_id"] == "OPS_ENGINE_DRIFT" for x in findings_operational(r))

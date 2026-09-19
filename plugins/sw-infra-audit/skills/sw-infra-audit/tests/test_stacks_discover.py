import pytest

from lib import stacks, discover, enrich


# ---------------------------------------------------------------- stacks
def _report():
    return {
        "services": [
            {"name": "challenge-api_api", "kind": "app", "replicas": "2/2", "routing_labels":
                {"traefik.http.routers.ch.rule": "Host(`api.challenge.com`)"}},
            {"name": "challenge-api_database", "kind": "banco", "replicas": "1/1", "routing_labels": {}},
            {"name": "traefik_traefik", "kind": "ingress/proxy", "replicas": "1/1", "routing_labels": {}},
        ],
        "findings": [
            {"rule_id": "SEC_PRIVILEGED", "severity": "high", "object": "traefik_traefik"},
            {"rule_id": "SEC_USER_ROOT", "severity": "med", "object": "challenge-api_api.1.xyz"},
        ],
    }


@pytest.mark.parametrize("name,stack,short", [
    ("challenge-api_database", "challenge-api", "database"),
    ("traefik_traefik", "traefik", "traefik"),
    ("avulso", "avulso", "avulso"),
])
def test_stack_of_e_short_name(name, stack, short):
    assert stacks.stack_of(name) == stack and stacks.short_name(name) == short


def test_group_agrupa_servicos_findings_e_spofs():
    gs = {g["stack"]: g for g in stacks.group(_report())}
    assert set(gs) == {"challenge-api", "traefik"}
    ch = gs["challenge-api"]
    assert len(ch["services"]) == 2
    assert ch["findings_med"] == 1                                  # finding com sufixo de task conta
    assert ch["spofs"] == ["challenge-api_database"]                # banco 1/1
    assert ch["routes"] == ["Host(`api.challenge.com`)"]
    assert gs["traefik"]["findings_high"] == 1 and gs["traefik"]["note"] == "red"


def test_group_ordena_pior_primeiro():
    assert stacks.group(_report())[0]["stack"] == "traefik"          # tem o high


# ---------------------------------------------------------------- discover
def test_host_from_context_endpoint():
    assert discover.host_from_context_endpoint("tcp://203.0.113.10:2376") == "203.0.113.10"
    assert discover.host_from_context_endpoint("unix:///var/run/docker.sock") == "localhost"


def test_propose_encontra_prometheus_e_prioriza_publicado():
    rep = {"services": [
        {"name": "monitoring_prometheus", "image": "prom/prometheus",
         "ports": [{"port": "9090/tcp", "host_ip": "0.0.0.0", "host_port": "9090"}]},
        {"name": "monitoring_cadvisor", "image": "gcr.io/cadvisor/cadvisor", "ports": []},
    ]}
    props = discover.propose(rep, "198.51.100.9")
    assert props[0]["kind_hint"] == "prometheus"
    assert props[0]["url"] == "http://198.51.100.9:9090/api/v1/query?query=up"
    assert props[0]["published"] is True
    assert discover.best(rep, "198.51.100.9")["service"] == "monitoring_prometheus"


def test_propose_detecta_identificador_na_tag_ou_no_nome():
    # caso real: 'portainer/template-swarm-monitoring:prometheus-v2.44.0' — 'prometheus' só na TAG
    rep = {"services": [
        {"name": "monitoring_prometheus", "image": "portainer/template-swarm-monitoring",
         "tag": "prometheus-v2.44.0",
         "ports": [{"port": "9090/tcp", "host_ip": "0.0.0.0", "host_port": "9090"}]},
    ]}
    props = discover.propose(rep, "198.51.100.9")
    assert props and props[0]["kind_hint"] == "prometheus"
    assert props[0]["url"].endswith(":9090/api/v1/query?query=up")


def test_propose_vazio_sem_fonte():
    assert discover.propose({"services": [{"name": "app", "image": "myapp", "ports": []}]}, "h") == []


# ---------------------------------------------------------------- enrich
def test_attach_casa_series_com_services():
    rep = {"services": [{"name": "challenge-api_api"}, {"name": "traefik_traefik"}]}
    runtime = {"requests_24h": {"challenge-api_api": 100, "fantasma": 7}}
    enrich.attach(rep, runtime)
    assert rep["services"][0]["runtime"]["requests_24h"] == 100
    assert rep["runtime_cluster"]["requests_24h"] == {"fantasma": 7}   # sem match vira cluster


def test_attach_casa_por_sufixo():
    rep = {"services": [{"name": "challenge-api_api"}]}
    enrich.attach(rep, {"requests_24h": {"api": 42}})                  # router 'api' → stack_api
    assert rep["services"][0]["runtime"]["requests_24h"] == 42


# ---------------------------------------------------------------- exporter (/metrics texto)
SAMPLE = """# HELP rabbitmq_queue_messages_ready mensagens prontas
# TYPE rabbitmq_queue_messages_ready gauge
rabbitmq_queue_messages_ready{queue="emails",vhost="/"} 42
rabbitmq_queue_messages_ready{queue="jobs",vhost="/"} 8
rabbitmq_queue_consumers{queue="emails"} 3
traefik_service_requests_total{code="200",service="challenge-api@docker"} 1000
traefik_service_requests_total{code="500",service="challenge-api@docker"} 7
metrica_ignorada{x="1"} 99
linha_invalida sem valor numerico
"""


def test_parse_text_metrics():
    parsed = enrich.parse_text_metrics(SAMPLE)
    nomes = [n for n, _, _ in parsed]
    assert "rabbitmq_queue_messages_ready" in nomes
    assert "linha_invalida" not in nomes                       # linha malformada ignorada
    labels = [l for n, l, _ in parsed if n == "rabbitmq_queue_consumers"][0]
    assert labels["queue"] == "emails"


def test_collect_from_exporter_soma_series(monkeypatch):
    monkeypatch.setattr(enrich, "get", lambda url, allowed, timeout=8: SAMPLE)
    out = enrich.collect_from_exporter("http://h:15692", ["h"])
    assert out["queue_ready"] == {"emails": 42, "jobs": 8}
    assert out["queue_consumers"] == {"emails": 3}
    assert out["requests_total"]["challenge-api"] == 1007      # soma 200 + 500, '@docker' removido


def test_collect_from_exporter_vazio_quando_nao_responde(monkeypatch):
    monkeypatch.setattr(enrich, "get", lambda url, allowed, timeout=8: None)
    assert enrich.collect_from_exporter("http://h:9999", ["h"]) == {}

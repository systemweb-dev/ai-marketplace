import pytest

from lib import stacks, discover


# ---------------------------------------------------------------- stacks
def _report():
    return {
        "services": [
            {"name": "loja-api_api", "kind": "app", "replicas": "2/2", "routing_labels":
                {"traefik.http.routers.ch.rule": "Host(`api.exemplo.test`)"}},
            {"name": "loja-api_database", "kind": "banco", "replicas": "1/1", "routing_labels": {}},
            {"name": "traefik_traefik", "kind": "ingress/proxy", "replicas": "1/1", "routing_labels": {}},
        ],
        "findings": [
            {"rule_id": "SEC_PRIVILEGED", "severity": "high", "object": "traefik_traefik"},
            {"rule_id": "SEC_USER_ROOT", "severity": "med", "object": "loja-api_api.1.xyz"},
        ],
    }


@pytest.mark.parametrize("name,stack,short", [
    ("loja-api_database", "loja-api", "database"),
    ("traefik_traefik", "traefik", "traefik"),
    ("avulso", "avulso", "avulso"),
])
def test_stack_of_e_short_name(name, stack, short):
    assert stacks.stack_of(name) == stack and stacks.short_name(name) == short


def test_group_agrupa_servicos_findings_e_spofs():
    gs = {g["stack"]: g for g in stacks.group(_report())}
    assert set(gs) == {"loja-api", "traefik"}
    ch = gs["loja-api"]
    assert len(ch["services"]) == 2
    assert ch["findings_med"] == 1                                  # finding com sufixo de task conta
    assert ch["spofs"] == ["loja-api_database"]                # banco 1/1
    assert ch["routes"] == ["Host(`api.exemplo.test`)"]
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


def test_propose_nao_inventa_porta_quando_a_da_metrica_nao_esta_publicada():
    """Casos reais do cluster: o traefik publica 80 e 443 (a métrica é a 8080) e o rabbitmq
    publica 15672, que é a UI de administração (a métrica é a 15692). Cair na primeira porta
    publicada fazia a skill PROPOR com confiança um endereço que devolve HTML, não métrica."""
    rep = {"services": [
        {"name": "traefik_traefik", "image": "traefik", "ports": [
            {"port": "80/tcp", "host_ip": "0.0.0.0", "host_port": "80"},
            {"port": "443/tcp", "host_ip": "0.0.0.0", "host_port": "443"}]},
        {"name": "rabbitmq_rabbitmq", "image": "rabbitmq", "ports": [
            {"port": "15672/tcp", "host_ip": "0.0.0.0", "host_port": "15672"}]},
    ]}

    por_servico = {c["service"]: c for c in discover.propose(rep, "198.51.100.9")}

    assert por_servico["traefik_traefik"]["url"] == "http://198.51.100.9:8080/metrics"
    assert por_servico["rabbitmq_rabbitmq"]["url"] == "http://198.51.100.9:15692/metrics"
    for c in por_servico.values():
        assert c["published"] is False, (
            "`published` precisa dizer se a porta DA MÉTRICA está publicada; dizer True porque "
            "o serviço publica alguma outra porta promete alcance que não existe")


def test_propose_vazio_sem_fonte():
    assert discover.propose({"services": [{"name": "app", "image": "myapp", "ports": []}]}, "h") == []

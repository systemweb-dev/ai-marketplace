from lib import impact


def _rep():
    return {
        "services": [
            {"name": "traefik_traefik", "kind": "ingress/proxy", "replicas": "1/1",
             "nodes": ["mgr-1"], "routing_labels": {"traefik.http.routers.a.rule": "Host(`a`)"}},
            {"name": "rabbitmq", "kind": "fila", "replicas": "1/1", "nodes": ["mgr-1"]},
            {"name": "web", "kind": "app", "replicas": "2/3", "tasks_failed": 0, "nodes": ["w1"]},
        ],
        "findings": [{"rule_id": "OPS_SERVICE_STOPPED", "object": "app_db"},
                     {"rule_id": "SEC_PORT_EXPOSED", "object": "traefik_traefik"}],
        "dimensions": {"higiene": {"limits_pct": 40, "healthcheck_pct": 20,
                                   "pinned_pct": 96, "nonroot_pct": 0}},
    }


def test_cenario_de_perda_de_no_agrupa_quem_nao_tem_replica():
    ps = impact.build(_rep())
    no = [p for p in ps if "mgr-1" in p["cenario"]][0]
    assert "ingress cai" in no["consequencia"]          # traduz pra consequência, não pra rótulo
    assert "sem failover" in no["consequencia"]         # e cita o serviço com estado
    assert no["impacto"] == "alto"
    assert set(no["alvos"]) == {"traefik_traefik", "rabbitmq"}


def test_servico_parado_vira_ponto_de_impacto_nao_saude():
    ps = impact.build(_rep())
    p = [x for x in ps if "parados" in x["cenario"]][0]
    assert "ninguém percebeu" in p["consequencia"] and p["alvos"] == ["app_db"]


def test_replica_faltando_sem_falha_e_capacidade_reduzida():
    p = [x for x in impact.build(_rep()) if "réplicas faltando" in x["cenario"]][0]
    assert "margem" in p["consequencia"] and "web (2/3)" in p["alvos"]


def test_higiene_vira_cenario_com_percentual_real():
    ps = impact.build(_rep())
    assert any("60% dos serviços rodam sem limite" in x["consequencia"] for x in ps)
    assert any("só 20% dos serviços têm healthcheck" in x["consequencia"] for x in ps)


def test_ordenado_por_impacto_depois_esforco():
    ps = impact.build(_rep())
    assert ps[0]["impacto"] == "alto"
    assert [p["impacto"] for p in ps] == sorted([p["impacto"] for p in ps],
                                                key=lambda i: {"alto": 0, "médio": 1, "baixo": 2}[i])


def test_cluster_impecavel_nao_gera_pontos():
    r = {"services": [{"name": "a", "kind": "app", "replicas": "3/3", "nodes": ["n1"]}],
         "findings": [],
         "dimensions": {"higiene": {"limits_pct": 100, "healthcheck_pct": 100,
                                    "pinned_pct": 100, "nonroot_pct": 100}}}
    assert impact.build(r) == []


def test_certificado_de_vida_longa_vira_ponto_de_impacto():
    r = _rep()
    r["tls"] = {"days_left": 7299, "status": "ok"}
    p = [x for x in impact.build(r) if "certificado de cliente vazar" in x["cenario"]][0]
    assert "19 anos" in p["consequencia"] and "root no host" in p["consequencia"]
    assert "chave SSH" in p["fix"] and p["impacto"] == "alto"


def test_certificado_curto_nao_gera_ponto():
    r = _rep(); r["tls"] = {"days_left": 300, "status": "ok"}
    assert not any("certificado" in x["cenario"] for x in impact.build(r))

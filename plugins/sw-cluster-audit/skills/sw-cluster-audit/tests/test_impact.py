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


def _cluster(n_managers=1, acme=True):
    nodes = [{"hostname": "mgr-1", "role": "Leader"}]
    nodes += [{"hostname": f"mgr-{i}", "role": "manager"} for i in range(2, n_managers + 1)]
    nodes += [{"hostname": f"w-{i}", "role": "worker"} for i in range(1, 4)]
    tk = {"name": "traefik_traefik", "kind": "ingress/proxy", "replicas": "1/1",
          "nodes": ["mgr-1"], "routing_labels": {"traefik.http.routers.a.rule": "Host(`a`)"},
          "mounts": ([{"type": "volume", "source": "letsencrypt", "target": "/letsencrypt"}]
                     if acme else [])}
    return {"nodes": nodes, "services": [tk], "findings": [], "dimensions": {}}


def _plano_do_no(rep):
    p = [x for x in impact.build(rep) if x["cenario"].startswith("Se o nó")][0]
    return p["plano"]


def test_plano_manda_promover_manager_quando_so_ha_um():
    passos = _plano_do_no(_cluster(n_managers=1))
    promover = passos[0]
    assert "Promover" in promover["passo"] and "quórum de 3" in promover["passo"]
    assert promover["comando"].startswith("docker node promote w-")   # nomes REAIS dos workers
    assert "control plane" in promover["porque"]


def test_plano_nao_manda_promover_quando_ja_ha_quorum():
    passos = _plano_do_no(_cluster(n_managers=3))
    assert not any("Promover" in p["passo"] for p in passos)


def test_acme_em_volume_local_vira_passo_bloqueante_antes_de_escalar():
    passos = _plano_do_no(_cluster(acme=True))
    titulos = [p["passo"] for p in passos]
    i_acme = next(i for i, t in enumerate(titulos) if "certificado" in t)
    i_escala = next(i for i, t in enumerate(titulos) if "escalar" in t)
    assert i_acme < i_escala, "resolver o ACME tem que vir ANTES de escalar, senão quebra o TLS"
    assert "letsencrypt" in passos[i_acme]["porque"]      # cita o volume que ele achou


def test_sem_acme_local_nao_inventa_o_passo():
    passos = _plano_do_no(_cluster(acme=False))
    assert not any("certificado" in p["passo"] for p in passos)


def test_load_balancer_vem_depois_de_escalar_e_explica_por_que():
    passos = _plano_do_no(_cluster())
    lb = [p for p in passos if "load balancer" in p["passo"]][0]
    assert passos.index(lb) == len(passos) - 1
    assert "réplica" in lb["porque"] and "viva" in lb["porque"]


def test_servico_com_estado_ganha_passo_proprio_sem_falar_em_replica():
    rep = _cluster()
    rep["services"].append({"name": "app_db", "kind": "banco", "replicas": "1/1",
                            "nodes": ["mgr-1"], "mounts": []})
    passos = _plano_do_no(rep)
    est = [p for p in passos if "estado" in p["passo"]][0]
    assert "backup" in est["porque"] and "app_db" in est["porque"]
    assert "--replicas 2 app_db" not in (est["comando"] or "")   # nunca sugerir isso p/ banco

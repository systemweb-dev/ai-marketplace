from lib import metrics, rules


def _report(replicas_db="1/1", node_state="Ready"):
    return {
        "nodes": [{"hostname": "n1", "state": node_state, "availability": "Active"}],
        "services": [
            {"name": "db", "kind": "banco", "replicas": replicas_db, "digest": None},
            {"name": "web", "kind": "proxy", "replicas": "2/2", "digest": "sha256:a"},
        ],
        "findings": [
            {"rule_id": "SEC_USER_ROOT", "severity": "med", "object": "db"},
            {"rule_id": "SEC_PRIVILEGED", "severity": "high", "object": "db"},
            {"rule_id": "SEC_IMAGE_UNPINNED", "severity": "med", "object": "db"},
        ],
    }


# ---------------------------------------------------------------- saúde = operação
def test_cluster_rodando_e_saudavel_mesmo_com_achados_de_seguranca():
    """O ponto central: higiene ruim NÃO torna a saúde do cluster crítica."""
    r = _report()
    r["findings"].extend(rules.findings_operational(r))
    dims = metrics.compute(r)["dimensions"]
    assert dims["operacao"]["note"] == "green"        # tudo no ar
    assert dims["seguranca"]["note"] == "red"         # segurança tem achado crítico
    assert metrics.verdict(dims) == "green"           # SAÚDE = só falha ativa; risco não conta


def test_servico_parado_estavel_nao_afeta_a_saude():
    """0 réplicas SEM falha é pendência (ponto de impacto), não doença — o cluster funciona."""
    r = _report(replicas_db="0/1")
    r["findings"].extend(rules.findings_operational(r))
    dims = metrics.compute(r)["dimensions"]
    assert dims["operacao"]["note"] == "green" and metrics.verdict(dims) == "green"
    assert dims["operacao"]["stopped"] == 1          # mas fica registrado


def test_falha_ativa_parcial_e_atencao():
    """1/3 falhando: ainda serve, mas não converge → atenção, não 'fora do ar'."""
    r = _report()
    r["services"].append({"name": "api", "kind": "app", "replicas": "1/3",
                          "tasks_failed": 4, "digest": "sha256:a"})
    r["findings"].extend(rules.findings_operational(r))
    dims = metrics.compute(r)["dimensions"]
    assert dims["operacao"]["failing"] == 1 and metrics.verdict(dims) == "yellow"


def test_replica_faltando_SEM_falha_nao_e_doenca():
    """2/3 sem erro = capacidade reduzida (ponto de impacto), não doença."""
    r = _report()
    r["services"].append({"name": "web2", "kind": "app", "replicas": "2/3",
                          "tasks_failed": 0, "digest": "sha256:a"})
    r["findings"].extend(rules.findings_operational(r))
    assert metrics.verdict(metrics.compute(r)["dimensions"]) == "green"


def test_no_fora_do_ar_derruba_a_saude():
    r = _report(node_state="Down")
    r["findings"].extend(rules.findings_operational(r))
    assert metrics.verdict(metrics.compute(r)["dimensions"]) == "red"


def test_cluster_impecavel_fica_verde():
    r = {"nodes": [{"hostname": "n1", "state": "Ready", "availability": "Active"}],
         "services": [{"name": "web", "kind": "proxy", "replicas": "2/2", "digest": "sha256:a"},
                      {"name": "db", "kind": "banco", "replicas": "3/3", "digest": "sha256:b"}],
         "findings": []}
    dims = metrics.compute(r)["dimensions"]
    assert metrics.verdict(dims) == "green" and dims["disponibilidade"]["note"] == "green"


# ---------------------------------------------------------------- achados esperados
def test_finding_esperado_nao_pesa_na_nota_de_seguranca():
    r = _report()
    r["findings"] = [{"rule_id": "SEC_DOCKER_SOCK_EXPECTED", "severity": "low",
                      "object": "cadvisor", "expected": True}]
    dims = metrics.compute(r)["dimensions"]
    assert dims["seguranca"]["note"] == "green" and dims["seguranca"]["expected"] == 1


def test_group_findings_manda_esperados_pro_fim():
    fs = [{"rule_id": "SEC_DOCKER_SOCK_EXPECTED", "severity": "low", "object": "a", "expected": True},
          {"rule_id": "SEC_PRIVILEGED", "severity": "high", "object": "b"}]
    assert metrics.group_findings(fs)[0]["rule_id"] == "SEC_PRIVILEGED"


# ---------------------------------------------------------------- dimensões
def test_dimensoes_calculam_percentuais():
    d = metrics.compute(_report())["dimensions"]
    assert d["disponibilidade"]["spof_stateful"] == ["db"] and d["disponibilidade"]["ha_pct"] == 50
    assert d["higiene"]["pinned_pct"] == 50 and d["higiene"]["nonroot_pct"] == 50


def test_top_offenders_normaliza_task_id():
    fs = [{"rule_id": "X", "severity": "med", "object": "svc.1.abc"},
          {"rule_id": "Y", "severity": "med", "object": "svc"}]
    assert metrics.top_offenders(fs)[0] == {"object": "svc", "findings": 2}


def test_job_falhando_nao_conta_como_saude():
    """Um migrate que roda e sai não deixa o cluster doente."""
    r = _report()
    r["services"].append({"name": "app_migrate", "kind": "app", "replicas": "0/1",
                          "tasks_failed": 1, "mode": "replicated", "digest": "sha256:a"})
    dims = metrics.compute(r)["dimensions"]
    assert dims["operacao"]["failing"] == 0 and metrics.verdict(dims) == "green"


def test_zero_replicas_falhando_e_vermelho_parcial_e_amarelo():
    fora = _report()
    fora["services"].append({"name": "api", "kind": "app", "replicas": "0/2",
                             "tasks_failed": 3, "digest": "sha256:a"})
    d1 = metrics.compute(fora)["dimensions"]
    assert d1["operacao"]["down"] == ["api"] and metrics.verdict(d1) == "red"

    parcial = _report()
    parcial["services"].append({"name": "web2", "kind": "app", "replicas": "2/3",
                                "tasks_failed": 2, "digest": "sha256:a"})
    d2 = metrics.compute(parcial)["dimensions"]
    assert d2["operacao"]["partial"] == ["web2"] and metrics.verdict(d2) == "yellow"

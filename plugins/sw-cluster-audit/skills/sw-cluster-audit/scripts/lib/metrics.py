"""Métricas derivadas (determinísticas): notas por dimensão, higiene e top ofensores.

Princípio: **saúde do cluster = operação** (está rodando?). Postura de segurança e higiene são
dimensões separadas — importantes, mas não derrubam a saúde de um cluster que está de pé.
"""
from collections import Counter

from lib.rules import is_job_service

STATEFUL = {"banco", "fila", "cache/fila", "cache", "busca"}
CRITICAL_PATH = {"ingress/proxy", "proxy", "api-gateway"}


def _desired_replicas(rep):
    try:
        return int(str(rep).split("/")[1])
    except (ValueError, IndexError, AttributeError):
        return None


def _pct(x, total):
    return round(100 * x / total) if total else 0


def _sem_replica(svc):
    """0 réplicas rodando com desejado > 0 — está fora do ar."""
    try:
        run_, des = str(svc.get("replicas")).split("/")
        return int(des) > 0 and int(run_) == 0
    except (ValueError, AttributeError):
        return False


def _abaixo_do_desejado(svc):
    """running < desired (e desired > 0) — divergência do que foi pedido."""
    try:
        run_, des = str(svc.get("replicas")).split("/")
        return int(des) > 0 and int(run_) < int(des)
    except (ValueError, AttributeError):
        return False


def compute(report):
    services = report.get("services")
    services = services if isinstance(services, list) else []
    findings = report.get("findings") or []
    n = len(services)

    ops = [f for f in findings if str(f.get("rule_id", "")).startswith("OPS_")]
    sec = [f for f in findings if str(f.get("rule_id", "")).startswith("SEC_")]
    # achados "esperados" (docker.sock em ferramenta de monitoramento, job concluído) não pesam
    sec_real = [f for f in sec if not f.get("expected")]
    ops_real = [f for f in ops if not f.get("expected")]

    # SAÚDE = só o que está QUEBRADO AGORA. Serviço parado de forma estável e réplica
    # faltando sem erro NÃO são doença — viram pontos de impacto (lib/impact.py).
    nodes_down = sum(1 for f in ops_real if f.get("rule_id") == "OPS_NODE_DOWN")
    stopped = {f["object"] for f in ops_real if f.get("rule_id") == "OPS_SERVICE_STOPPED"}
    # Falha ativa = abaixo do desejado E falhando agora. Jobs ficam de fora (terminar é o
    # comportamento correto deles). Distingue "fora do ar" (0 réplicas) de "parcial".
    ativos = [s for s in services if not is_job_service(s) and s.get("tasks_failed")]
    fora_do_ar = {s.get("name") for s in ativos if _sem_replica(s)}
    parciais = {s.get("name") for s in ativos if _abaixo_do_desejado(s) and not _sem_replica(s)}
    falhando = fora_do_ar | parciais
    sec_high = sum(1 for f in sec_real if f.get("severity") == "high")
    sec_med = sum(1 for f in sec_real if f.get("severity") == "med")

    root_objs = {f["object"] for f in findings if f.get("rule_id") == "SEC_USER_ROOT"}
    pinned = sum(1 for s in services if s.get("digest"))
    non_root = sum(1 for s in services if s.get("name") not in root_objs)
    with_limits = sum(1 for s in services
                      if (s.get("limits") or {}).get("nano_cpus") or (s.get("limits") or {}).get("mem_bytes"))
    with_hc = sum(1 for s in services if s.get("has_healthcheck"))

    ha, spof_stateful, spof_critical = 0, [], []
    for s in services:
        des = _desired_replicas(s.get("replicas"))
        kind = s.get("kind")
        if des and des > 1:
            ha += 1
        elif kind in STATEFUL:
            spof_stateful.append(s.get("name"))
        elif kind in CRITICAL_PATH:
            spof_critical.append(s.get("name"))

    ha_pct, nonroot_pct, pinned_pct = _pct(ha, n), _pct(non_root, n), _pct(pinned, n)

    if n == 0:
        # nada foi coletado: honestidade > alarme. Sem dados não se afirma nota nenhuma.
        unknown = {"note": "unknown"}
        return {"services_total": 0,
                "dimensions": {k: dict(unknown) for k in
                               ("operacao", "disponibilidade", "seguranca", "higiene")},
                "top_offenders": []}

    dims = {
        # OPERAÇÃO — a saúde de verdade: só fica vermelho se algo está fora do ar.
        "operacao": {
            "services_up": n - len(stopped), "services_total": n,
            "stopped": len(stopped), "failing": len(falhando), "nodes_down": nodes_down,
            "down": sorted(fora_do_ar), "partial": sorted(parciais),
            "note": ("red" if (nodes_down or fora_do_ar)
                     else ("yellow" if parciais else "green")),
        },
        # DISPONIBILIDADE — risco se algo cair (não é falha atual).
        "disponibilidade": {
            "ha_pct": ha_pct, "spof_stateful": spof_stateful, "spof_critical": spof_critical,
            "note": "red" if ha_pct == 0 else ("yellow" if (spof_stateful or spof_critical) else "green"),
        },
        # SEGURANÇA — postura; "esperados" não contam.
        "seguranca": {
            "high": sec_high, "med": sec_med,
            "expected": sum(1 for f in sec if f.get("expected")),
            "note": "red" if sec_high else ("yellow" if sec_med else "green"),
        },
        # HIGIENE — boas práticas de imagem/usuário.
        "higiene": {
            "pinned_pct": pinned_pct, "nonroot_pct": nonroot_pct,
            "limits_pct": _pct(with_limits, n), "healthcheck_pct": _pct(with_hc, n),
            "note": "red" if (nonroot_pct < 25 and pinned_pct < 50)
                    else ("yellow" if (nonroot_pct < 80 or pinned_pct < 90) else "green"),
        },
    }
    return {"services_total": n, "dimensions": dims, "top_offenders": top_offenders(sec_real)}


def verdict(dims):
    """Veredito de SAÚDE do cluster.

    A saúde reflete APENAS operação — o que está quebrado agora:
      red    = nó fora do ar, ou serviço com 0 réplicas falhando (algo está FORA DO AR).
      yellow = serviço parcialmente degradado e falhando (serve, mas não converge).
      green  = tudo que deve rodar está rodando.
    Risco (SPOF), pendência (serviço parado) e higiene NÃO derrubam a saúde: viram
    "pontos de impacto". Um cluster com 1 réplica de banco funciona 100% — é risco, não doença.
    """
    op = (dims.get("operacao") or {}).get("note", "green")
    return op if op in ("unknown", "red", "yellow") else "green"


def top_offenders(findings, k=5):
    c = Counter((f.get("object") or "").split(".")[0] for f in findings if f.get("object"))
    return [{"object": o, "findings": qtd} for o, qtd in c.most_common(k)]


def group_findings(findings):
    """Agrupa por rule_id: {rule_id, severity, count, objects[], expected}."""
    by = {}
    for f in findings:
        rid = f.get("rule_id")
        g = by.setdefault(rid, {"rule_id": rid, "severity": f.get("severity"),
                                "fix": f.get("fix"), "expected": bool(f.get("expected")),
                                "count": 0, "objects": []})
        g["count"] += 1
        if len(g["objects"]) < 50:
            g["objects"].append(f.get("object"))
    order = {"high": 0, "med": 1, "low": 2}
    # esperados vão pro fim (são informativos)
    return sorted(by.values(), key=lambda g: (g["expected"], order.get(g["severity"], 9), -g["count"]))

"""Métricas derivadas (determinísticas): notas por dimensão, higiene e top ofensores.

Princípio: **saúde do cluster = operação** (está rodando?). Postura de segurança e higiene são
dimensões separadas — importantes, mas não derrubam a saúde de um cluster que está de pé.
"""
from collections import Counter

STATEFUL = {"banco", "fila", "cache/fila", "cache", "busca"}
CRITICAL_PATH = {"ingress/proxy", "proxy", "api-gateway"}


def _desired_replicas(rep):
    try:
        return int(str(rep).split("/")[1])
    except (ValueError, IndexError, AttributeError):
        return None


def _pct(x, total):
    return round(100 * x / total) if total else 0


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

    ops_high = sum(1 for f in ops_real if f.get("severity") == "high")
    ops_med = sum(1 for f in ops_real if f.get("severity") == "med")
    stopped = {f["object"] for f in ops_real if f.get("rule_id") == "OPS_SERVICE_STOPPED"}
    sec_high = sum(1 for f in sec_real if f.get("severity") == "high")
    sec_med = sum(1 for f in sec_real if f.get("severity") == "med")

    root_objs = {f["object"] for f in findings if f.get("rule_id") == "SEC_USER_ROOT"}
    pinned = sum(1 for s in services if s.get("digest"))
    non_root = sum(1 for s in services if s.get("name") not in root_objs)

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
            "stopped": len(stopped), "degraded": ops_med - len(stopped), "nodes_down": ops_high,
            "note": "red" if ops_high else ("yellow" if ops_med else "green"),
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
            "note": "red" if (nonroot_pct < 25 and pinned_pct < 50)
                    else ("yellow" if (nonroot_pct < 80 or pinned_pct < 90) else "green"),
        },
    }
    return {"services_total": n, "dimensions": dims, "top_offenders": top_offenders(sec_real)}


def verdict(dims):
    """Veredito de SAÚDE do cluster.

    red    = algo REALMENTE fora do ar (nó down, serviço sem réplica). Só isso é "crítico".
    yellow = está rodando, mas com ressalvas conhecidas (réplica degradada, SPOF, achado de
             segurança crítico). Risco ≠ falha.
    green  = rodando, redundante e sem achado crítico.
    """
    op = (dims.get("operacao") or {}).get("note", "green")
    if op == "unknown":
        return "unknown"                     # sem dados → não afirma nada
    if op == "red":
        return "red"
    av = (dims.get("disponibilidade") or {}).get("note", "green")
    sec = (dims.get("seguranca") or {}).get("note", "green")
    if op == "yellow" or av not in ("green", "unknown") or sec == "red":
        return "yellow"
    return "green"


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

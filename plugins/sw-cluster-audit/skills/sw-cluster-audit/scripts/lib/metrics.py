"""Métricas derivadas (determinísticas) a partir dos fatos do report: notas por dimensão,
higiene e top ofensores. NÃO é análise (isso é do agente) — são números objetivos."""
from collections import Counter

STATEFUL = {"banco", "fila", "cache/fila", "cache", "busca"}


def _desired_replicas(rep):
    """'2/2' -> 2 ; '0/1' -> 1 ; None/estranho -> None."""
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

    highs = sum(1 for f in findings if f.get("severity") == "high")
    meds = sum(1 for f in findings if f.get("severity") == "med")
    root_objs = {f["object"] for f in findings if f.get("rule_id") == "SEC_USER_ROOT"}

    pinned = sum(1 for s in services if s.get("digest"))
    non_root = sum(1 for s in services if s.get("name") not in root_objs)

    ha = 0
    spof_stateful = []
    for s in services:
        des = _desired_replicas(s.get("replicas"))
        if des and des > 1:
            ha += 1
        elif s.get("kind") in STATEFUL:
            spof_stateful.append(s.get("name"))

    dims = {
        "seguranca": {"high": highs, "med": meds,
                      "note": "red" if highs else ("yellow" if meds else "green")},
        "disponibilidade": {"ha_pct": _pct(ha, n), "spof_stateful": spof_stateful,
                            "note": "red" if spof_stateful else ("yellow" if _pct(ha, n) < 50 else "green")},
        "higiene": {"pinned_pct": _pct(pinned, n), "nonroot_pct": _pct(non_root, n),
                    "note": "red" if _pct(non_root, n) < 40 else ("yellow" if _pct(pinned, n) < 60 else "green")},
    }
    return {"services_total": n, "dimensions": dims, "top_offenders": top_offenders(findings)}


def top_offenders(findings, k=5):
    # normaliza o objeto (service.slot.taskid → service) pra não duplicar o mesmo serviço
    c = Counter((f.get("object") or "").split(".")[0] for f in findings if f.get("object"))
    return [{"object": o, "findings": qtd} for o, qtd in c.most_common(k)]


def group_findings(findings):
    """Agrupa por rule_id: {rule_id, severity, count, objects[]} — pro relatório amigável."""
    by = {}
    for f in findings:
        rid = f.get("rule_id")
        g = by.setdefault(rid, {"rule_id": rid, "severity": f.get("severity"),
                                "fix": f.get("fix"), "count": 0, "objects": []})
        g["count"] += 1
        if len(g["objects"]) < 50:
            g["objects"].append(f.get("object"))
    order = {"high": 0, "med": 1, "low": 2}
    return sorted(by.values(), key=lambda g: (order.get(g["severity"], 9), -g["count"]))

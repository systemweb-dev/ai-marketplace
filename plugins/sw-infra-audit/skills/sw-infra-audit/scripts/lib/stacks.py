"""Agrupamento por stack — no Swarm os services nascem como `<stack>_<service>`.

Serve pra o relatório mostrar cada aplicação junta (ex.: todo o `challenge-api` num bloco),
em vez de 56 services soltos numa lista.
"""

def stack_of(service_name):
    """'challenge-api_database' -> 'challenge-api'. Sem '_' → o próprio nome (avulso)."""
    if not service_name:
        return "(sem nome)"
    return service_name.split("_", 1)[0] if "_" in service_name else service_name


def short_name(service_name):
    """'challenge-api_database' -> 'database' (nome curto dentro do stack)."""
    if not service_name or "_" not in service_name:
        return service_name
    return service_name.split("_", 1)[1]


def _desired(rep):
    try:
        return int(str(rep).split("/")[1])
    except (ValueError, IndexError, AttributeError):
        return None


def group(report):
    """Agrupa services + findings por stack.

    Retorna lista ordenada (mais findings primeiro) de:
      {stack, services[], findings_high, findings_med, has_ingress, kinds[], routes[]}
    """
    services = report.get("services")
    services = services if isinstance(services, list) else []
    findings = report.get("findings") or []

    # findings por stack (o object pode ser 'stack_svc' ou 'stack_svc.slot.taskid')
    fcount = {}
    for f in findings:
        st = stack_of((f.get("object") or "").split(".")[0])
        b = fcount.setdefault(st, {"high": 0, "med": 0, "low": 0})
        b[f.get("severity", "low")] = b.get(f.get("severity", "low"), 0) + 1

    groups = {}
    for s in services:
        st = stack_of(s.get("name"))
        g = groups.setdefault(st, {"stack": st, "services": [], "kinds": [], "routes": [],
                                   "findings_high": 0, "findings_med": 0, "spofs": []})
        g["services"].append(s)
        kind = s.get("kind") or "app"
        if kind not in g["kinds"]:
            g["kinds"].append(kind)
        for k, v in (s.get("routing_labels") or {}).items():
            if k.endswith(".rule") and v not in g["routes"]:
                g["routes"].append(v)
        des = _desired(s.get("replicas"))
        if des == 1 and kind in {"banco", "fila", "cache/fila", "cache", "busca", "ingress/proxy", "proxy"}:
            g["spofs"].append(s.get("name"))

    for st, g in groups.items():
        c = fcount.get(st) or {}
        g["findings_high"] = c.get("high", 0)
        g["findings_med"] = c.get("med", 0)
        g["note"] = "red" if g["findings_high"] or g["spofs"] else ("yellow" if g["findings_med"] else "green")

    return sorted(groups.values(),
                  key=lambda g: (-g["findings_high"], -len(g["spofs"]), -g["findings_med"], g["stack"]))

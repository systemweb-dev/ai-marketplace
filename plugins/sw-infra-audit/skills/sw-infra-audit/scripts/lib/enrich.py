"""Enriquecimento com métricas de RUNTIME a partir de uma fonte confirmada (ex.: Prometheus).

Genérico por design: uma TABELA de queries declara o que buscar; o que não existir na fonte
vira ausência silenciosa (a seção fica n/a). Nada aqui é obrigatório — sem endpoint confirmado,
o relatório continua saindo só com os fatos do Docker.
"""
import json
import re
from urllib.parse import quote

from lib.http_get import get

# (chave normalizada, PromQL, label da série que identifica o serviço, transformação)
# `by_service=True` → resultado vira {serviço: valor}; senão é um número do cluster.
PROM_QUERIES = [
    ("requests_24h",
     'sum by (service) (increase(traefik_service_requests_total[24h]))', "service", "int"),
    ("errors_5xx_24h",
     'sum by (service) (increase(traefik_service_requests_total{code=~"5.."}[24h]))', "service", "int"),
    ("p95_ms",
     'histogram_quantile(0.95, sum by (le, service) '
     '(rate(traefik_service_request_duration_seconds_bucket[24h]))) * 1000', "service", "ms"),
    ("queue_ready",
     'sum by (queue) (rabbitmq_queue_messages_ready)', "queue", "int"),
    ("queue_consumers",
     'sum by (queue) (rabbitmq_queue_consumers)', "queue", "int"),
    ("cpu_pct",
     'sum by (container_label_com_docker_swarm_service_name) '
     '(rate(container_cpu_usage_seconds_total[5m])) * 100',
     "container_label_com_docker_swarm_service_name", "pct"),
    ("mem_bytes",
     'sum by (container_label_com_docker_swarm_service_name) (container_memory_usage_bytes)',
     "container_label_com_docker_swarm_service_name", "int"),
]


def _clean_key(v):
    """'ai2contract-api@docker' -> 'ai2contract-api' ; mantém o resto como veio."""
    return (v or "").split("@")[0]


def _fmt(kind, raw):
    try:
        f = float(raw)
    except (TypeError, ValueError):
        return None
    if kind == "int":
        return int(round(f))
    if kind == "pct":
        return round(f, 1)
    if kind == "ms":
        return round(f, 1)
    return f


def prom_query(base_url, promql, allowed_hosts, timeout=8):
    """Executa uma query instantânea no Prometheus. Retorna a lista de results ou None."""
    url = f"{base_url.rstrip('/')}/api/v1/query?query={quote(promql)}"
    body = get(url, allowed_hosts, timeout)
    if not body:
        return None
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if data.get("status") != "success":
        return None
    return ((data.get("data") or {}).get("result")) or []


def probe(base_url, allowed_hosts, timeout=5):
    """Confere se a fonte responde e é um Prometheus utilizável."""
    return prom_query(base_url, "up", allowed_hosts, timeout) is not None


# ---------------------------------------------------------------- exporters (/metrics em texto)
_LINE = re.compile(r'^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+(?P<value>[^\s]+)$')
_LBL = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')

# Métricas instantâneas úteis quando SÓ há exporter (sem servidor Prometheus pra janelas de 24h).
EXPORTER_METRICS = {
    "rabbitmq_queue_messages_ready": ("queue_ready", "queue", "int"),
    "rabbitmq_queue_consumers": ("queue_consumers", "queue", "int"),
    "traefik_service_requests_total": ("requests_total", "service", "int"),
    "container_memory_usage_bytes": ("mem_bytes", "container_label_com_docker_swarm_service_name", "int"),
}


def parse_text_metrics(body):
    """Parser do formato texto do Prometheus → [(nome, {labels}, valor)]."""
    out = []
    for line in (body or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE.match(line)
        if not m:
            continue
        labels = dict(_LBL.findall(m.group("labels") or ""))
        try:
            out.append((m.group("name"), labels, float(m.group("value"))))
        except ValueError:
            continue
    return out


def collect_from_exporter(base_url, allowed_hosts, timeout=8):
    """Coleta de um endpoint /metrics cru (exporter). Soma séries com o mesmo label-alvo."""
    body = get(f"{base_url.rstrip('/')}/metrics", allowed_hosts, timeout)
    if not body:
        return {}
    out = {}
    for name, labels, value in parse_text_metrics(body):
        spec = EXPORTER_METRICS.get(name)
        if not spec:
            continue
        key, label, fmt = spec
        target = _clean_key(labels.get(label))
        if not target:
            continue
        bucket = out.setdefault(key, {})
        bucket[target] = bucket.get(target, 0) + value
    # normaliza os números só no fim (soma antes, formata depois)
    for key, series in out.items():
        fmt = next(s[2] for s in EXPORTER_METRICS.values() if s[0] == key)
        out[key] = {k: _fmt(fmt, v) for k, v in series.items()}
    return out


def probe_exporter(base_url, allowed_hosts, timeout=5):
    """Confere se o endpoint serve métricas no formato texto do Prometheus."""
    body = get(f"{base_url.rstrip('/')}/metrics", allowed_hosts, timeout)
    return bool(body) and bool(parse_text_metrics(body))


def collect_runtime(base_url, allowed_hosts, timeout=8):
    """Roda a tabela de queries. Retorna {chave: {nome_da_serie: valor}} só do que existir."""
    out = {}
    for key, promql, label, fmt in PROM_QUERIES:
        res = prom_query(base_url, promql, allowed_hosts, timeout)
        if not res:
            continue
        series = {}
        for item in res:
            name = _clean_key((item.get("metric") or {}).get(label))
            val = _fmt(fmt, (item.get("value") or [None, None])[1])
            if name and val is not None:
                series[name] = val
        if series:
            out[key] = series
    return out


def attach(report, runtime):
    """Casa as séries com os services do report (por nome) e anexa em `service['runtime']`.

    Casamento: nome exato, senão sufixo/prefixo (traefik usa o nome do router, que costuma ser
    o nome do service do stack). O que não casar vira métrica de cluster em `runtime_cluster`.
    """
    services = report.get("services")
    services = services if isinstance(services, list) else []
    names = {s.get("name"): s for s in services}
    leftovers = {}

    for key, series in (runtime or {}).items():
        for sname, val in series.items():
            svc = names.get(sname)
            if svc is None:                     # tenta casar por sufixo (stack_service vs router)
                cand = [n for n in names if n and (n.endswith(f"_{sname}") or sname in n)]
                svc = names[cand[0]] if len(cand) == 1 else None
            if svc is None:
                leftovers.setdefault(key, {})[sname] = val
                continue
            svc.setdefault("runtime", {})[key] = val

    if leftovers:
        report["runtime_cluster"] = leftovers
    return report

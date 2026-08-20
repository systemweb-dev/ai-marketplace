"""Descoberta de fontes de métrica a partir dos FATOS já coletados (sem rede).

A skill é genérica: em vez de cravar um endpoint, ela olha o que existe no cluster
(services + portas publicadas + host do context) e PROPÕE os melhores candidatos.
Quem decide é o usuário (confirmação) — o `collect.py` só faz GET no que for confirmado.
"""
import re

# Ordem de preferência: agregador que já faz scrape > exporter dedicado > API do serviço.
# kind_hint: como interpretar o endpoint depois (parser/queries).
CANDIDATES = [
    # (regex na imagem, kind_hint, porta padrão, path de teste, prioridade, o que entrega)
    (r"prom/prometheus|prometheus", "prometheus", 9090, "/api/v1/query?query=up", 1,
     "requests, latência, filas, CPU/mem — tudo que o Prometheus já coleta"),
    (r"traefik", "traefik_metrics", 8080, "/metrics", 2,
     "requests/erros do Traefik (exige --metrics.prometheus=true)"),
    (r"rabbitmq", "rabbitmq_prom", 15692, "/metrics", 2,
     "mensagens em fila, consumers (plugin rabbitmq_prometheus)"),
    (r"cadvisor", "cadvisor", 8080, "/metrics", 3,
     "CPU/memória por container"),
    (r"node-exporter|node_exporter", "node_exporter", 9100, "/metrics", 3,
     "CPU/mem/disco por nó"),
]


def _published_ports(svc):
    out = []
    for p in (svc.get("ports") or []):
        if isinstance(p, dict):
            if p.get("host_port"):
                out.append(int(p["host_port"]))
        elif p:
            try:
                out.append(int(p))
            except (TypeError, ValueError):
                pass
    return out


def host_from_context_endpoint(endpoint):
    """'tcp://203.0.113.10:2376' -> '203.0.113.10'. unix:// -> 'localhost'."""
    if not endpoint:
        return None
    if endpoint.startswith("unix://") or endpoint.startswith("npipe://"):
        return "localhost"
    m = re.match(r"^[a-z]+://([^:/]+)", endpoint)
    return m.group(1) if m else None


def propose(report, host):
    """Retorna candidatos [{service, kind_hint, url, priority, provides, published}] ordenados.

    `published=True` quando a porta está publicada no host (alcançável de fora do cluster).
    """
    services = report.get("services")
    services = services if isinstance(services, list) else []
    found = []
    for s in services:
        # o identificador pode estar na imagem, na TAG ou no nome do service — casos reais:
        # 'portainer/template-swarm-monitoring:prometheus-v2.44.0' tem 'prometheus' só na tag.
        haystack = " ".join(str(x or "").lower() for x in
                            (s.get("image"), s.get("tag"), s.get("name")))
        ports = _published_ports(s)
        for pattern, hint, default_port, path, prio, provides in CANDIDATES:
            if not re.search(pattern, haystack):
                continue
            port = default_port if default_port in ports else (ports[0] if ports else default_port)
            found.append({
                "service": s.get("name"), "kind_hint": hint,
                "url": f"http://{host}:{port}{path}" if host else None,
                "priority": prio, "provides": provides,
                "published": bool(ports),
            })
            break
    # publicados primeiro, depois prioridade
    return sorted(found, key=lambda c: (not c["published"], c["priority"], c["service"] or ""))


def best(report, host):
    """O melhor candidato único (ou None) — o que a skill sugere por padrão."""
    props = propose(report, host)
    return props[0] if props else None

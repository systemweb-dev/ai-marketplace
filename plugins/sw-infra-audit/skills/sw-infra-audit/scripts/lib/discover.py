"""Descoberta de fontes de métrica a partir dos FATOS já coletados (sem rede).

A skill é genérica: em vez de cravar um endpoint, ela olha o que existe no cluster
(services + portas publicadas + host do context) e PROPÕE os melhores candidatos.
Quem decide é o usuário (confirmação) — o `collect.py` só faz GET no que for confirmado.
"""
import re

from lib import produtos

# Quem expõe métrica, e em que porta, vive em `references/produtos.toml` — era a terceira
# lista deste código chaveada por nome de imagem. A `prioridade` de lá ordena a preferência:
# agregador que já faz scrape (1) > exporter dedicado (3).
#
# O casamento é por TRECHO, não por expressão: expressão num arquivo de dados é código, e o
# resto da skill recusa isso. `node-exporter|node_exporter` virou dois trechos no mesmo bloco.


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
        for trechos, hint, default_port, path, prio, provides in produtos.candidatos_de_metrica():
            if not any(t in haystack for t in trechos):
                continue
            # A porta é SEMPRE a do catálogo. Cair na primeira porta publicada parecia
            # esperto e propunha endereço que não serve métrica: o traefik publica 80/443
            # (a métrica é a 8080) e o rabbitmq publica a 15672, que é a UI de administração
            # (a métrica é a 15692 do plugin). Melhor propor a porta certa e avisar que ela
            # não está publicada do que propor com confiança uma porta que devolve HTML.
            found.append({
                "service": s.get("name"), "kind_hint": hint,
                "url": f"http://{host}:{default_port}{path}" if host else None,
                "priority": prio, "provides": provides,
                # `published` é sobre a porta DA MÉTRICA, não sobre o serviço publicar algo
                "published": default_port in ports,
            })
            break
    # publicados primeiro, depois prioridade
    return sorted(found, key=lambda c: (not c["published"], c["priority"], c["service"] or ""))


def best(report, host):
    """O melhor candidato único (ou None) — o que a skill sugere por padrão."""
    props = propose(report, host)
    return props[0] if props else None

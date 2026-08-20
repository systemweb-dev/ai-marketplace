"""Pontos de impacto — cenário → consequência.

Responde a pergunta que o usuário realmente faz olhando o relatório: **o que me derruba, e o
quanto dói?** Nada aqui é "saúde": são riscos e pendências de um cluster que está funcionando.

Tudo determinístico, derivado dos fatos. O agente pode enriquecer o texto, mas os cenários e a
contagem saem daqui.
"""
STATEFUL = {"banco", "fila", "cache/fila", "cache", "busca"}
INGRESS = {"ingress/proxy", "proxy", "api-gateway"}

_ORDER = {"alto": 0, "médio": 1, "baixo": 2}


def _p(cenario, consequencia, impacto, esforco, alvos=(), fix=None):
    return {"cenario": cenario, "consequencia": consequencia, "impacto": impacto,
            "esforco": esforco, "alvos": list(alvos)[:8], "fix": fix}


def _replicas(rep):
    try:
        run_, des = str(rep).split("/")
        return int(run_), int(des)
    except (ValueError, AttributeError):
        return None, None


def build(report):
    """Lista de pontos de impacto, do que mais dói para o que menos dói."""
    services = report.get("services")
    services = services if isinstance(services, list) else []
    findings = report.get("findings") or []
    dims = report.get("dimensions") or {}
    pontos = []

    # ---- 1. perda de nó: quem roda com réplica única lá?
    por_no = {}
    for s in services:
        run_, des = _replicas(s.get("replicas"))
        if des == 1 and run_ == 1:
            for n in (s.get("nodes") or []):
                por_no.setdefault(n, []).append(s)

    for no, svcs in sorted(por_no.items(), key=lambda kv: -len(kv[1])):
        rotas = sum(len([k for k in (s.get("routing_labels") or {}) if k.endswith(".rule")])
                    for s in svcs)
        ingress = [s for s in svcs if s.get("kind") in INGRESS]
        estado = [s for s in svcs if s.get("kind") in STATEFUL]
        if not svcs:
            continue
        partes = []
        if ingress:
            apps = sum(1 for x in services if x.get("routing_labels"))
            partes.append(f"o ingress cai e as {apps} aplicações roteadas ficam inacessíveis")
        if estado:
            partes.append(f"{len(estado)} serviço(s) com estado saem do ar sem failover "
                          f"({', '.join(s['name'] for s in estado[:3])})")
        outros = len(svcs) - len(ingress) - len(estado)
        if outros > 0:
            partes.append(f"mais {outros} serviço(s) sem réplica de reserva")
        pontos.append(_p(
            f"Se o nó {no} cair",
            "; ".join(partes) + ".",
            "alto" if (ingress or estado) else "médio",
            "alto" if ingress else "médio",
            [s["name"] for s in svcs],
            "distribuir réplicas entre nós; para o ingress, promover outro manager e "
            "compartilhar o storage do ACME antes de escalar" if ingress else
            "subir uma segunda réplica onde o serviço permitir",
        ))

    # ---- 2. serviços parados (faxina, não incidente)
    parados = [f for f in findings if f.get("rule_id") == "OPS_SERVICE_STOPPED"]
    if parados:
        pontos.append(_p(
            f"Se algum dos {len(parados)} serviços parados deveria estar no ar",
            "é uma indisponibilidade que ninguém percebeu — nenhum alarme dispara para um "
            "serviço que o Swarm não está tentando subir.",
            "alto", "baixo", [f["object"] for f in parados],
            "confirmar um a um: se era para rodar, subir; se foi desativado, remover o service",
        ))

    # ---- 3. capacidade reduzida (abaixo do desejado, mas sem falha)
    degradados = [s for s in services
                  if (lambda r, d: d and r and 0 < r < d)(*_replicas(s.get("replicas")))
                  and not s.get("tasks_failed")]
    if degradados:
        pontos.append(_p(
            "Se um nó cair enquanto há réplicas faltando",
            f"{len(degradados)} serviço(s) já rodam abaixo do configurado — a margem para "
            "absorver mais uma perda é menor do que você planejou.",
            "médio", "baixo",
            [f'{s["name"]} ({s.get("replicas")})' for s in degradados],
            "descobrir por que a réplica não é agendada (constraint, recurso ou porta em uso)",
        ))

    # ---- 4. recursos sem limite
    hig = dims.get("higiene") or {}
    if hig.get("limits_pct", 100) < 80:
        pontos.append(_p(
            "Se um container vazar memória ou disparar CPU",
            f"consome o nó inteiro e derruba os vizinhos — {100 - hig.get('limits_pct', 0)}% dos "
            "serviços rodam sem limite de CPU/memória.",
            "médio", "médio", (),
            "docker service update --limit-cpu 1 --limit-memory 512M <service>",
        ))

    # ---- 5. sem healthcheck
    if hig.get("healthcheck_pct", 100) < 60:
        pontos.append(_p(
            "Se uma aplicação travar sem morrer o processo",
            f"o Swarm continua achando que está viva e o tráfego segue sendo entregue — só "
            f"{hig.get('healthcheck_pct', 0)}% dos serviços têm healthcheck.",
            "médio", "médio", (),
            "docker service update --health-cmd '<comando>' --health-interval 30s <service>",
        ))

    # ---- 6. credencial de acesso ao daemon com validade muito longa
    tls = report.get("tls") or {}
    dias = tls.get("days_left") if isinstance(tls, dict) else None
    if isinstance(dias, int) and dias > 365 * 3:
        anos = dias // 365
        pontos.append(_p(
            "Se o certificado de cliente vazar (CI/CD, máquina de dev, backup)",
            f"quem tiver a cópia ganha acesso total ao daemon — que equivale a root no host — "
            f"por {anos} anos. Não há revogação neste modelo: a única saída é gerar uma CA nova "
            "e atualizar todos os clientes.",
            "alto", "médio", (),
            "manter o certificado só onde é necessário; para esteiras de CI, preferir chave SSH "
            "dedicada (revogável em uma linha) em vez de distribuir o cert do Docker",
        ))

    # ---- 7. superfície exposta (informativo: o mTLS ainda é a barreira)
    expostos = [f["object"] for f in findings if f.get("rule_id") == "SEC_PORT_EXPOSED"]
    if expostos:
        pontos.append(_p(
            "Se o firewall da nuvem permitir a porta publicada",
            "o serviço fica alcançável da internet. Para a API do Docker com --tlsverify o "
            "certificado de cliente continua barrando — o risco real está em quem tem cópia dele.",
            "baixo", "baixo", expostos,
            "publicar só na interface interna quando não houver consumidor externo",
        ))

    # ---- 8. imagem não fixada
    if hig.get("pinned_pct", 100) < 90:
        pontos.append(_p(
            "Se a tag de uma imagem for republicada",
            f"o próximo deploy sobe um código diferente do testado — {100 - hig.get('pinned_pct', 0)}% "
            "das imagens não têm digest fixo.",
            "baixo", "médio", (),
            "fixar tag imutável + digest (image@sha256:...)",
        ))

    # ---- 9. root
    if hig.get("nonroot_pct", 100) < 50:
        pontos.append(_p(
            "Se uma aplicação exposta for comprometida",
            f"o atacante já começa como root dentro do container — {100 - hig.get('nonroot_pct', 0)}% "
            "dos serviços rodam como root.",
            "médio", "médio", (),
            "definir USER não-root na imagem, começando pelos serviços expostos",
        ))

    pontos.sort(key=lambda x: (_ORDER.get(x["impacto"], 9), _ORDER.get(x["esforco"], 9)))
    return pontos

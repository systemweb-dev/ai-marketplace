"""Pontos de impacto — cenário → consequência.

Responde a pergunta que o usuário realmente faz olhando o relatório: **o que me derruba, e o
quanto dói?** Nada aqui é "saúde": são riscos e pendências de um cluster que está funcionando.

Tudo determinístico, derivado dos fatos. O agente pode enriquecer o texto, mas os cenários e a
contagem saem daqui.
"""
STATEFUL = {"banco", "fila", "cache/fila", "cache", "busca"}
INGRESS = {"ingress/proxy", "proxy", "api-gateway"}

_ORDER = {"alto": 0, "médio": 1, "baixo": 2}


def _p(cenario, consequencia, impacto, esforco, alvos=(), fix=None, plano=()):
    """Um ponto de impacto.

    `plano` é o que diferencia conselho de instrução: lista ordenada de
    {passo, comando, porque}. Cada passo precisa ser executável como está — "distribuir
    réplicas entre nós" não é passo, é desejo.
    """
    return {"cenario": cenario, "consequencia": consequencia, "impacto": impacto,
            "esforco": esforco, "alvos": list(alvos)[:8], "fix": fix,
            "plano": [dict(x) for x in plano]}


def _step(passo, comando=None, porque=None):
    return {"passo": passo, "comando": comando, "porque": porque}


def _managers(nodes):
    return [n for n in (nodes or []) if str(n.get("role") or "").lower() in ("manager", "leader")]


def _acme_local(svc):
    """Traefik com storage do ACME em volume/bind LOCAL não escala: cada réplica emitiria
    o próprio certificado, batendo no rate limit do Let's Encrypt e servindo certs diferentes."""
    for m in (svc.get("mounts") or []):
        alvo = str(m.get("target") or "")
        if "letsencrypt" in alvo.lower() or "acme" in alvo.lower():
            return m
    return None


def _plano_ingress(ingress, nodes, n_apps):
    """Plano concreto pra tirar o ingress de ponto único — os passos dependem do que existe."""
    mgrs = _managers(nodes)
    nome = ingress.get("name")
    passos = []

    if len(mgrs) < 3:
        faltam = 3 - len(mgrs)
        alvos = [n.get("hostname") for n in (nodes or [])
                 if str(n.get("role") or "").lower() == "worker"][:faltam]
        passos.append(_step(
            f"Promover {faltam} worker(s) a manager (quórum de 3)",
            "docker node promote " + " ".join(alvos or ["<worker>"]),
            f"Hoje há {len(mgrs)} manager. Com um só, perder esse nó derruba o control plane "
            "junto: você não consegue nem rodar `service update` pra consertar. Três managers "
            "toleram a perda de um. Isso também faz a constraint `node.role == manager` do "
            f"{nome} passar a ser satisfeita em 3 nós em vez de 1."))

    acme = _acme_local(ingress)
    if acme:
        origem = acme.get("source") or "volume local"
        passos.append(_step(
            "Tirar a emissão de certificado de dentro do ingress",
            "# opção A (recomendada em cloud): terminar TLS num load balancer gerenciado\n"
            "#   e deixar o ingress só roteando HTTP — o storage do ACME deixa de existir.\n"
            "# opção B: manter o ACME, porém com desafio DNS-01 e storage compartilhado\n"
            "#   entre as réplicas (mais peças, mais chance de conflito de escrita).",
            f"É este o bloqueio pra escalar: o {nome} guarda o ACME em `{origem}`, que é "
            "local do nó. Com 2 réplicas, cada uma emitiria o próprio certificado — rate "
            "limit do Let's Encrypt e clientes recebendo certs diferentes. Escalar antes de "
            "resolver isso quebra o TLS."))

    passos.append(_step(
        f"Só então escalar o {nome}",
        f"docker service update --replicas 2 {nome}\n"
        f"docker service ps {nome}   # confirmar que caíram em nós diferentes",
        "Com o storage resolvido e 3 managers, a segunda réplica tem onde rodar."))

    passos.append(_step(
        "Colocar um load balancer na frente apontando pra todos os nós",
        "# alvos: todos os nós do cluster, na porta publicada do ingress\n"
        "# health check: HTTP na mesma porta — o LB tira do rodízio o nó que não responder",
        "A malha de roteamento do Swarm entrega em qualquer nó, mas ela precisa de uma réplica "
        f"viva pra entregar. Por isso o LB sozinho não resolveria: sem o passo anterior, ele só "
        "distribuiria tráfego entre nós que encaminham para um ingress que não existe mais."))
    return passos


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

    nodes = report.get("nodes") or []
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
        n_apps = sum(1 for x in services if x.get("routing_labels"))
        plano = _plano_ingress(ingress[0], nodes, n_apps) if ingress else []
        if estado:
            plano.append(_step(
                "Tratar os serviços com estado à parte — LB e réplica não resolvem",
                "# 1. confirme que o volume de cada um tem backup testado (restaurar, não só copiar)\n"
                "# 2. para os que suportam, avalie serviço gerenciado ou replicação nativa\n"
                "# 3. o que sobrar sem HA: fixe o nó e documente o RTO honesto\n"
                + "\n".join(f"docker service ps {s['name']}" for s in estado[:3]),
                "Subir uma segunda réplica de banco não dá alta disponibilidade — dá duas "
                "instâncias brigando pelo mesmo volume. Aqui a proteção real é backup restaurável "
                f"({', '.join(s['name'] for s in estado[:3])}); redundância exige replicação do "
                "próprio motor, que é decisão de arquitetura, não de `service update`."))
        if not plano:
            plano.append(_step(
                "Subir uma segunda réplica dos serviços sem reserva",
                "\n".join(f"docker service update --replicas 2 {s['name']}" for s in svcs[:3]),
                "São serviços sem estado — escalar é seguro e a malha do Swarm já balanceia."))

        pontos.append(_p(
            f"Se o nó {no} cair",
            "; ".join(partes) + ".",
            "alto" if (ingress or estado) else "médio",
            "alto" if ingress else "médio",
            [s["name"] for s in svcs],
            plano=plano,
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

"""Coletor do alvo docker — o miolo é o `assemble_report` que já existia, sem mudança.

O que mudou é a moldura: ele recebe um alvo, devolve o bloco daquele alvo, e a URL de métricas
vem do alvo (nunca de descoberta). O schema interno continua o v1, em `docker_report.py`.
"""
from lib.redact import redact_container, redact_service, scrub_info, scrub_text
from lib.rules import (findings_for_workload, findings_operational,
                       findings_from_errors, findings_from_cert)
from lib.runner import run
import inspect
import json
from lib import cert, discover, enrich, impact, metrics
from lib.coletores.docker_report import na, new_report, split_image

DEFAULT_TIMEOUT = 15

_KINDS = [
    ("traefik", "ingress/proxy"), ("nginx", "proxy"), ("haproxy", "proxy"),
    ("envoy", "proxy"), ("caddy", "proxy"), ("kong", "api-gateway"),
    ("rabbitmq", "fila"), ("kafka", "fila/broker"), ("nats", "fila/broker"),
    ("redis", "cache/fila"), ("memcached", "cache"),
    ("postgres", "banco"), ("mysql", "banco"), ("mariadb", "banco"), ("mongo", "banco"),
    ("elasticsearch", "busca"), ("opensearch", "busca"),
    ("prometheus", "observabilidade"), ("grafana", "observabilidade"), ("loki", "observabilidade"),
    ("minio", "object-storage"),
]


def detect_kind(image):
    img = (image or "").lower()
    for key, kind in _KINDS:
        if key in img:
            return kind
    return "app"


# ---------------------------------------------------------------- gate de context (seam testável)
def _jlines(out):
    return [json.loads(l) for l in (out or "").splitlines() if l.strip()]


def _first(out):
    """`docker inspect` retorna uma lista JSON; pega o 1º objeto (ou None)."""
    if not out:
        return None
    data = json.loads(out)
    return data[0] if isinstance(data, list) and data else (data or None)


def _state(t):
    """Primeira palavra de CurrentState: 'Running 3 days ago' -> 'Running'."""
    return str(t.get("CurrentState") or "").split()[0] if t.get("CurrentState") else ""


def _completed_job(tasks):
    """Terminou com sucesso E não há nada rodando agora.

    Só `any(Complete)` seria largo demais: um worker que roda 4/4 e reinicia saindo com 0
    também acumula tasks Complete, e ficaria isento do check de serviço parado no dia em
    que caísse de verdade. Exigir zero tasks Running fecha essa brecha.
    """
    if not tasks:
        return False
    return (any(_state(t) == "Complete" for t in tasks)
            and not any(_state(t) == "Running" for t in tasks))


def assemble_report(run_fn, timeout, context, generated_at, connected_node):
    """Monta o report.json a partir de comandos read-only.

    DÍVIDA TÉCNICA (code review 19/08/2026): complexidade ciclomática 25 (limite 10).
    Quando for mexer aqui, extrair _collect_nodes / _collect_services / _collect_containers.
    Adiado de propósito: é o coração da coleta e os testes cobrem o comportamento atual. `run_fn(cmd, timeout) -> str|None`."""
    r = new_report(generated_at=generated_at, context=context)
    errs = []                       # motivos reais das falhas (TLS expirado, timeout, etc.)

    # Detecta a assinatura UMA vez. Usar try/except TypeError aqui seria perigoso: um
    # TypeError vindo de DENTRO do runner (após o comando já ter rodado) causaria uma
    # segunda execução — e ainda mascararia o bug real.
    _accepts_errors = len(inspect.signature(run_fn).parameters) >= 3

    def _run(cmd, t=timeout):
        return run_fn(cmd, t, errs) if _accepts_errors else run_fn(cmd, t)

    def _why(default):
        return errs[0]["reason"] if errs else default
    r["scope"] = {"connected_node": connected_node, "container_checks_cover": "only_connected_node"}

    # --- health / info (cluster)
    info = _first_json(_run(["docker", "info", "--format", "{{json .}}"]))
    if info is not None:
        r["cluster"]["engine_version"] = info.get("ServerVersion")
        r["cluster"]["swarm"] = (info.get("Swarm", {}) or {}).get("LocalNodeState") == "active"
        r["health"]["info"] = scrub_info(info)
    else:
        r["not_collected"].append({"what": "docker info", "reason": _why("indisponível")})

    # --- nodes (swarm; capacidade — uso real não existe sem métricas)
    nodes_raw = _run(["docker", "node", "ls", "--format", "{{json .}}"])

    # UMA chamada traz as tasks de TODOS os nós (campos .Node/.Name/.CurrentState/.Error).
    # Evita 1 chamada por serviço/nó — em cluster remoto isso era o gargalo.
    all_tasks = []
    if nodes_raw:
        node_ids = [n.get("ID") or n.get("Hostname") for n in _jlines(nodes_raw)]
        node_ids = [x for x in node_ids if x]
        if node_ids:
            # Chamada mais pesada da coleta (todas as tasks do cluster de uma vez).
            # Precisa de folga: com dezenas de serviços passa fácil dos 15s padrão.
            raw = _run(["docker", "node", "ps", *node_ids,
                        "--format", "{{json .}}", "--no-trunc"], max(timeout * 4, 60))
            if raw is None:
                tasks_ok = False
                r["not_collected"].append({"what": "tasks por nó/serviço",
                                           "reason": _why("listagem de tasks indisponível")})
            else:
                tasks_ok = True
                all_tasks = _jlines(raw)
        else:
            tasks_ok = False
    else:
        tasks_ok = False

    def _task_err(t):
        """Erro de task é texto livre do daemon — sanitiza e trunca (ver redact.scrub_text)."""
        return scrub_text(t.get("Error") or t.get("CurrentState") or "")

    def _is_recent(t):
        """CurrentState traz 'X minutes/hours/days ago' — só conta falha das últimas ~24h."""
        cs = str(t.get("CurrentState") or "").lower()
        return not any(w in cs for w in (" days ago", " weeks ago", " months ago", " years ago"))

    # o `docker node ps` com vários nós repete a listagem — dedupe pelo ID da task
    seen_ids, deduped = set(), []
    for t in all_tasks:
        tid = t.get("ID")
        if tid and tid in seen_ids:
            continue
        seen_ids.add(tid)
        deduped.append(t)
    all_tasks = deduped

    tasks_by_node, tasks_by_service = {}, {}
    for t in all_tasks:
        tasks_by_node.setdefault(t.get("Node"), []).append(t)
        tasks_by_service.setdefault(str(t.get("Name") or "").split(".")[0], []).append(t)
    if nodes_raw is None:
        r["nodes"] = na(_why("node ls indisponível (não-swarm)"))
    else:
        for n in _jlines(nodes_raw):
            nid = n.get("ID") or n.get("Hostname")
            insp = _first(_run(["docker", "node", "inspect", nid])) or {}
            desc = insp.get("Description", {}) or {}
            res = desc.get("Resources", {}) or {}
            plat = desc.get("Platform", {}) or {}
            mgr = insp.get("ManagerStatus") or {}
            # tasks deste nó (do índice montado numa única chamada)
            tasks = tasks_by_node.get(n.get("Hostname"), [])
            running = sum(1 for t in tasks if _state(t) == "Running")
            failed = [t for t in tasks if _state(t) in ("Failed", "Rejected") and _is_recent(t)]
            r["nodes"].append({
                "hostname": n.get("Hostname"), "role": n.get("ManagerStatus") or "worker",
                "availability": n.get("Availability"), "state": n.get("Status"),
                "leader": bool(mgr.get("Leader", False)),
                "reachability": mgr.get("Reachability"),
                "engine": (desc.get("Engine", {}) or {}).get("EngineVersion"),
                "platform": f'{plat.get("OS", "")}/{plat.get("Architecture", "")}'.strip("/"),
                "capacity": {"nano_cpus": res.get("NanoCPUs"), "mem_bytes": res.get("MemoryBytes")},
                "tasks_running": running if tasks_ok else None,
                "tasks_failed": len(failed) if tasks_ok else None,
                "failed_examples": [f'{t.get("Name")}: {_task_err(t)}' for t in failed[:3]],
            })
        r["not_collected"].append({"what": "uso de CPU/mem em tempo real por nó",
                                   "reason": "requer Prometheus/cAdvisor (capacidade é reportada)"})

    # --- disco (nó conectado): imagens/containers/volumes/cache e o que dá pra recuperar
    df_raw = _run(["docker", "system", "df", "--format", "{{json .}}"])
    df = _jlines(df_raw)
    if df:
        r["disk"] = [{"tipo": d.get("Type"), "total": d.get("TotalCount"), "ativo": d.get("Active"),
                      "tamanho": d.get("Size"), "recuperavel": d.get("Reclaimable")} for d in df]
    else:
        r["disk"] = na(_why("docker system df indisponível"))

    # --- services (cluster-wide — achados de segurança confiáveis)
    svc_raw = _run(["docker", "service", "ls", "--format", "{{json .}}"])
    if svc_raw is None:
        r["services"] = na(_why("service ls indisponível (não-swarm)"))
    else:
        for s in _jlines(svc_raw):
            name = s.get("Name") or s.get("ID")
            insp = _first(_run(["docker", "service", "inspect", name]))
            if insp is None:
                continue
            red = redact_service(insp)
            img = split_image(red.get("image"))
            # tasks deste service (mesmo índice) — pega crash-loop que o "replicas ok" esconde
            tasks = tasks_by_service.get(name, [])
            failed = ([t for t in tasks if _state(t) in ("Failed", "Rejected") and _is_recent(t)]
                      if tasks_ok else [])
            completed_job = _completed_job(tasks)
            r["services"].append({
                "name": red.get("name"), "image": img["image"], "tag": img["tag"],
                "digest": img["digest"], "replicas": s.get("Replicas"), "ports": red.get("ports"),
                "env_keys": red.get("env_keys"),        # só CHAVES (seguro), útil no relatório
                "kind": detect_kind(red.get("image")),  # tipo detectado (traefik/fila/banco/…)
                "routing_labels": red.get("routing_labels") or {},
                "limits": red.get("limits"), "reservations": red.get("reservations"),
                "has_healthcheck": red.get("has_healthcheck"),
                "constraints": red.get("constraints"), "updated_at": red.get("updated_at"),
                # tipo/origem/destino apenas (redact_service já filtra) — o storage do ACME
                # do ingress é o que decide se ele pode ou não ser escalado
                "mounts": red.get("mounts"),
                "mode": red.get("mode"),
                "tasks_failed": len(failed) if tasks_ok else None, "completed_job": completed_job,
                "nodes": sorted({t.get("Node") for t in tasks
                                 if _state(t) == "Running" and t.get("Node")}),
                "failed_reason": _task_err(failed[0]) if failed else None,
            })
            r["findings"].extend(findings_for_workload({**red, **img}, scope="cluster-wide"))

    # --- containers (SÓ o nó conectado — escopo anotado em scope)
    ps_raw = _run(["docker", "ps", "--format", "{{json .}}"])
    if ps_raw is None:
        r["not_collected"].append({"what": "containers (docker ps)", "reason": _why("indisponível")})
    for c in _jlines(ps_raw):
        insp = _first(_run(["docker", "container", "inspect", c.get("ID") or c.get("Names")]))
        if insp is None:
            continue
        red = redact_container(insp)
        img = split_image(red.get("image"))
        red["name"] = c.get("Names") or c.get("ID")
        r["findings"].extend(findings_for_workload({**red, **img}, scope=connected_node))

    # --- networks
    net_raw = _run(["docker", "network", "ls", "--format", "{{json .}}"])
    for n in _jlines(net_raw):
        r["networks"].append({"name": n.get("Name"), "driver": n.get("Driver"), "scope": n.get("Scope")})

    # --- secrets / configs (NOMES only)
    r["secrets"] = [{"name": s.get("Name")} for s in _jlines(_run(["docker", "secret", "ls", "--format", "{{json .}}"]))]
    r["configs"] = [{"name": c.get("Name")} for c in _jlines(_run(["docker", "config", "ls", "--format", "{{json .}}"]))]

    # --- counts + verdict
    r["health"]["counts"] = {
        "nodes": len(r["nodes"]) if isinstance(r["nodes"], list) else 0,
        "services": len(r["services"]) if isinstance(r["services"], list) else 0,
        "findings": len(r["findings"]),
    }
    # achados OPERACIONAIS (nó fora, réplica não convergida) — é o que define a saúde
    r["findings"].extend(findings_operational(r))
    # validade dos certificados TLS do context (só as datas; nunca a chave privada)
    try:
        tls = cert.check(context)
    except OSError:
        tls = None
    r["tls"] = tls if tls else na("context não usa TLS (ssh:// ou socket local)")
    r["findings"].extend(findings_from_cert(tls, context))
    m = metrics.compute(r)                 # métricas determinísticas por dimensão + top ofensores
    r["dimensions"] = m["dimensions"]
    r["top_offenders"] = m["top_offenders"]
    r["health"]["verdict"] = metrics.verdict(m["dimensions"])   # saúde = só falha ativa
    r["impact_points"] = impact.build(r)                        # risco/pendência (cenário → consequência)
    r["health"]["counts"]["findings"] = len(r["findings"])
    if errs:
        r["collection_errors"] = errs[:10]
        r["findings"].extend(findings_from_errors(errs, context))
        m = metrics.compute(r)
        r["dimensions"], r["top_offenders"] = m["dimensions"], m["top_offenders"]
        r["health"]["verdict"] = metrics.verdict(m["dimensions"])
    return r


def host_from_context(ctx, timeout):
    """Descobre o host do cluster pelo endpoint do context (pra propor URLs de métricas)."""
    out = run(["docker", "context", "inspect", ctx], timeout, context=ctx)
    try:
        data = json.loads(out)[0] if out else {}
        endpoint = ((data.get("Endpoints") or {}).get("docker") or {}).get("Host")
    except (ValueError, IndexError, AttributeError, TypeError):
        return None
    return discover.host_from_context_endpoint(endpoint)


# o miolo v1 fala green/yellow/red/unknown; o relatório v2 fala no vocabulário do inventário
SAUDE_POR_VEREDITO = {"green": "🟢", "yellow": "🟡", "red": "🔴", "unknown": "sem dados"}
# o v1 fala crit/high/med/low; o relatório v2 usa o vocabulário do coletor http também
SEVERIDADE_POR_V1 = {"crit": "critical", "critical": "critical", "high": "high",
                     "med": "medium", "medium": "medium", "low": "low", "info": "info"}


def coletar(alvo, contexto):
    """Traduz o alvo docker para o bloco do report v2.

    A URL de métricas vem do ALVO, nunca de descoberta: a descoberta alcançaria host que o usuário
    não declarou, e isso quebraria a regra de egress. Aqui ela nem é chamada — vive no modo
    configurar, como sugestão para você colar no alvos.toml.
    """
    from lib import report as report_mod
    from lib import http_get
    from lib.runner import run

    nao_coletado = []
    def rodar(cmd, timeout, errors=None):
        """Todo comando deste alvo vai para o context DELE — e só para ele."""
        return run(cmd, timeout, errors, context=alvo["context"])

    bruto = assemble_report(run_fn=rodar, timeout=contexto["timeout"], context=alvo["context"],
                            generated_at=contexto.get("at", ""), connected_node=None)

    url = alvo.get("metricas_url")
    if not url:
        nao_coletado.append(report_mod.na(
            "métricas: o alvo não declara `metricas_url` — rode `configurar.py alvos --sugerir` "
            "para ver candidatos e colar um no alvos.toml"))
    else:
        permitido = [http_get.destino(url)]
        base = url.split("/api/")[0].split("/metrics")[0].rstrip("/")
        runtime = None
        if enrich.probe(base, permitido, contexto["timeout"]):
            runtime = enrich.collect_runtime(base, permitido, contexto["timeout"])
        elif enrich.probe_exporter(base, permitido, contexto["timeout"]):
            runtime = enrich.collect_from_exporter(base, permitido, contexto["timeout"])
        if runtime is not None:
            bruto["runtime"] = runtime
            enrich.attach(bruto, runtime)      # liga requests/erros a cada serviço
        else:
            nao_coletado.append(report_mod.na(
                f"métricas: {base} não respondeu como Prometheus nem como exporter"))

    achados = [{"regra": f.get("rule_id"), "objeto": f.get("object"),
                "severidade": SEVERIDADE_POR_V1.get(f.get("severity"), "info"),
                "detalhe": f.get("evidence"), "alvo": alvo["nome"]}
               for f in bruto.get("findings", [])]
    fatos = {chave: bruto.get(chave) for chave in
             ("nodes", "services", "networks", "secrets", "configs", "stacks", "tls", "scope",
              "runtime")
             if bruto.get(chave) is not None}

    # o que o miolo não conseguiu ver precisa chegar ao relatório, senão "sem achados" mente
    for item in bruto.get("not_collected", []):
        nao_coletado.append(report_mod.na(f"{item.get('what')}: {item.get('reason')}"))
    for erro in bruto.get("collection_errors", []):
        if isinstance(erro, dict):                 # {"cmd": ..., "reason": ...}
            nao_coletado.append(report_mod.na(f"{erro.get('cmd')}: {erro.get('reason')}"))
        else:
            nao_coletado.append(report_mod.na(str(erro)))

    return {"saude": SAUDE_POR_VEREDITO.get((bruto.get("health") or {}).get("verdict"), "sem dados"),
            "dimensoes": bruto.get("dimensions", {}),
            "fatos": fatos, "achados": achados, "nao_coletado": nao_coletado}


def _first_json(out):
    return json.loads(out) if out else None

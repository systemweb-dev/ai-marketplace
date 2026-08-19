#!/usr/bin/env python3
"""collect.py — coleta READ-ONLY de um cluster Docker → report.json (schema v1).

Uso:
  python3 collect.py --context <ctx> --out <dir> [--timeout 15] [--node <nome>] [--at <iso>]

- Seleciona o cluster via env DOCKER_CONTEXT (a flag `--context`/`-H` do docker é bloqueada de
  propósito pela allowlist — viraria "noun").
- Todo comando passa por lib.runner.run (allowlist + timeout + args-array).
- Nenhum import de rede.
"""
import argparse
import inspect
import json
import os
import sys

from lib.runner import run
from lib.redact import redact_container, redact_service, scrub_info, scrub_text
from lib.rules import (findings_for_workload, findings_operational,
                       findings_from_errors, findings_from_cert)
from lib.report import new_report, na, split_image
from lib import metrics, discover, enrich, cert
from lib.http_get import host_of

DEFAULT_TIMEOUT = 15
GITIGNORE_LINE = "docs/infra/"

# Detecção genérica de tipo de componente pela imagem (substring). Fallback: "app".
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
def confirm_context(ctx, confirmed):
    """Confirma auditar `ctx`. No modo skill, o agente passa `--confirmed-context <ctx>` DEPOIS
    de confirmar o alvo com o usuário via AskUserQuestion. Sem confirmação (ou divergente do
    `--context`) → False → a coleta aborta. NENHUM comando roda antes deste gate (FF5)."""
    return bool(confirmed) and confirmed == ctx


# ---------------------------------------------------------------- gitignore (antes de escrever)
def ensure_gitignore(repo, line=GITIGNORE_LINE):
    """Garante `line` no .gitignore de `repo` (idempotente). Chamar ANTES de escrever qualquer arquivo."""
    gi = os.path.join(str(repo), ".gitignore")
    existing = []
    if os.path.isfile(gi):
        with open(gi, encoding="utf-8") as f:
            existing = f.read().splitlines()
    if line not in existing:
        with open(gi, "a", encoding="utf-8") as f:
            if existing and existing[-1].strip() != "":
                f.write("\n")
            f.write(line + "\n")


# ---------------------------------------------------------------- coleta (função pura, run injetável)
def _jlines(out):
    return [json.loads(l) for l in (out or "").splitlines() if l.strip()]


def _first(out):
    """`docker inspect` retorna uma lista JSON; pega o 1º objeto (ou None)."""
    if not out:
        return None
    data = json.loads(out)
    return data[0] if isinstance(data, list) and data else (data or None)


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

    def _state(t):
        return str(t.get("CurrentState") or "").split()[0] if t.get("CurrentState") else ""

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
            # job de execução única: o Swarm marca a task como Complete (sinal infalível,
            # independente do nome do serviço)
            completed_job = any(_state(t) == "Complete" for t in tasks)
            r["services"].append({
                "name": red.get("name"), "image": img["image"], "tag": img["tag"],
                "digest": img["digest"], "replicas": s.get("Replicas"), "ports": red.get("ports"),
                "env_keys": red.get("env_keys"),        # só CHAVES (seguro), útil no relatório
                "kind": detect_kind(red.get("image")),  # tipo detectado (traefik/fila/banco/…)
                "routing_labels": red.get("routing_labels") or {},
                "limits": red.get("limits"), "reservations": red.get("reservations"),
                "has_healthcheck": red.get("has_healthcheck"),
                "constraints": red.get("constraints"), "updated_at": red.get("updated_at"),
                "mode": red.get("mode"),
                "tasks_failed": len(failed) if tasks_ok else None, "completed_job": completed_job,
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
    r["health"]["verdict"] = metrics.verdict(m["dimensions"])   # saúde = operação (não higiene)
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
    out = run(["docker", "context", "inspect", ctx], timeout)
    try:
        data = json.loads(out)[0] if out else {}
        endpoint = ((data.get("Endpoints") or {}).get("docker") or {}).get("Host")
    except (ValueError, IndexError, AttributeError, TypeError):
        return None
    return discover.host_from_context_endpoint(endpoint)


def _finding_key(f):
    return (f.get("rule_id"), f.get("object"))


def find_previous_report(out_dir):
    """Acha o report.json da auditoria anterior (dir irmão mais recente que não o atual)."""
    parent = os.path.dirname(os.path.abspath(os.path.expanduser(out_dir)))
    cur = os.path.basename(os.path.normpath(out_dir))
    if not os.path.isdir(parent):
        return None
    sibs = sorted(d for d in os.listdir(parent)
                  if d != cur and os.path.isfile(os.path.join(parent, d, "report.json")))
    if not sibs:
        return None
    prev_dir = sibs[-1]
    try:
        with open(os.path.join(parent, prev_dir, "report.json"), encoding="utf-8") as f:
            return {"stamp": prev_dir, "report": json.load(f)}
    except (OSError, ValueError):
        return None


def diff_findings(prev, cur_report):
    """Compara findings (por rule_id+object) com a auditoria anterior.

    Devolve também as LISTAS — assim o relatório mostra o que foi resolvido (histórico visível)
    e marca os achados novos, em vez de só um número.
    """
    prev_keys = {_finding_key(f) for f in (prev["report"].get("findings") or [])}
    cur_keys = {_finding_key(f) for f in (cur_report.get("findings") or [])}
    resolved, new = prev_keys - cur_keys, cur_keys - prev_keys
    fmt = lambda ks: sorted(f"{r} · {o}" for r, o in ks if r)
    return {"vs": prev["stamp"],
            "resolved": len(resolved), "new": len(new),
            "resolved_items": fmt(resolved)[:40],
            "new_keys": [list(k) for k in sorted(new, key=lambda k: (k[0] or "", k[1] or ""))]}


def _first_json(out):
    return json.loads(out) if out else None


# (o veredito de saúde vive em lib.metrics.verdict — baseado em OPERAÇÃO, não em higiene)


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--context", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--node", default="connected")
    ap.add_argument("--confirmed-context", default=None,
                    help="repita o context aqui pra confirmar a auditoria (gate de segurança)")
    ap.add_argument("--metrics", choices=["auto", "off"], default="auto",
                    help="auto (padrão): descobre sozinho as fontes de métrica DENTRO do cluster "
                         "confirmado e usa as que responderem. off: nenhuma requisição de rede.")
    ap.add_argument("--metrics-endpoint", action="append", default=[],
                    help="força um endpoint específico (opcional). Só é aceito se estiver no mesmo "
                         "host do context confirmado.")
    ap.add_argument("--discover-only", action="store_true",
                    help="só coleta os fatos e imprime os candidatos a fonte de métricas (sem rede)")
    ap.add_argument("--at", required=True, help="timestamp ISO (o caller passa; scripts não geram data)")
    args = ap.parse_args(argv)

    # GATE: nenhum comando roda antes da confirmação do context-alvo (FF5).
    if not confirm_context(args.context, args.confirmed_context):
        print("Coleta abortada: context não confirmado.", file=sys.stderr)
        return 2

    os.environ["DOCKER_CONTEXT"] = args.context  # seleção via env (não a flag bloqueada)
    out_dir = os.path.expanduser(args.out)
    ensure_gitignore(_repo_root(out_dir))         # .gitignore ANTES de escrever
    os.makedirs(out_dir, exist_ok=True)

    report = assemble_report(run, args.timeout, args.context, args.at, args.node)

    # --- fontes de métricas: descobre (sem rede) e só consulta o que foi CONFIRMADO ---
    endpoint_host = host_from_context(args.context, args.timeout)
    report["metrics_candidates"] = discover.propose(report, endpoint_host)
    if args.discover_only:
        print(json.dumps({"host": endpoint_host, "candidates": report["metrics_candidates"]},
                         ensure_ascii=False, indent=2))
        return 0
    if args.metrics == "off":
        report["not_collected"].append(
            {"what": "métricas de runtime (requests, filas, CPU/mem)", "reason": "--metrics off"})
    elif not endpoint_host:
        report["not_collected"].append(
            {"what": "métricas de runtime", "reason": "não foi possível determinar o host do cluster"})
    else:
        # SEGURANÇA: a allowlist é derivada — só o host do context que o usuário já confirmou.
        # Nada fixo no código e nenhum host de fora do cluster auditado é alcançável.
        allowed = [endpoint_host]
        urls = args.metrics_endpoint or [c["url"] for c in report["metrics_candidates"]
                                         if c.get("url") and c.get("published")]
        used = []
        for url in urls:
            if host_of(url) != endpoint_host:
                report["not_collected"].append(
                    {"what": f"métricas de {host_of(url)}", "reason": "host fora do cluster confirmado"})
                continue
            base = url.split("/api/")[0].split("/metrics")[0].rstrip("/")
            if base in used:
                continue
            # 1ª escolha: servidor Prometheus (janelas de 24h, taxas). 2ª: exporter cru (/metrics).
            if enrich.probe(base, allowed, args.timeout):
                runtime = enrich.collect_runtime(base, allowed, args.timeout)
            elif enrich.probe_exporter(base, allowed, args.timeout):
                runtime = enrich.collect_from_exporter(base, allowed, args.timeout)
            else:
                report["not_collected"].append(
                    {"what": f"métricas em {base}", "reason": "não respondeu ou não expõe métricas"})
                continue
            if runtime:
                enrich.attach(report, runtime)
                used.append(base)
        report["metrics_source"] = used or None
        if not used:
            report["not_collected"].append(
                {"what": "requests/filas/uso de recursos",
                 "reason": "nenhuma fonte de métricas respondeu no cluster"})

    prev = find_previous_report(out_dir)                 # diff com a auditoria anterior (se houver)
    if prev:
        report["history"] = diff_findings(prev, report)
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(os.path.join(out_dir, "report.json"))
    return 0


def _repo_root(path):
    """Sobe até achar um .git; se não achar, usa o cwd."""
    p = os.path.abspath(path)
    while p != os.path.dirname(p):
        if os.path.isdir(os.path.join(p, ".git")):
            return p
        p = os.path.dirname(p)
    return os.getcwd()


if __name__ == "__main__":
    sys.exit(main())

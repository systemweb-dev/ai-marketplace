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
import json
import os
import sys

from lib.runner import run
from lib.redact import redact_container, redact_service, scrub_info
from lib.rules import findings_for_workload
from lib.report import new_report, na, split_image
from lib import metrics

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
        existing = open(gi, encoding="utf-8").read().splitlines()
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
    """Monta o report.json a partir de comandos read-only. `run_fn(cmd, timeout) -> str|None`."""
    r = new_report(generated_at=generated_at, context=context)
    r["scope"] = {"connected_node": connected_node, "container_checks_cover": "only_connected_node"}

    # --- health / info (cluster)
    info = _first_json(run_fn(["docker", "info", "--format", "{{json .}}"], timeout))
    if info is not None:
        r["cluster"]["engine_version"] = info.get("ServerVersion")
        r["cluster"]["swarm"] = (info.get("Swarm", {}) or {}).get("LocalNodeState") == "active"
        r["health"]["info"] = scrub_info(info)
    else:
        r["not_collected"].append({"what": "docker info", "reason": "indisponível/timeout"})

    # --- nodes (swarm; capacidade — uso real não existe sem métricas)
    nodes_raw = run_fn(["docker", "node", "ls", "--format", "{{json .}}"], timeout)
    if nodes_raw is None:
        r["nodes"] = na("node ls indisponível (não-swarm ou timeout)")
    else:
        for n in _jlines(nodes_raw):
            insp = _first(run_fn(["docker", "node", "inspect", n.get("ID") or n.get("Hostname")], timeout))
            desc = (insp or {}).get("Description", {}) or {}
            res = desc.get("Resources", {}) or {}
            r["nodes"].append({
                "hostname": n.get("Hostname"), "role": n.get("ManagerStatus") or "worker",
                "availability": n.get("Availability"), "state": n.get("Status"),
                "leader": bool(((insp or {}).get("ManagerStatus") or {}).get("Leader", False)),
                "capacity": {"nano_cpus": res.get("NanoCPUs"), "mem_bytes": res.get("MemoryBytes")},
            })
        r["not_collected"].append({"what": "uso de CPU/mem/disco por nó", "reason": "requer Prometheus/cAdvisor"})

    # --- services (cluster-wide — achados de segurança confiáveis)
    svc_raw = run_fn(["docker", "service", "ls", "--format", "{{json .}}"], timeout)
    if svc_raw is None:
        r["services"] = na("service ls indisponível (não-swarm ou timeout)")
    else:
        for s in _jlines(svc_raw):
            name = s.get("Name") or s.get("ID")
            insp = _first(run_fn(["docker", "service", "inspect", name], timeout))
            if insp is None:
                continue
            red = redact_service(insp)
            img = split_image(red.get("image"))
            r["services"].append({
                "name": red.get("name"), "image": img["image"], "tag": img["tag"],
                "digest": img["digest"], "replicas": s.get("Replicas"), "ports": red.get("ports"),
                "env_keys": red.get("env_keys"),        # só CHAVES (seguro), útil no relatório
                "kind": detect_kind(red.get("image")),  # tipo detectado (traefik/fila/banco/…)
                "routing_labels": red.get("routing_labels") or {},
            })
            r["findings"].extend(findings_for_workload({**red, **img}, scope="cluster-wide"))

    # --- containers (SÓ o nó conectado — escopo anotado em scope)
    ps_raw = run_fn(["docker", "ps", "--format", "{{json .}}"], timeout)
    if ps_raw is None:
        r["not_collected"].append({"what": "containers (docker ps)", "reason": "indisponível/timeout"})
    for c in _jlines(ps_raw):
        insp = _first(run_fn(["docker", "container", "inspect", c.get("ID") or c.get("Names")], timeout))
        if insp is None:
            continue
        red = redact_container(insp)
        img = split_image(red.get("image"))
        red["name"] = c.get("Names") or c.get("ID")
        r["findings"].extend(findings_for_workload({**red, **img}, scope=connected_node))

    # --- networks
    net_raw = run_fn(["docker", "network", "ls", "--format", "{{json .}}"], timeout)
    for n in _jlines(net_raw):
        r["networks"].append({"name": n.get("Name"), "driver": n.get("Driver"), "scope": n.get("Scope")})

    # --- secrets / configs (NOMES only)
    r["secrets"] = [{"name": s.get("Name")} for s in _jlines(run_fn(["docker", "secret", "ls", "--format", "{{json .}}"], timeout))]
    r["configs"] = [{"name": c.get("Name")} for c in _jlines(run_fn(["docker", "config", "ls", "--format", "{{json .}}"], timeout))]

    # --- counts + verdict
    r["health"]["counts"] = {
        "nodes": len(r["nodes"]) if isinstance(r["nodes"], list) else 0,
        "services": len(r["services"]) if isinstance(r["services"], list) else 0,
        "findings": len(r["findings"]),
    }
    r["health"]["verdict"] = _verdict(r["findings"])
    m = metrics.compute(r)                 # métricas determinísticas por dimensão + top ofensores
    r["dimensions"] = m["dimensions"]
    r["top_offenders"] = m["top_offenders"]
    return r


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
    """Compara findings (por rule_id+object) com a auditoria anterior."""
    prev_keys = {_finding_key(f) for f in (prev["report"].get("findings") or [])}
    cur_keys = {_finding_key(f) for f in (cur_report.get("findings") or [])}
    return {"vs": prev["stamp"],
            "resolved": len(prev_keys - cur_keys),
            "new": len(cur_keys - prev_keys)}


def _first_json(out):
    return json.loads(out) if out else None


def _verdict(findings):
    sev = {f.get("severity") for f in findings}
    if "high" in sev:
        return "red"
    if "med" in sev:
        return "yellow"
    return "green"


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--context", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--node", default="connected")
    ap.add_argument("--confirmed-context", default=None,
                    help="repita o context aqui pra confirmar a auditoria (gate de segurança)")
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

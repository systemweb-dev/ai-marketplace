#!/usr/bin/env python3
"""build_report.py — report.json (schema v1) → HTML self-contained (primário) → PDF (opt-in).

Uso: python3 build_report.py --dir <out_dir>   # lê <dir>/report.json, escreve relatorio.html [+ .pdf]

Sem imports de rede. O PDF é gerado só se houver Chromium/Chrome (headless, offline); senão,
entrega o HTML e avisa.
"""
import argparse
import html
import json
import os
import shutil
import subprocess
import sys

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "assets", "report-template", "template.html")

_VERDICT = {"green": ("🟢", "OK"), "yellow": ("🟡", "Atenção"), "red": ("🔴", "Crítico")}

CHROME_CANDIDATES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]


def _e(x):
    return html.escape("" if x is None else str(x))


def find_chromium():
    for c in CHROME_CANDIDATES:
        p = shutil.which(c)
        if p:
            return p
    return None


def _na_or(section, render_fn):
    """Se a seção é um marcador n/a, mostra o aviso; senão renderiza."""
    if isinstance(section, dict) and section.get("status") == "n/a":
        return f'<p class="muted">não coletado — {_e(section.get("reason"))}</p>'
    if not section:
        return '<p class="muted">nenhum.</p>'
    return render_fn(section)


def _fmt_ports(ports):
    out = []
    for p in (ports or []):
        if isinstance(p, dict):
            loc = f'{p.get("host_ip")}:{p.get("host_port")}' if p.get("host_ip") else (p.get("host_port") or "")
            out.append(f'{p.get("port")} → {loc}' if loc else str(p.get("port")))
        else:
            out.append(str(p))
    return ", ".join(out)


def _routing_summary(s):
    """Traefik: mostra as regras de roteamento (Host(...)); senão, as portas."""
    rl = s.get("routing_labels") or {}
    rules = [v for k, v in rl.items() if k.endswith(".rule")]
    return " · ".join(rules) if rules else _fmt_ports(s.get("ports"))


def _fmt_capacity(cap):
    cap = cap or {}
    cpus = cap.get("nano_cpus")
    mem = cap.get("mem_bytes")
    parts = []
    if cpus:
        parts.append(f"{cpus / 1e9:.0f} vCPU")
    if mem:
        parts.append(f"{mem / 1024 ** 3:.1f} GB")
    return " · ".join(parts) or "—"


def _table(headers, rows):
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_html(report):
    ctx = (report.get("cluster") or {}).get("context")
    engine = (report.get("cluster") or {}).get("engine_version")
    health = report.get("health") or {}
    verdict = health.get("verdict", "green")
    emoji, label = _VERDICT.get(verdict, ("⚪", "?"))
    scope = report.get("scope") or {}
    counts = health.get("counts") or {}

    cards = "".join(f'<div class="card"><div class="n">{_e(v)}</div><div class="l">{_e(k)}</div></div>'
                    for k, v in counts.items())

    findings = _na_or(report.get("findings"), lambda fs: _table(
        ["Sev", "Regra", "Objeto", "Evidência", "Correção", "Escopo"],
        [[f'<span class="badge {_e(f.get("severity"))}">{_e(f.get("severity"))}</span>',
          f'<code>{_e(f.get("rule_id"))}</code>', _e(f.get("object")), _e(f.get("evidence")),
          f'<span class="fix">{_e(f.get("fix"))}</span>', _e(f.get("scope"))] for f in fs]))

    nodes = _na_or(report.get("nodes"), lambda ns: _table(
        ["Host", "Role", "Disp.", "Estado", "Leader", "Capacidade"],
        [[_e(n.get("hostname")), _e(n.get("role")), _e(n.get("availability")), _e(n.get("state")),
          "sim" if n.get("leader") else "—", _e(_fmt_capacity(n.get("capacity")))]
         for n in ns]))

    services = _na_or(report.get("services"), lambda ss: _table(
        ["Service", "Imagem", "Réplicas", "Portas", "Env (chaves)"],
        [[_e(s.get("name")),
          _e(f'{s.get("image")}:{s.get("tag")}' + (f'@{s.get("digest")}' if s.get("digest") else "")),
          _e(s.get("replicas")),
          _e(_fmt_ports(s.get("ports"))),
          _e(", ".join(s.get("env_keys") or []))] for s in ss]))

    comp_an = report.get("components_analysis") or {}
    components = _na_or(report.get("services"), lambda ss: _table(
        ["Componente", "Tipo", "Roteamento / portas", "Análise"],
        [[_e(s.get("name")), f'<span class="badge low">{_e(s.get("kind") or "app")}</span>',
          _e(_routing_summary(s)), _e(comp_an.get(s.get("name"), "—"))] for s in ss]))

    networks = _na_or(report.get("networks"), lambda ns: _table(
        ["Rede", "Driver", "Scope"], [[_e(n.get("name")), _e(n.get("driver")), _e(n.get("scope"))] for n in ns]))

    nc = report.get("not_collected") or []
    not_collected = ("<br>Não coletado: " + "; ".join(f'{_e(x.get("what"))} ({_e(x.get("reason"))})' for x in nc)) if nc else ""
    sc = [s.get("name") for s in (report.get("secrets") or [])] + [c.get("name") for c in (report.get("configs") or [])]
    secrets_configs = _e(", ".join(sc)) if sc else "nenhum"

    repl = {
        "%%TITLE%%": _e(f"Auditoria de cluster — {ctx}"), "%%CONTEXT%%": _e(ctx), "%%ENGINE%%": _e(engine),
        "%%GENERATED_AT%%": _e(report.get("generated_at")), "%%SCOPE%%": _e(scope.get("container_checks_cover")),
        "%%VERDICT%%": _e(verdict), "%%VERDICT_EMOJI%%": emoji, "%%VERDICT_LABEL%%": _e(label),
        "%%CARDS%%": cards, "%%FINDINGS%%": findings, "%%NODES%%": nodes, "%%SERVICES%%": services,
        "%%COMPONENTS%%": components, "%%NETWORKS%%": networks,
        "%%CONNECTED_NODE%%": _e(scope.get("connected_node")),
        "%%NOT_COLLECTED%%": not_collected, "%%SECRETS_CONFIGS%%": secrets_configs,
    }
    page = open(TEMPLATE, encoding="utf-8").read()
    for k, v in repl.items():
        page = page.replace(k, v)
    return page


def build(report, out_dir):
    out_dir = os.path.expanduser(str(out_dir))
    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, "relatorio.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render_html(report))

    pdf_path = None
    chrome = find_chromium()
    if chrome:
        pdf_path = os.path.join(out_dir, "relatorio.pdf")
        try:
            subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                            "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}",
                            f"file://{os.path.abspath(html_path)}"],
                           check=True, capture_output=True, timeout=60)
        except (subprocess.SubprocessError, OSError):
            pdf_path = None
    return {"html": html_path, "pdf": pdf_path}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    args = ap.parse_args(argv)
    d = os.path.expanduser(args.dir)
    report = json.loads(open(os.path.join(d, "report.json"), encoding="utf-8").read())
    res = build(report, d)
    print(res["html"])
    if res["pdf"]:
        print(res["pdf"])
    else:
        print("PDF não gerado (sem Chromium) — HTML entregue.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

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

from lib import metrics
from lib.rule_meta import meta as rule_meta

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


def _list(items):
    items = [i for i in (items or []) if i]
    if not items:
        return '<p class="muted">—</p>'
    return "<ul>" + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>"


_DIM_LABEL = {"seguranca": "Segurança", "disponibilidade": "Disponibilidade", "higiene": "Higiene"}
_NOTE_BIG = {"green": "OK", "yellow": "Atenção", "red": "Crítico"}


def _dim_cards(dims):
    out = []
    for key in ("seguranca", "disponibilidade", "higiene"):
        d = (dims or {}).get(key) or {}
        note = d.get("note", "green")
        if key == "seguranca":
            desc = f'{d.get("high", 0)} críticos · {d.get("med", 0)} médios'
        elif key == "disponibilidade":
            desc = f'{d.get("ha_pct", 0)}% com HA · {len(d.get("spof_stateful") or [])} SPOF stateful'
        else:
            desc = f'{d.get("pinned_pct", 0)}% imagem fixa · {d.get("nonroot_pct", 0)}% non-root'
        out.append(f'<div class="dim {note}"><div class="t">{_DIM_LABEL[key]}</div>'
                   f'<div class="s">{_NOTE_BIG.get(note, "?")}</div><div class="d">{_e(desc)}</div></div>')
    return "".join(out)


def _recs(recs):
    if not recs:
        return '<p class="muted">Sem recomendações registradas. (o agente preenche `recommendations`)</p>'
    out = []
    for r in recs:
        imp = (r.get("impact") or "").lower()
        icl = "hi" if imp.startswith("alt") else ("mid" if imp.startswith(("méd", "med")) else "lo")
        out.append(f'<div class="rec"><div class="rt">{_e(r.get("title"))}</div>'
                   f'<div class="rw">{_e(r.get("why"))}</div><div class="tags">'
                   f'<span class="tag {icl}">impacto: {_e(r.get("impact") or "—")}</span>'
                   f'<span class="tag">esforço: {_e(r.get("effort") or "—")}</span></div></div>')
    return "".join(out)


def _findings_grouped(findings):
    if isinstance(findings, dict) and findings.get("status") == "n/a":
        return f'<p class="muted">não coletado — {_e(findings.get("reason"))}</p>'
    if not findings:
        return '<p class="muted">Nenhum achado. 🎉</p>'
    out = []
    for g in metrics.group_findings(findings):
        m = rule_meta(g["rule_id"])
        objs = g["objects"][:8]
        extra = g["count"] - len(objs)
        objs_txt = ", ".join(objs) + (f" … +{extra}" if extra > 0 else "")
        out.append(
            f'<div class="fgroup"><div class="fh">'
            f'<span class="badge {_e(g["severity"])}">{_e(g["severity"])}</span>'
            f'<strong>{_e(m["label"])}</strong> <code>{_e(g["rule_id"])}</code>'
            f'<span class="cnt">{g["count"]} afetados</span></div>'
            f'<div class="what">{_e(m["what"])}</div>'
            f'<div class="why"><strong>Por que importa:</strong> {_e(m["why"])}</div>'
            f'<div class="fix"><strong>Como corrigir:</strong> {_e(g.get("fix"))}</div>'
            f'<div class="objs">Afetados: {_e(objs_txt)}</div></div>')
    return "".join(out)


def render_html(report):
    ctx = (report.get("cluster") or {}).get("context")
    engine = (report.get("cluster") or {}).get("engine_version")
    verdict = (report.get("health") or {}).get("verdict", "green")
    emoji, label = _VERDICT.get(verdict, ("⚪", "?"))
    scope = report.get("scope") or {}

    summary = report.get("summary") or "Resumo ainda não escrito (o agente preenche `summary` com o porquê do veredito)."
    hist = report.get("history")
    history = (f'<p class="hist">📊 vs auditoria anterior ({_e(hist.get("vs"))}): '
               f'<strong>{hist.get("resolved", 0)}</strong> resolvidos · '
               f'<strong>{hist.get("new", 0)}</strong> novos</p>') if hist else ""

    nodes = _na_or(report.get("nodes"), lambda ns: _table(
        ["Host", "Role", "Disp.", "Estado", "Leader", "Capacidade"],
        [[_e(n.get("hostname")), _e(n.get("role")), _e(n.get("availability")), _e(n.get("state")),
          "sim" if n.get("leader") else "—", _e(_fmt_capacity(n.get("capacity")))] for n in ns]))

    services = _na_or(report.get("services"), lambda ss: _table(
        ["Service", "Tipo", "Imagem", "Réplicas", "Portas"],
        [[_e(s.get("name")), _e(s.get("kind")),
          _e(f'{s.get("image")}:{s.get("tag")}' + ("@…" if s.get("digest") else "")),
          _e(s.get("replicas")), _e(_fmt_ports(s.get("ports")))] for s in ss]))

    comp_an = report.get("components_analysis") or {}
    components = _na_or(report.get("services"), lambda ss: _table(
        ["Componente", "Tipo", "Roteamento / portas", "Análise"],
        [[_e(s.get("name")), f'<span class="badge low">{_e(s.get("kind") or "app")}</span>',
          _e(_routing_summary(s)), _e(comp_an.get(s.get("name"), "—"))]
         for s in ss if comp_an.get(s.get("name")) or s.get("kind") != "app"]) or '<p class="muted">—</p>')

    networks = _na_or(report.get("networks"), lambda ns: _table(
        ["Rede", "Driver", "Scope"], [[_e(n.get("name")), _e(n.get("driver")), _e(n.get("scope"))] for n in ns]))

    offenders = report.get("top_offenders") or []
    top = _table(["Service", "Findings"], [[_e(o.get("object")), _e(o.get("findings"))] for o in offenders]) \
        if offenders else '<p class="muted">—</p>'

    nc = report.get("not_collected") or []
    not_collected = ("<br>Não coletado: " + "; ".join(f'{_e(x.get("what"))} ({_e(x.get("reason"))})' for x in nc)) if nc else ""
    sc = [s.get("name") for s in (report.get("secrets") or [])] + [c.get("name") for c in (report.get("configs") or [])]
    secrets_configs = (f'{len(sc)} no total. <details><summary>ver nomes</summary>{_e(", ".join(sc))}</details>'
                       if sc else "nenhum")

    repl = {
        "%%TITLE%%": _e(f"Auditoria de cluster — {ctx}"), "%%CONTEXT%%": _e(ctx), "%%ENGINE%%": _e(engine),
        "%%GENERATED_AT%%": _e(report.get("generated_at")), "%%SCOPE%%": _e(scope.get("container_checks_cover")),
        "%%VERDICT%%": _e(verdict), "%%VERDICT_EMOJI%%": emoji, "%%VERDICT_LABEL%%": _e(label),
        "%%HISTORY%%": history, "%%SUMMARY%%": _e(summary),
        "%%DIMENSIONS%%": _dim_cards(report.get("dimensions")),
        "%%RECOMMENDATIONS%%": _recs(report.get("recommendations")),
        "%%STRENGTHS%%": _list(report.get("strengths")), "%%WEAKNESSES%%": _list(report.get("weaknesses")),
        "%%FINDINGS_GROUPED%%": _findings_grouped(report.get("findings")),
        "%%COMPONENTS%%": components, "%%TOP_OFFENDERS%%": top,
        "%%NODES%%": nodes, "%%SERVICES%%": services, "%%NETWORKS%%": networks,
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

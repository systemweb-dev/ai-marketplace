#!/usr/bin/env python3
"""build_report.py — report.json (schema v1) → HTML self-contained (primário) → PDF (opt-in).

Uso: python3 build_report.py --dir <out_dir>   # lê <dir>/report.json, escreve relatorio.html [+ .pdf]

Sem acesso a rede (o único módulo com rede é lib/http_get.py, usado só na coleta). O PDF é
gerado se houver Chromium/Chrome (headless, offline); senão entrega o HTML e avisa.
"""
import argparse
import html
import json
import os
import shutil
import subprocess
import sys

from lib import metrics, stacks
from lib.rule_meta import meta as rule_meta

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "assets", "report-template", "template.html")

_VERDICT = {"green": ("●", "Operacional"), "yellow": ("●", "Operacional com ressalvas"),
            "red": ("●", "Degradado"), "unknown": ("○", "Sem dados")}
_NOTE_TXT = {"green": "OK", "yellow": "Atenção", "red": "Crítico", "unknown": "sem dados"}
_DIM_LABEL = {"operacao": "Operação", "disponibilidade": "Disponibilidade",
              "seguranca": "Segurança", "higiene": "Higiene"}
_DIM_ORDER = ("operacao", "disponibilidade", "seguranca", "higiene")

CHROME_CANDIDATES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]


# ---------------------------------------------------------------- helpers
def _e(x):
    return html.escape("" if x is None else str(x))


def find_chromium():
    for c in CHROME_CANDIDATES:
        p = shutil.which(c)
        if p:
            return p
    return None


def _na_or(section, render_fn):
    if isinstance(section, dict) and section.get("status") == "n/a":
        return f'<p class="muted">não coletado — {_e(section.get("reason"))}</p>'
    if not section:
        return '<p class="muted">nenhum.</p>'
    return render_fn(section)


def _table(headers, rows, aligns=None):
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = ""
    for r in rows:
        tds = ""
        for i, c in enumerate(r):
            cls = ' class="num"' if aligns and i < len(aligns) and aligns[i] == "num" else ""
            tds += f"<td{cls}>{c}</td>"
        body += f"<tr>{tds}</tr>"
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _rich(text):
    """Escapa tudo e devolve só <strong> — o agente pode destacar trechos sem abrir XSS."""
    return (_e(text).replace("&lt;strong&gt;", "<strong>").replace("&lt;/strong&gt;", "</strong>"))


def _list(items):
    items = [i for i in (items or []) if i]
    if not items:
        return '<p class="muted">—</p>'
    return "<ul>" + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>"


def _fmt_ports(ports):
    out = []
    for p in (ports or []):
        if isinstance(p, dict):
            loc = f'{p.get("host_ip")}:{p.get("host_port")}' if p.get("host_ip") else (p.get("host_port") or "")
            out.append(f'{p.get("port")} → {loc}' if loc else str(p.get("port")))
        else:
            out.append(str(p))
    return ", ".join(out)


def _fmt_capacity(cap):
    cap = cap or {}
    parts = []
    if cap.get("nano_cpus"):
        parts.append(f'{cap["nano_cpus"] / 1e9:.0f} vCPU')
    if cap.get("mem_bytes"):
        parts.append(f'{cap["mem_bytes"] / 1024 ** 3:.1f} GB')
    return " · ".join(parts) or "—"


def _human(n):
    """12345 -> 12,3 mil ; 1234567 -> 1,2 mi"""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "—"
    for lim, suf in ((1e9, "bi"), (1e6, "mi"), (1e3, "mil")):
        if abs(n) >= lim:
            return f"{n / lim:.1f} {suf}".replace(".", ",")
    return f"{int(n)}"


def _mb(n):
    try:
        return f"{float(n) / 1024 ** 2:.0f} MB"
    except (TypeError, ValueError):
        return "—"


def _runtime_cells(svc):
    """Resumo curto das métricas de runtime que existirem para o service."""
    rt = svc.get("runtime") or {}
    bits = []
    if rt.get("requests_24h") is not None:
        e = rt.get("errors_5xx_24h") or 0
        bits.append(f'{_human(rt["requests_24h"])} req/24h' + (f' · {_human(e)} 5xx' if e else ""))
    if rt.get("p95_ms") is not None:
        bits.append(f'p95 {rt["p95_ms"]:.0f} ms')
    if rt.get("queue_ready") is not None:
        bits.append(f'{_human(rt["queue_ready"])} na fila · {rt.get("queue_consumers", 0)} consumers')
    if rt.get("cpu_pct") is not None:
        bits.append(f'{rt["cpu_pct"]}% CPU')
    if rt.get("mem_bytes") is not None:
        bits.append(_mb(rt["mem_bytes"]))
    return " · ".join(bits) or "—"


# ---------------------------------------------------------------- seções
def _kpis(report, groups):
    services = report.get("services")
    n_svc = len(services) if isinstance(services, list) else 0
    nodes = report.get("nodes")
    n_nodes = len(nodes) if isinstance(nodes, list) else 0
    total_req = sum((s.get("runtime") or {}).get("requests_24h") or 0
                    for s in (services if isinstance(services, list) else []))
    cards = [(str(n_nodes), "nós"), (str(n_svc), "serviços"), (str(len(groups)), "aplicações")]
    cards.append((_human(total_req) if total_req else "—", "requests 24h"))
    return "".join(f'<div class="card kpi"><div class="n">{_e(v)}</div><div class="l">{_e(l)}</div></div>'
                   for v, l in cards)


def _dim_cards(dims):
    out = []
    for key in _DIM_ORDER:
        d = (dims or {}).get(key) or {}
        note = d.get("note", "green")
        if key == "operacao":
            up, total = d.get("services_up", 0), d.get("services_total", 0)
            pct = _pct(up, total)
            legend = (f'<div class="barlbl"><span>serviços no ar</span><span>{up}/{total}</span></div>'
                      f'<div class="barlbl"><span>parados / nós fora</span>'
                      f'<span>{d.get("stopped", 0)} / {d.get("nodes_down", 0)}</span></div>')
        elif key == "disponibilidade":
            pct = d.get("ha_pct", 0)
            legend = (f'<div class="barlbl"><span>serviços com réplica &gt; 1</span><span>{pct}%</span></div>'
                      f'<div class="barlbl"><span>sem redundância (estado/ingress)</span>'
                      f'<span>{len(d.get("spof_stateful") or []) + len(d.get("spof_critical") or [])}</span></div>')
        elif key == "seguranca":
            high, med = d.get("high", 0), d.get("med", 0)
            pct = max(0, 100 - min(100, high * 12 + med))
            legend = (f'<div class="barlbl"><span>achados críticos</span><span>{high}</span></div>'
                      f'<div class="barlbl"><span>achados médios</span><span>{med}</span></div>')
        else:
            pct = d.get("nonroot_pct", 0)
            legend = (f'<div class="barlbl"><span>containers não-root</span><span>{pct}%</span></div>'
                      f'<div class="barlbl"><span>imagens com versão fixa</span>'
                      f'<span>{d.get("pinned_pct", 0)}%</span></div>')
        gauge = f'<div class="bar"><i style="width:{pct}%"></i></div>'
        out.append(f'<div class="card dim {note}"><div class="t">{_DIM_LABEL[key]}</div>'
                   f'<div class="v">{_NOTE_TXT.get(note, "?")}</div>{gauge}{legend}</div>')
    return "".join(out)


def _pct(x, total):
    return round(100 * x / total) if total else 0


def _recs(recs):
    if not recs:
        return '<p class="muted">Sem recomendações registradas (o agente preenche <code>recommendations</code>).</p>'
    out = []
    for i, r in enumerate(recs, 1):
        imp = (r.get("impact") or "").lower()
        icl = "hi" if imp.startswith("alt") else ("mid" if imp.startswith(("méd", "med")) else "lo")
        cmd = r.get("command")
        if cmd:
            cmd = str(cmd).replace("\\n", "\n")   # normaliza \n literal vindo do JSON
            lines = [ln for ln in cmd.split("\n")]
            body = "\n".join(f'<span class="p">$ </span>{_e(ln)}' if not ln.lstrip().startswith("#")
                             else f'<span class="p">{_e(ln)}</span>' for ln in lines)
            cmd_html = f'<div class="cmd">{body}</div>'
        else:
            cmd_html = ""
        out.append(
            f'<div class="card rec"><div class="num">{i}</div><div class="body">'
            f'<div class="rt">{_e(r.get("title"))}</div>'
            f'<div class="rw">{_e(r.get("why"))}</div>{cmd_html}'
            f'<div class="tags"><span class="tag {icl}">impacto {_e(r.get("impact") or "—")}</span>'
            f'<span class="tag">esforço {_e(r.get("effort") or "—")}</span>'
            + (f'<span class="tag">{_e(r.get("scope"))}</span>' if r.get("scope") else "")
            + '</div></div></div>')
    return "".join(out)


def _stack_blocks(report, groups, comp_an):
    if not groups:
        return '<p class="muted">—</p>'
    out = []
    for g in groups:
        rows = []
        for s in sorted(g["services"], key=lambda x: x.get("name") or ""):
            img = f'{s.get("image")}:{s.get("tag")}' if s.get("tag") else f'{s.get("image")}'
            rows.append([
                f'<b>{_e(stacks.short_name(s.get("name")))}</b>',
                f'<span class="badge kind">{_e(s.get("kind") or "app")}</span>',
                f'<code>{_e(img)}</code>',
                _e(s.get("replicas") or "—"),
                _e(_runtime_cells(s)),
            ])
        tbl = _table(["Serviço", "Tipo", "Imagem", "Réplicas", "Runtime"], rows, [None, None, None, "num", None])
        routes = " · ".join(g["routes"][:3]) + (f' +{len(g["routes"]) - 3}' if len(g["routes"]) > 3 else "")
        badges = ""
        if g["findings_high"]:
            badges += f'<span class="badge high">{g["findings_high"]} críticos</span>'
        if g["findings_med"]:
            badges += f'<span class="badge med">{g["findings_med"]} médios</span>'
        if g["spofs"]:
            badges += f'<span class="badge low">{len(g["spofs"])} sem HA</span>'
        notes = [comp_an.get(s.get("name")) for s in g["services"] if comp_an.get(s.get("name"))]
        note_html = ('<div class="an">' + " ".join(_e(n) for n in notes) + "</div>") if notes else ""
        out.append(
            f'<div class="card stack {g["note"]}"><div class="sh"><span class="dot"></span>'
            f'<span class="nm">{_e(g["stack"])}</span>{badges}'
            + (f'<span class="routes">{_e(routes)}</span>' if routes else "")
            + f'</div>{tbl}{note_html}</div>')
    return "".join(out)


def _findings_grouped(findings):
    if isinstance(findings, dict) and findings.get("status") == "n/a":
        return f'<p class="muted">não coletado — {_e(findings.get("reason"))}</p>'
    if not findings:
        return '<p class="muted">Nenhum achado. 🎉</p>'
    out = []
    for g in metrics.group_findings(findings):
        m = rule_meta(g["rule_id"])
        uniq = sorted({o.split(".")[0] for o in g["objects"]})
        shown = uniq[:10]
        extra = len(uniq) - len(shown)
        objs_txt = ", ".join(shown) + (f" … +{extra}" if extra > 0 else "")
        expected = g.get("expected")
        badge = ('<span class="badge low">esperado</span>' if expected
                 else f'<span class="badge {_e(g["severity"])}">{_e(g["severity"])}</span>')
        fix_label = "Opcional" if expected else "Como corrigir"
        out.append(
            f'<div class="card fg"><div class="fh">{badge}'
            f'<span class="fn">{_e(m["label"])}</span><code>{_e(g["rule_id"])}</code>'
            f'<span class="cnt">{g["count"]} ocorrências</span></div>'
            f'<div class="row">{_e(m["what"])}</div>'
            f'<div class="row"><b>Por que importa:</b> {_e(m["why"])}</div>'
            f'<div class="row"><b>{fix_label}:</b> {_e(g.get("fix"))}</div>'
            f'<div class="objs">Afetados ({len(uniq)}): {_e(objs_txt)}</div></div>')
    return "".join(out)


# ---------------------------------------------------------------- render
def render_html(report):
    ctx = (report.get("cluster") or {}).get("context")
    engine = (report.get("cluster") or {}).get("engine_version")
    verdict = (report.get("health") or {}).get("verdict", "green")
    emoji, label = _VERDICT.get(verdict, ("●", "?"))
    scope = report.get("scope") or {}
    dims = report.get("dimensions") or {}
    groups = stacks.group(report)
    comp_an = report.get("components_analysis") or {}

    op = dims.get("operacao") or {}
    av = dims.get("disponibilidade") or {}
    sem_ha = len(av.get("spof_stateful") or []) + len(av.get("spof_critical") or [])
    oneline = (f'{op.get("services_up", 0)}/{op.get("services_total", 0)} serviços no ar'
               + (f' · {sem_ha} sem redundância' if sem_ha else ""))

    summary = report.get("summary") or ("Resumo ainda não escrito — o agente preenche <code>summary</code> "
                                        "explicando o porquê do veredito.")
    hist = report.get("history")
    history = (f'<p class="hist">Comparado à auditoria anterior ({_e(hist.get("vs"))}): '
               f'<b>{hist.get("resolved", 0)}</b> resolvidos · <b>{hist.get("new", 0)}</b> novos.</p>') if hist else ""

    src = report.get("metrics_source")
    metrics_src = (f'· métricas de runtime: {_e(", ".join(src))}' if src
                   else '· sem fonte de métricas de runtime')

    nodes = _na_or(report.get("nodes"), lambda ns: _table(
        ["Host", "Papel", "Disponibilidade", "Estado", "Líder", "Capacidade"],
        [[f'<b>{_e(n.get("hostname"))}</b>', _e(n.get("role")), _e(n.get("availability")),
          _e(n.get("state")), "sim" if n.get("leader") else "—", _e(_fmt_capacity(n.get("capacity")))]
         for n in ns]))

    services = _na_or(report.get("services"), lambda ss: _table(
        ["Serviço", "Tipo", "Imagem", "Réplicas", "Portas"],
        [[_e(s.get("name")), _e(s.get("kind")),
          _e(f'{s.get("image")}:{s.get("tag")}'), _e(s.get("replicas")), _e(_fmt_ports(s.get("ports")))]
         for s in ss]))

    networks = _na_or(report.get("networks"), lambda ns: _table(
        ["Rede", "Driver", "Escopo"],
        [[_e(n.get("name")), _e(n.get("driver")), _e(n.get("scope"))] for n in ns]))

    nc = report.get("not_collected") or []
    not_collected = ("<br>Não coletado: " + "; ".join(f'{_e(x.get("what"))} ({_e(x.get("reason"))})' for x in nc)) if nc else ""
    sc = [s.get("name") for s in (report.get("secrets") or [])] + [c.get("name") for c in (report.get("configs") or [])]
    secrets_configs = (f'{len(sc)} no total. <details><summary>ver nomes</summary>{_e(", ".join(sc))}</details>'
                       if sc else "nenhum")

    repl = {
        "%%TITLE%%": _e(f"Auditoria de cluster — {ctx}"), "%%CONTEXT%%": _e(ctx), "%%ENGINE%%": _e(engine),
        "%%GENERATED_AT%%": _e(report.get("generated_at")), "%%SCOPE%%": _e(scope.get("container_checks_cover")),
        "%%METRICS_SOURCE%%": metrics_src,
        "%%VERDICT%%": _e(verdict), "%%VERDICT_EMOJI%%": emoji, "%%VERDICT_LABEL%%": _e(label),
        "%%VERDICT_ONELINE%%": _e(oneline),
        "%%HISTORY%%": history, "%%SUMMARY%%": summary if summary.startswith("Resumo ainda") else _rich(summary),
        "%%KPIS%%": _kpis(report, groups),
        "%%DIMENSIONS%%": _dim_cards(dims),
        "%%RECOMMENDATIONS%%": _recs(report.get("recommendations")),
        "%%STRENGTHS%%": _list(report.get("strengths")), "%%WEAKNESSES%%": _list(report.get("weaknesses")),
        "%%STACKS%%": _stack_blocks(report, groups, comp_an),
        "%%FINDINGS_GROUPED%%": _findings_grouped(report.get("findings")),
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

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
import re
import shutil
import subprocess
import sys

from lib import metrics, stacks
from lib.rule_meta import meta as rule_meta

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "assets", "report-template", "template.html")

_VERDICT = {"green": ("●", "Saudável"), "yellow": ("●", "Atenção"),
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
        note = d.get("note", "unknown")   # sem nota não é "ok": é sem dados
        if key == "operacao":
            up, total = d.get("services_up", 0), d.get("services_total", 0)
            pct = _pct(up, total)
            legend = (f'<div class="barlbl"><span>serviços no ar</span><span>{up}/{total}</span></div>'
                      f'<div class="barlbl"><span>parados / nós fora</span>'
                      f'<span>{d.get("stopped", 0)} / {d.get("nodes_down", 0)}</span></div>')
        elif key == "disponibilidade":
            pct = d.get("ha_pct", 0)
            legend = (f'<div class="barlbl"><span>com 2+ réplicas</span><span>{pct}%</span></div>'
                      f'<div class="barlbl"><span>sem redundância</span>'
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


def _diverge(valores):
    """Índices cujo valor foge da maioria.

    É o que dá razão de existir à comparação lado a lado: uma tabela que só repete
    `Ready · Ready · Ready · Ready` gasta tinta sem informar. O que informa é a célula
    que destoa — engine atrasada, nó com metade da memória.
    """
    limpos = [v for v in valores if v not in ("—", "", None)]
    if len(set(limpos)) < 2:
        return set()
    freq = {}
    for v in limpos:
        freq[v] = freq.get(v, 0) + 1
    maioria = max(freq.values())
    # sem maioria clara (todos diferentes), nada a destacar: destacar tudo não diz nada
    if maioria == 1:
        return set()
    comum = [v for v, c in freq.items() if c == maioria]
    return {i for i, v in enumerate(valores) if v not in ("—", "", None) and v not in comum}


def _exit_code(txt):
    """'svc.1: "task: non-zero exit (137)"' -> ('svc', '137')."""
    import re
    svc = str(txt).split(":", 1)[0].rsplit(".", 1)[0]
    m = re.search(r"exit \((\d+)\)", str(txt))
    return svc, (m.group(1) if m else None)


def _node_failures(nodes):
    """Falhas agrupadas por código de saída, fora da tabela.

    Antes cada nó carregava 3 linhas de texto cru dentro da própria célula, quebradas a cada
    ~20 caracteres. Agrupar por código revela o que a listagem escondia: um mesmo exit em
    vários serviços não relacionados é UM evento (um restart), não N problemas.
    """
    por_code = {}
    for n in nodes:
        for ex in (n.get("failed_examples") or []):
            svc, code = _exit_code(ex)
            por_code.setdefault(code or "?", []).append((svc, n.get("hostname")))
    if not por_code:
        return ""
    PISTA = {"137": "SIGKILL — processo terminado de fora (restart do daemon, OOM ou limite)",
             "143": "SIGTERM — parada solicitada",
             "1": "erro da aplicação",
             "255": "erro da aplicação (código genérico)"}
    blocos = []
    for code, itens in sorted(por_code.items(), key=lambda kv: -len(kv[1])):
        nos = sorted({h for _, h in itens})
        servicos = sorted({s for s, _ in itens})
        pista = PISTA.get(code, "")
        multi = (' <span class="nfmulti">mesmo código em '
                 f'{len(servicos)} serviços de {len(nos)} nós</span>') if len(nos) > 1 else ""
        blocos.append(
            f'<div class="nfrow"><div class="nfhead"><span class="nfcode">exit {_e(code)}</span>'
            f'<span class="nfhint">{_e(pista)}</span>{multi}</div>'
            f'<div class="nfsvcs">{_e(" · ".join(servicos))}</div></div>')
    return ('<div class="nfail"><div class="nfh">Falhas recentes por código de saída</div>'
            + "".join(blocos) + "</div>")


def _node_table(nodes):
    """Nós como colunas de uma tabela comparativa.

    Em cards, cada rótulo se repetia uma vez por nó e a maioria dos valores era idêntica —
    a repetição consumia a largura que faltava aos valores. Na tabela o rótulo aparece uma
    vez e a leitura vira horizontal, que é como se compara nó com nó.
    """
    if isinstance(nodes, dict) and nodes.get("status") == "n/a":
        return f'<p class="muted">não coletado — {_e(nodes.get("reason"))}</p>'
    if not nodes:
        return '<p class="muted">nenhum nó (cluster não-Swarm).</p>'

    def cap(n):
        c = n.get("capacity") or {}
        cpu, mem = c.get("nano_cpus"), c.get("mem_bytes")
        if not cpu and not mem:
            return "—"
        return (f'{cpu // 1_000_000_000} vCPU' if cpu else "—") + \
               (f'<br><span class="nsub">{mem / 1_073_741_824:.1f} GB</span>' if mem else "")

    linhas = [
        ("papel", [("líder" if n.get("leader") else (n.get("role") or "worker")).lower() for n in nodes], False),
        ("estado", [n.get("state") or "—" for n in nodes], False),
        ("disponibilidade", [n.get("availability") or "—" for n in nodes], False),
        ("engine", [n.get("engine") or "—" for n in nodes], True),
        ("plataforma", [n.get("platform") or "—" for n in nodes], True),
        ("capacidade", [cap(n) for n in nodes], True),
        ("tasks rodando", [str(n.get("tasks_running")) if n.get("tasks_running") is not None else "—" for n in nodes], False),
        ("falhas 24h", [str(n.get("tasks_failed") or 0) for n in nodes], False),
    ]
    if any(n.get("reachability") for n in nodes):
        linhas.insert(3, ("alcance (raft)", [n.get("reachability") or "—" for n in nodes], False))

    head = "".join(
        f'<th class="{"lead" if n.get("leader") else ""}">{_e(n.get("hostname"))}</th>' for n in nodes)
    corpo = []
    for rotulo, valores, marcar in linhas:
        fora = _diverge(valores) if marcar else set()
        tds = "".join(
            f'<td class="{"dv" if i in fora else ""}">{v if rotulo == "capacidade" else _e(v)}</td>'
            for i, v in enumerate(valores))
        corpo.append(f'<tr><th scope="row">{_e(rotulo)}</th>{tds}</tr>')

    nota = ('<div class="ndnote">células marcadas divergem do resto do cluster</div>'
            if any(_diverge(v) for _, v, m in linhas if m) else "")
    return (f'<table class="ndt"><thead><tr><th></th>{head}</tr></thead>'
            f'<tbody>{"".join(corpo)}</tbody></table>{nota}' + _node_failures(nodes))


def _disk(disk):
    """Uso de disco do nó conectado (docker system df)."""
    if isinstance(disk, dict) and disk.get("status") == "n/a":
        return ('<h2><span class="n">5b</span> Disco</h2>'
                f'<p class="muted">não coletado — {_e(disk.get("reason"))}</p>')
    if not disk:
        return ""
    rows = [[_e(d.get("tipo")), _e(d.get("total")), _e(d.get("ativo")),
             _e(d.get("tamanho")), _e(d.get("recuperavel"))] for d in disk]
    return ('<h2><span class="n">5b</span> Disco — nó conectado</h2>'
            + _table(["Tipo", "Total", "Ativos", "Tamanho", "Recuperável"], rows,
                     [None, "num", "num", "num", "num"]))


def _tls(tls):
    """Validade dos certificados TLS do context — sempre exibida quando há TLS."""
    if isinstance(tls, dict) and tls.get("status") == "n/a":
        return ('<h2><span class="n">5c</span> Certificados TLS</h2>'
                f'<p class="muted">{_e(tls.get("reason"))}</p>')
    if not tls:
        return ""
    rows = []
    for c in tls.get("certs", []):
        st = c["status"]
        badge = {"expired": '<span class="badge high">expirado</span>',
                 "expiring": '<span class="badge med">vence em breve</span>',
                 "ok": '<span class="badge ok">válido</span>'}.get(st, "")
        dias = c["days_left"]
        rows.append([f'<code>{_e(c["file"])}</code>', _e(c.get("label")), badge,
                     _e(c["not_after"][:10]),
                     _e(f'{dias} dias' if dias >= 0 else f'venceu há {abs(dias)} dias')])
    return ('<h2><span class="n">5c</span> Certificados TLS do acesso ao cluster</h2>'
            + _table(["Arquivo", "Papel", "Situação", "Válido até", "Restante"], rows,
                     [None, None, None, None, "num"]))


def _plano(passos):
    """Plano de execução: passos numerados com comando pronto e o porquê de cada um.

    É o que separa relatório de conselho — sem isso o card diz "distribua as réplicas" e
    deixa a parte difícil (em que ordem, e por que essa ordem) por conta do leitor.
    """
    if not passos:
        return ""
    itens = []
    for i, p in enumerate(passos, 1):
        cmd = (f'<pre class="ipre">{_e(p["comando"])}</pre>' if p.get("comando") else "")
        why = (f'<div class="iwhy">{_e(p["porque"])}</div>' if p.get("porque") else "")
        itens.append(f'<li><b>{_e(p.get("passo"))}</b>{why}{cmd}</li>')
    return f'<div class="iplan"><div class="iplanh">Como resolver</div><ol>{"".join(itens)}</ol></div>'


def _impact(pontos):
    """Cenário → consequência. É aqui que mora o risco (a saúde só fala do que quebrou)."""
    if not pontos:
        return '<p class="muted">Nenhum ponto de impacto relevante — cluster redundante e com boa higiene.</p>'
    cls = {"alto": "red", "médio": "yellow", "baixo": "green"}
    out = []
    for p in pontos:
        alvos = (f'<div class="ial">{_e(", ".join(p["alvos"]))}</div>' if p.get("alvos") else "")
        fix = (f'<div class="ifix">→ {_e(p["fix"])}</div>' if p.get("fix") else "")
        plano = _plano(p.get("plano"))
        out.append(
            f'<div class="card imp {cls.get(p["impacto"], "yellow")}">'
            f'<div class="ic">{_e(p["cenario"])} <span class="arrow">→</span></div>'
            f'<div class="icons">{_e(p["consequencia"])}</div>{fix}{plano}{alvos}'
            f'<div class="tags"><span class="tag {"hi" if p["impacto"]=="alto" else "mid"}">'
            f'impacto {_e(p["impacto"])}</span>'
            f'<span class="tag">esforço {_e(p["esforco"])}</span></div></div>')
    return "".join(out)


def _history(hist):
    """Histórico visível: o que foi resolvido desde a auditoria anterior."""
    if not hist:
        return ""
    resolved, new = hist.get("resolved", 0), hist.get("new", 0)
    items = hist.get("resolved_items") or []
    lst = ""
    if items:
        shown = items[:12]
        extra = len(items) - len(shown)
        lst = ("<ul>" + "".join(f"<li>{_e(i)}</li>" for i in shown)
               + (f"<li>… +{extra}</li>" if extra > 0 else "") + "</ul>")
    return ('<h2><span class="n">2b</span> Desde a auditoria anterior</h2>'
            f'<div class="card hist">Comparado a <b>{_e(hist.get("vs"))}</b>: '
            f'<span class="badge ok">{resolved} resolvidos</span> '
            f'<span class="badge new">{new} novos</span>'
            + (f'<div style="margin-top:8px">Resolvidos:</div>{lst}' if lst else "")
            + "</div>")


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


def _stack_blocks(groups, comp_an):
    if not groups:
        return '<p class="muted">—</p>'
    out = []
    for g in groups:
        rows = []
        for s in sorted(g["services"], key=lambda x: x.get("name") or ""):
            img = f'{s.get("image")}:{s.get("tag")}' if s.get("tag") else f'{s.get("image")}'
            sinais = []
            if s.get("has_healthcheck") is False:
                sinais.append("sem healthcheck")
            lim = s.get("limits") or {}
            if not lim.get("nano_cpus") and not lim.get("mem_bytes"):
                sinais.append("sem limites")
            if s.get("tasks_failed"):
                sinais.append(f'{s["tasks_failed"]} task(s) falharam')
            if s.get("constraints"):
                sinais.append("· ".join(s["constraints"][:2]))
            rows.append([
                f'<b>{_e(stacks.short_name(s.get("name")))}</b>',
                f'<span class="badge kind">{_e(s.get("kind") or "app")}</span>',
                f'<code>{_e(img)}</code>',
                _e(s.get("replicas") or "—"),
                _e(_runtime_cells(s)),
                _e(" · ".join(sinais) or "ok"),
            ])
        tbl = _table(["Serviço", "Tipo", "Imagem", "Réplicas", "Runtime", "Observações"], rows,
                     [None, None, None, "num", None, None])
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


def _findings_grouped(findings, new_rules=frozenset()):
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
        if g["rule_id"] in new_rules:
            badge += '<span class="badge new">novo</span>' 
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
    falhando, parados = op.get("failing", 0), op.get("stopped", 0)
    oneline = f'{op.get("services_up", 0)}/{op.get("services_total", 0)} serviços no ar'
    if falhando:
        oneline += f' · {falhando} falhando'
    elif parados:
        oneline += f' · {parados} parados a confirmar'
    if sem_ha:
        oneline += f' · {sem_ha} sem redundância'
    _ = sem_ha

    summary = report.get("summary") or ("Resumo ainda não escrito — o agente preenche <code>summary</code> "
                                        "explicando o porquê do veredito.")
    # regras que apareceram só nesta auditoria (histórico visível)
    new_rules = {k[0] for k in ((report.get("history") or {}).get("new_keys") or [])}

    src = report.get("metrics_source")
    metrics_src = (f'métricas: <b>{_e(", ".join(src))}</b>' if src
                   else 'sem fonte de métricas de runtime')

    networks = _na_or(report.get("networks"), lambda ns: _table(
        ["Rede", "Driver", "Escopo"],
        [[_e(n.get("name")), _e(n.get("driver")), _e(n.get("scope"))] for n in ns]))

    nc = report.get("not_collected") or []
    not_collected = ("<br>Não coletado: " + "; ".join(f'{_e(x.get("what"))} ({_e(x.get("reason"))})' for x in nc)) if nc else ""
    sc = [s.get("name") for s in (report.get("secrets") or [])] + [c.get("name") for c in (report.get("configs") or [])]
    # sem <details>: no PDF não dá pra clicar, então tudo aparece
    secrets_configs = (f'<div class="names">{_e(", ".join(sc))}</div>' if sc
                       else '<p class="muted">nenhum.</p>')

    repl = {
        "%%TITLE%%": _e(f"Auditoria de cluster — {ctx}"), "%%CONTEXT%%": _e(ctx), "%%ENGINE%%": _e(engine),
        "%%GENERATED_AT%%": _e(report.get("generated_at")), "%%SCOPE%%": _e(scope.get("container_checks_cover")),
        "%%METRICS_SOURCE%%": metrics_src,
        "%%VERDICT%%": _e(verdict), "%%VERDICT_EMOJI%%": emoji, "%%VERDICT_LABEL%%": _e(label),
        "%%VERDICT_ONELINE%%": _e(oneline),
        "%%HISTORY%%": _history(report.get("history")),
        "%%SUMMARY%%": summary if summary.startswith("Resumo ainda") else _rich(summary),
        "%%KPIS%%": _kpis(report, groups),
        "%%DIMENSIONS%%": _dim_cards(dims),
        "%%IMPACT%%": _impact(report.get("impact_points")),
        "%%RECOMMENDATIONS%%": _recs(report.get("recommendations")),
        "%%STRENGTHS%%": _list(report.get("strengths")), "%%WEAKNESSES%%": _list(report.get("weaknesses")),
        "%%STACKS%%": _stack_blocks(groups, comp_an),
        "%%FINDINGS_GROUPED%%": _findings_grouped(report.get("findings"), new_rules),
        "%%NODES%%": _node_table(report.get("nodes")), "%%DISK%%": _disk(report.get("disk")) + _tls(report.get("tls")),
        "%%NETWORKS%%": networks,
        "%%CONNECTED_NODE%%": _e(scope.get("connected_node")),
        "%%NOT_COLLECTED%%": not_collected, "%%SECRETS_CONFIGS%%": secrets_configs,
    }
    with open(TEMPLATE, encoding="utf-8") as f:
        page = f.read()
    for k, v in repl.items():
        page = page.replace(k, v)
    return page


FORMATOS = ("html", "html+pdf")


def build(report, out_dir, formato="html+pdf"):
    """Escreve o relatório. `formato` decide se o PDF também sai.

    O HTML é o produto; o PDF é escolha de quem recebe — e custa alguns segundos de Chromium
    em toda rodada. Por isso a skill pergunta no fim, em vez de gerar sempre.
    """
    if formato not in FORMATOS:
        raise ValueError(f"formato {formato!r} não existe; os formatos são "
                         f"{', '.join(FORMATOS)}")
    out_dir = os.path.expanduser(str(out_dir))
    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, "relatorio.html")
    # o v3 é o formato por alvos e componentes. Relatório de schema anterior não é
    # redesenhado nem comparado: ele fica onde está, como histórico.
    if report.get("schema_version") != 3:
        raise ValueError(f"schema {report.get('schema_version')!r}: este build lê o v3; "
                         f"relatórios anteriores ficam onde estão, como histórico")
    pagina = render_html_v3(report)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(pagina)

    pdf_path = None
    chrome = find_chromium() if formato == "html+pdf" else None
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


# ---------------------------------------------------------------- relatório v3 (por alvos e componentes)
TEMPLATE_V3 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "assets", "report-template", "template_v3.html")

ORDEM_SEVERIDADE = ("critical", "high", "medium", "low", "info")
ROTULO_SEVERIDADE = {"critical": "Crítico", "high": "Alto", "medium": "Médio",
                     "low": "Baixo", "info": "Informativo"}


def montar_contexto(r):
    """Do report v3 para o que o template desenha, na ordem em que o leitor precisa."""
    if r.get("schema_version") != 3:
        raise ValueError(f"schema {r.get('schema_version')!r}: este build lê o v3; "
                         f"relatórios anteriores ficam onde estão, como histórico")

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from lib.report import achados_ordenados

    por_estado = {}
    for alvo in r["alvos"]:
        por_estado[alvo["saude"]] = por_estado.get(alvo["saude"], 0) + 1

    return {
        "gerado_em": r["generated_at"],
        "panorama": {"total": len(r["alvos"]), "por_estado": por_estado,
                     "achados": len(achados_ordenados(r)),
                     "aceitos": len(r.get("aceites") or [])},
        "inventario": r.get("inventario") or [],
        "achados": achados_ordenados(r),
        "aceites": r.get("aceites") or [],
        "alvos": r["alvos"],
        "historico": r.get("historico"),
        "resumo": r.get("resumo", ""), "fortes": r.get("fortes", []),
        "fracos": r.get("fracos", []), "recomendacoes": r.get("recomendacoes", []),
    }


# o vocabulário de estado em PALAVRA: emoji some na impressão em preto e branco e exige legenda
ESTADO_EM_PALAVRA = {"🟢": ("Operacional", "ok"), "🟡": ("Atenção", "warn"),
                     "🔴": ("Degradado", "bad"), "sem dados": ("Sem dados", "na")}


def _plural(quantidade, singular, plural):
    return f"{quantidade} {singular if quantidade == 1 else plural}"


def _panorama(p):
    """Contagem por estado — NUNCA uma nota única: número só da infra vira meta, e meta vira teatro."""
    chips = []
    for estado, qtd in sorted(p["por_estado"].items()):
        palavra, classe = ESTADO_EM_PALAVRA.get(estado, (str(estado), "na"))
        chips.append(f'<span class="chip {classe}"><i class="dot"></i>{qtd} {_e(palavra)}</span>')
    chips.append(f'<span class="chip acc"><i class="dot"></i>'
                 f'{_plural(p["achados"], "achado", "achados")}</span>')
    if p["aceitos"]:
        chips.append(f'<span class="chip na"><i class="dot"></i>'
                     f'{_plural(p["aceitos"], "risco aceito", "riscos aceitos")}</span>')
    return "".join(chips)


def _estado(saude):
    """Estado em PALAVRA, com o ponto colorido ao lado: emoji some na impressão em preto e
    branco e exige legenda que ninguém lê."""
    palavra, classe = ESTADO_EM_PALAVRA.get(saude, (str(saude), "na"))
    return f'<span class="chip {classe}"><i class="dot"></i>{_e(palavra)}</span>'


def _inventario(itens):
    if not itens:
        return '<p class="muted">nenhum alvo.</p>'
    return _table(["Alvo", "Tipo", "Onde", "Estado"],
                  [[_e(i["nome"]), _e(i["tipo"]), _e(i["onde"]), _estado(i["saude"])]
                   for i in itens])


def _achados_v3(achados):
    if not achados:
        return '<p class="muted">nenhum achado.</p>'
    saida = []
    for severidade in ORDEM_SEVERIDADE:
        desta = [a for a in achados if a.get("severidade") == severidade]
        if not desta:
            continue
        saida.append(f"<h3>{ROTULO_SEVERIDADE[severidade]}</h3>")
        saida.append(_table(["Alvo", "Regra", "Objeto", "Detalhe"],
                            [[_e(a.get("alvo")), _e(a.get("regra")), _e(a.get("objeto")),
                              _e(a.get("detalhe") or "")] for a in desta]))
    return "".join(saida)


def _aceites_v3(aceites):
    if not aceites:
        return '<p class="muted">nenhum risco aceito registrado.</p>'
    linhas = []
    for a in aceites:
        if a.get("vencido"):
            estado = '<span class="chip bad">vencido</span>'
        elif a.get("obsoleto"):
            estado = '<span class="chip na">não casa com achado</span>'
        else:
            estado = '<span class="chip ok">válido</span>' 
        linhas.append([_e(a.get("alvo")), _e(a.get("regra")), _e(a.get("motivo")),
                       _e(a.get("origem")), _e(a.get("desde") or ""),
                       _e(a.get("revisar_em") or "sem data"), estado])
    return _table(["Alvo", "Regra", "Motivo", "Origem", "Desde", "Revisar em", "Estado"], linhas)


def _recomendacoes_v3(recs):
    """O que o agente priorizou, com o comando pronto. Como em todo o resto do relatório: o
    comando é para você executar — a auditoria nunca executa nada."""
    if not recs:
        return '<p class="muted">nenhuma recomendação escrita nesta rodada.</p>'
    blocos = []
    for rec in recs:
        comando = str(rec.get("comando") or "").replace("\\n", "\n")
        meta = " · ".join(_e(p) for p in (
            f'alvo {rec.get("alvo")}' if rec.get("alvo") else "",
            f'impacto {rec.get("impacto")}' if rec.get("impacto") else "",
            f'esforço {rec.get("esforco")}' if rec.get("esforco") else "") if p)
        blocos.append(
            f'<div class="ach" style="--c:var(--acc)">'
            f'<div class="ach-h"><b>{_e(rec.get("titulo"))}</b></div>'
            f'<p class="ach-o">{meta}</p>'
            f'<p class="ach-d">{_rich(rec.get("porque"))}</p>'
            + (f'<div class="fix"><pre>{_e(comando)}</pre></div>' if comando else "")
            + '</div>')
    return "".join(blocos)



def _alvos_v3(alvos):
    """Uma ficha por alvo: estado, o que o agente escreveu, e o que NÃO foi coletado com o
    motivo — a parte que impede o relatório de mentir por omissão."""
    blocos = []
    for alvo in alvos:
        nao = alvo.get("nao_coletado") or []
        partes = [f'<div class="sys"><h3>{_e(alvo["nome"])}</h3>'
                  f'<span class="tag">{_e(alvo["tipo"])}</span>'
                  f'<span class="dono">{_e(alvo["onde"])}</span>'
                  f'{_estado(alvo["saude"])}</div>']
        if alvo.get("analise"):
            partes.append(f'<p class="an">{_rich(alvo["analise"])}</p>')
        if alvo.get("dimensoes"):
            partes.append(_dim_cards(alvo["dimensoes"]))
        if nao:
            itens = "".join(f'<div class="semdados">{_e(n.get("motivo"))}</div>' for n in nao)
            partes.append(f'<p class="fix-h" style="margin-top:10px">Não coletado</p>{itens}')
        blocos.append(f'<div class="card comp">{"".join(partes)}</div>')
    return "".join(blocos) or '<p class="muted">nenhum alvo.</p>'



def _historico_v3(h):
    if not h:
        return '<p class="muted">primeira auditoria neste projeto (ou histórico desligado).</p>'
    partes = [f'<p class="sub">comparado com {_e(h.get("vs"))}</p>']
    partes.append("<p><b>Resolvidos:</b> " + (_e(", ".join(h.get("resolvidos") or [])) or "nenhum") + "</p>")
    partes.append("<p><b>Novos:</b> " + (_e(", ".join(h.get("novos") or [])) or "nenhum") + "</p>")
    return "".join(partes)


# ---------------------------------------------------------------- insights e remediação (v3)
SECOES_V3 = (("panorama", "Panorama"), ("topologia", "Topologia"),
             ("instrumentos", "Instrumentos"),
             ("insights", "Insights por sistema"), ("achados", "Achados"),
             ("impacto", "Se isto falhar"), ("aceites", "Riscos aceitos"),
             ("recomendacoes", "Recomendações"), ("leitura", "Pontos fortes e de atenção"),
             ("alvos", "Por alvo"), ("historico", "Desde a auditoria anterior"))


def _quando(carimbo):
    """`2026-09-19T10:00:00Z` → `19/09/2026 10:00 UTC`. O carimbo ISO é para o histórico
    comparar; quem lê o relatório lê data."""
    from datetime import datetime
    try:
        instante = datetime.fromisoformat(str(carimbo).replace("Z", "+00:00"))
    except ValueError:
        return str(carimbo)
    return instante.strftime("%d/%m/%Y %H:%M UTC")


DESCRICAO_SECAO = {
    "panorama": "o que existe, onde vive e em que estado",
    "topologia": "os componentes agrupados por papel, com os achados de cada um",
    "instrumentos": "as medidas que têm tolerância declarada",
    "insights": "o que cada componente respondeu, com a fonte",
    "achados": "cada um com passo a passo e como confirmar",
    "impacto": "cenário e consequência, a partir do que existe hoje",
    "aceites": "decisão consciente, com justificativa e prazo",
    "recomendacoes": "o que o agente priorizou, com o comando pronto",
    "leitura": "o que sustenta bem e o que merece atenção",
    "alvos": "uma ficha por alvo, com o que não foi coletado",
    "historico": "diferença em relação à rodada anterior",
}


def _sumario(ctx):
    """Sumário que conta, não só lista.

    Sem número de página: o Chromium não tem `target-counter`, e descobrir a página numa
    segunda passada dependeria de ferramenta externa — duas máquinas gerariam relatórios
    diferentes para a mesma entrada. A navegação existe assim mesmo: o Chromium converte
    estas âncoras em link com destino de página dentro do PDF.
    """
    panorama = ctx["panorama"]
    componentes = sum(len(a.get("componentes", [])) for a in ctx["alvos"])
    com_fonte = sum(1 for a in ctx["alvos"] for c in a.get("componentes", [])
                    for r in c.get("respostas", []) if not r.get("sem_dados"))
    historico = ctx.get("historico") or {}
    contagens = {
        "panorama": (_plural(panorama["total"], "alvo", "alvos"), ""),
        "topologia": (_plural(componentes, "componente", "componentes"), ""),
        "instrumentos": (_plural(com_fonte, "leitura", "leituras"), ""),
        "achados": (_plural(panorama["achados"], "aberto", "abertos"),
                    "bad" if panorama["achados"] else "ok"),
        "impacto": ("", ""),
        "aceites": (_plural(panorama["aceitos"], "risco aceito", "riscos aceitos"), ""),
        "recomendacoes": (_plural(len(ctx["recomendacoes"]), "ação", "ações"), ""),
        "leitura": ("", ""),
        "alvos": ("", ""),
        "historico": (f'{len(historico.get("resolvidos", []))} saíram · '
                      f'{len(historico.get("novos", []))} entraram' if historico else "", ""),
    }
    linhas = []
    for pos, (id_, titulo) in enumerate(SECOES_V3, 1):
        quanto, classe = contagens.get(id_, ("", ""))
        linhas.append(
            f'<a class="sum-l {classe}" href="#{id_}"><span class="sum-n">{pos:02d}</span>'
            f'<b>{_e(titulo)}</b>'
            f'<span class="sum-q">{_e(quanto)}</span>'
            f'<span class="sum-d">{_e(DESCRICAO_SECAO.get(id_, ""))}</span></a>')
    return f'<div class="sumario"><div class="sum-t">{"".join(linhas)}</div></div>'


def _numero(valor):
    """12480 → 12.480. Número grande sem separador é número que ninguém lê."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return _e(valor)
    if isinstance(valor, int):
        return _e(f"{valor:,}".replace(",", "."))
    return _e(f"{valor:,.2f}".replace(",", "@").replace(".", ",").replace("@", "."))


def _ranking(itens):
    maior = max((i.get("valor") or 0 for i in itens), default=0) or 1
    linhas = []
    for item in itens:
        largura = 100 * (item.get("valor") or 0) / maior
        linhas.append(f'<div class="rk"><span class="lb">{_e(item.get("chave"))}</span>'
                      f'<span class="vl">{_numero(item.get("valor"))}</span>'
                      f'<span class="bar"><i style="width:{largura:.0f}%"></i></span></div>')
    return f'<div class="rank">{"".join(linhas)}</div>'


def _resposta(resposta):
    from lib.perguntas import PERGUNTAS

    pergunta = PERGUNTAS.get(resposta.get("pergunta"), {})
    titulo = _e(pergunta.get("titulo") or resposta.get("pergunta"))
    if resposta.get("sem_dados") or resposta.get("erro_interno"):
        return (f'<div class="semdados"><b>{titulo}</b> — {_e(resposta.get("motivo"))}</div>')
    valor = resposta.get("valor")
    if isinstance(valor, list):
        # numa lista, a unidade vale para cada linha — repeti-la embaixo do ranking só confunde
        corpo = _ranking(valor)
    else:
        unidade = pergunta.get("unidade")
        sufixo = f' <span class="un">{_e(unidade)}</span>' if unidade else ""
        corpo = f'<span class="v">{_numero(valor)}</span>{sufixo}'
    return (f'<div class="insight"><div class="ih"><b>{titulo}</b>'
            f'<span class="src">fonte: {_e(resposta.get("fonte"))}</span></div>'
            f'{corpo}</div>')


def _insights_v3(alvos):
    """Um cartão por componente: papel, e cada resposta com a FONTE que a produziu.

    Número sem fonte não entra no relatório — é isso que separa dado de chute, e é o que
    permite ao leitor saber se "0 requisições" quer dizer "não houve tráfego" ou "ninguém
    perguntou".
    """
    blocos = []
    for alvo in alvos:
        for componente in alvo.get("componentes", []):
            respostas = "".join(_resposta(r) for r in componente.get("respostas", []))
            if not respostas:
                respostas = ('<p class="muted">nenhuma pergunta para este papel nesta '
                             'versão.</p>')
            analise = (f'<p class="an">{_rich(componente["analise"])}</p>'
                       if componente.get("analise") else "")
            blocos.append(
                f'<div class="card comp"><div class="sys">'
                f'<span class="tag">{_e(componente.get("papel"))}</span>'
                f'<h3>{_e(componente.get("nome"))}</h3>'
                f'<span class="dono">{_e(alvo.get("nome"))}</span></div>'
                f'{analise}{respostas}</div>')
    return "".join(blocos) or '<p class="muted">nenhum componente respondeu nesta rodada.</p>'


def _remediacao(bloco):
    if not bloco:
        return ""
    return (f'<div class="fix"><p class="fix-h">Como resolver</p>'
            f'{_rich(bloco.get("como_resolver"))}'
            f'<p class="val"><b>Como confirmar:</b> {_rich(bloco.get("como_confirmar"))}</p>'
            f'<p class="nao"><b>Quando não fazer:</b> {_rich(bloco.get("quando_nao_fazer"))}</p>'
            f'</div>')


def _achados_com_remediacao(achados):
    if not achados:
        return '<p class="muted">nenhum achado nesta rodada.</p>'
    blocos = []
    for achado in achados:
        remediacao = achado.get("como_resolver") or {}
        titulo = _e(remediacao.get("titulo") or achado.get("regra"))
        onde = " · ".join(_e(p) for p in (achado.get("alvo"), achado.get("componente"),
                                          achado.get("objeto")) if p)
        vencido = ('<span class="chip bad">aceite vencido</span>'
                   if achado.get("aceite_vencido") else "")
        blocos.append(
            f'<div class="ach {_e(achado.get("severidade"))}">'
            f'<div class="ach-h"><b>{titulo}</b>'
            f'<span class="sev">{_e(ROTULO_SEVERIDADE.get(achado.get("severidade"), ""))}</span>'
            f'{vencido}</div>'
            f'<p class="ach-o">{_e(achado.get("regra"))} · {onde}</p>'
            f'<p class="ach-d">{_e(remediacao.get("por_que_importa") or achado.get("detalhe") or "")}</p>'
            f'{_remediacao(remediacao)}</div>')
    return "".join(blocos)


def _impacto_v3(alvos):
    """O que `impact.py` calcula: cenário → consequência. Ele rodava desde o v1 e o resultado
    era descartado porque a chave não entrava na lista copiada para `fatos`."""
    pontos = [(alvo.get("nome"), ponto) for alvo in alvos
              for ponto in (alvo.get("fatos", {}).get("impact_points") or [])]
    if not pontos:
        return '<p class="muted">sem pontos de impacto calculados nesta rodada.</p>'
    linhas = []
    for nome, ponto in pontos:
        linhas.append(f'<div class="imp"><b>{_e(ponto.get("titulo"))}</b>'
                      f'<span class="dono">{_e(nome)}</span>'
                      f'<p>{_e(ponto.get("cenario"))} → <b>{_e(ponto.get("consequencia"))}</b></p>'
                      f'</div>')
    return "".join(linhas)


# ---------------------------------------------------------------- topologia e instrumentos (v3)
# a ordem das camadas: quem recebe o tráfego, quem processa, quem guarda, quem observa.
# É agrupamento por PAPEL — a skill não mede dependência, e o relatório diz isso na legenda.
CAMADAS = (("entrada", "recebe o tráfego"), ("app", "processa"),
           ("fila", "enfileira"), ("banco", "guarda"), ("cache", "guarda"),
           ("busca", "guarda"), ("storage", "guarda"),
           ("observabilidade", "observa"))


def _no_da_topologia(alvo, componente):
    """Um nó: nome, papel, quantos achados abertos e a leitura que tiver."""
    abertos = len(componente.get("achados") or [])
    classe = "bad" if abertos >= 2 else ("at" if abertos else "ok")
    from lib.perguntas import PERGUNTAS

    respostas = [r for r in componente.get("respostas", []) if not r.get("sem_dados")]
    leitura = ""
    if respostas:
        primeira = respostas[0]
        titulo = PERGUNTAS.get(primeira["pergunta"], {}).get("titulo", "")
        leitura = f'<p class="leitura">{_e(titulo)}: {_numero(primeira.get("valor"))}</p>'
    elif componente.get("respostas"):
        leitura = '<p class="leitura vazio">sem fonte declarada</p>'
    qt = f'<span class="qt">{abertos}</span>' if abertos else ""
    return (f'<div class="no {classe}"><b>{_e(componente["nome"])}</b>'
            f'<span class="sub">{_e(componente.get("papel"))} · {_e(alvo["nome"])}</span>'
            f'{qt}{leitura}</div>')


def _topologia(alvos):
    """Camadas por papel. NÃO é grafo de dependência — dizer isso é obrigação, não rodapé."""
    por_papel = {}
    for alvo in alvos:
        for componente in alvo.get("componentes", []):
            por_papel.setdefault(componente.get("papel", "app"), []).append((alvo, componente))
    if not por_papel:
        return '<p class="muted">nenhum componente no inventário desta rodada.</p>'

    camadas = []
    for papel, _rotulo in CAMADAS:
        nos = por_papel.pop(papel, [])
        if not nos:
            continue
        marca = " ramifica" if len(nos) > 1 else ""
        camadas.append(f'<div class="camada{marca}">'
                       + "".join(_no_da_topologia(a, c) for a, c in nos) + "</div>")
    for papel, nos in sorted(por_papel.items()):        # papel fora da ordem conhecida
        marca = " ramifica" if len(nos) > 1 else ""
        camadas.append(f'<div class="camada{marca}">'
                       + "".join(_no_da_topologia(a, c) for a, c in nos) + "</div>")

    legenda = ('<div class="legenda">'
               '<span><i style="--c:var(--verde)"></i>sem achado aberto</span>'
               '<span><i style="--c:var(--ambar)"></i>1 achado</span>'
               '<span><i style="--c:var(--vermelho)"></i>2 ou mais</span>'
               '</div>'
               '<p class="nota-legenda">As camadas agrupam por <b>papel</b> — quem recebe o '
               'tráfego, quem processa, quem guarda. <b>Não é dependência medida</b>: a skill '
               'observa o papel de cada componente, não quem chama quem.</p>')
    return f'<div class="mapa">{"".join(camadas)}{legenda}</div>'


def _angulo(valor, faixa):
    """A agulha percorre 180° do zero ao máximo declarado. Fora da escala, encosta no fim —
    inventar posição para valor fora de faixa seria desenhar dado que não existe."""
    maximo = float(faixa["maximo"]) or 1.0
    fracao = min(max(float(valor) / maximo, 0.0), 1.0)
    if faixa["sentido"] == "maior_melhor":
        fracao = 1.0 - fracao
    return round(-90 + 180 * fracao, 1)


def _medidor(resposta, pergunta):
    faixa = pergunta["faixa"]
    ang = _angulo(resposta["valor"], faixa)
    unidade = f' <span class="un">{_e(pergunta.get("unidade"))}</span>' if pergunta.get("unidade") else ""
    limite = ("bom até" if faixa["sentido"] == "menor_melhor" else "bom a partir de")
    return (f'<div class="med"><div class="anel">'
            f'<div class="arco"></div><div class="furo"></div>'
            f'<div class="agulha" style="--ang:{ang}deg"></div><div class="eixo"></div></div>'
            f'<p class="v num">{_numero(resposta["valor"])}{unidade}</p>'
            f'<p class="k">{_e(pergunta["titulo"])}</p>'
            f'<p class="faixa">{limite} {_numero(faixa["bom_ate"])}'
            f' · ruim a partir de {_numero(faixa["ruim_a_partir"])}</p>'
            f'<p class="f">fonte: {_e(resposta.get("fonte"))}</p></div>')


def _instrumentos(alvos):
    """Mostrador só onde a pergunta declara faixa. O resto vira cartão de insight, sem agulha."""
    from lib.perguntas import PERGUNTAS

    medidores = []
    for alvo in alvos:
        for componente in alvo.get("componentes", []):
            for resposta in componente.get("respostas", []):
                pergunta = PERGUNTAS.get(resposta.get("pergunta"), {})
                if resposta.get("sem_dados") or not pergunta.get("faixa"):
                    continue
                medidores.append(_medidor(resposta, pergunta))
    if not medidores:
        return ('<p class="muted">nenhuma medida com tolerância declarada respondeu nesta '
                'rodada.</p>')
    return f'<div class="medidores">{"".join(medidores)}</div>'


def _selos(inventario):
    """Estado por alvo, em palavra e com ponto — emoji some na impressão em preto e branco."""
    contagem = {}
    for item in inventario:
        contagem[item.get("saude")] = contagem.get(item.get("saude"), 0) + 1
    selos = []
    for estado, qtd in sorted(contagem.items()):
        palavra, classe = ESTADO_EM_PALAVRA.get(estado, (str(estado), "na"))
        selos.append(f'<span class="selo {classe}"><i></i>{qtd} {_e(palavra.lower())}</span>')
    return "".join(selos)


def render_html_v3(r):
    ctx = montar_contexto(r)
    quantos = len(ctx["inventario"])
    titulo = f"Auditoria de infraestrutura — {quantos} alvo" + ("s" if quantos != 1 else "")
    repl = {
        "%%TITLE%%": _e(titulo),
        "%%GENERATED_AT%%": _e(_quando(ctx["gerado_em"])),
        "%%PANORAMA_LINHA%%": _e(_plural(ctx["panorama"]["achados"], "achado", "achados")),
        "%%PANORAMA%%": _panorama(ctx["panorama"]),
        "%%RESUMO%%": (f"<p>{_rich(ctx['resumo'])}</p>" if ctx["resumo"]
                       else '<p class="muted">resumo ainda não escrito.</p>'),
        "%%INVENTARIO%%": _inventario(ctx["inventario"]),
        "%%SUMARIO%%": _sumario(ctx),
        "%%SELOS%%": _selos(ctx["inventario"]),
        "%%TOPOLOGIA%%": _topologia(ctx["alvos"]),
        "%%INSTRUMENTOS%%": _instrumentos(ctx["alvos"]),
        "%%INSIGHTS%%": _insights_v3(ctx["alvos"]),
        "%%IMPACTO%%": _impacto_v3(ctx["alvos"]),
        "%%ACHADOS%%": _achados_com_remediacao(ctx["achados"]),
        "%%ACEITES%%": _aceites_v3(ctx["aceites"]),
        "%%RECOMENDACOES%%": _recomendacoes_v3(ctx["recomendacoes"]),
        "%%FORTES%%": _list(ctx["fortes"]),
        "%%FRACOS%%": _list(ctx["fracos"]),
        "%%ALVOS%%": _alvos_v3(ctx["alvos"]),
        "%%HISTORICO%%": _historico_v3(ctx["historico"]),
    }
    with open(TEMPLATE_V3, encoding="utf-8") as f:
        pagina = f.read()
    # UMA passada: substituir em laço reprocessaria o texto já inserido, e um `%%ALVOS%%` escrito
    # pelo agente injetaria uma seção inteira no relatório
    return re.sub(r"%%[A-Z_]+%%", lambda m: repl.get(m.group(0), m.group(0)), pagina)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--formato", default="html+pdf", choices=FORMATOS,
                    help="html (só a página) ou html+pdf (padrão)")
    args = ap.parse_args(argv)
    d = os.path.expanduser(args.dir)
    with open(os.path.join(d, "report.json"), encoding="utf-8") as f:
        report = json.load(f)
    try:
        res = build(report, d, formato=args.formato)
    except ValueError as erro:                 # schema que este build não lê
        print(str(erro), file=sys.stderr)
        return 2
    print(res["html"])
    if res["pdf"]:
        print(res["pdf"])
    elif args.formato == "html+pdf":
        print("PDF não gerado (sem Chromium) — HTML entregue.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

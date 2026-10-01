#!/usr/bin/env python3
"""build_report.py — report.json (schema v1) → HTML self-contained (primário) → PDF (opt-in).

Uso: python3 build_report.py --dir <out_dir>   # lê <dir>/report.json, escreve relatorio.html [+ .pdf]

Sem acesso a rede (o único módulo com rede é lib/http_get.py, usado só na coleta). O PDF é
gerado se houver Chromium/Chrome (headless, offline); senão entrega o HTML e avisa.
"""
import argparse
import base64
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


def _inline(trecho):
    """Negrito e código inline, sobre texto JÁ escapado. Nada aqui abre tag."""
    trecho = re.sub(r"`([^`]+)`", r"<code>\1</code>", trecho)
    trecho = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", trecho)
    return (trecho.replace("&lt;strong&gt;", "<strong>")
                  .replace("&lt;/strong&gt;", "</strong>"))


_MARCA_NUM = re.compile(r"\d+[.)]\s+")
_MARCA_PONTO = re.compile(r"[-*]\s+")


def _marca(linha):
    """("ol", tamanho) / ("ul", tamanho) quando a linha abre item de lista; (None, 0) se não."""
    for tipo, marca in (("ol", _MARCA_NUM), ("ul", _MARCA_PONTO)):
        casado = marca.match(linha)
        if casado:
            return tipo, casado.end()
    return None, 0


def _blocos_de_texto(trecho):
    """Parágrafos e listas de um pedaço que não contém bloco de código.

    Regras do markdown padrão, porque este renderizador também desenha o texto que o AGENTE
    escreve (resumo, análise), e ele quebra linha onde quiser:
      - a lista só começa no início do bloco ou depois de uma linha que termina em `:` —
        "cresceu em\\n- 40% na última hora" é uma frase, não uma lista;
      - dentro da lista, linha sem marcador CONTINUA o item (continuação preguiçosa), com ou
        sem indentação. Para encerrar a lista, deixa-se uma linha em branco.
    """
    saida = []
    for bloco in re.split(r"\n\s*\n", trecho):
        linhas = [linha.strip() for linha in bloco.splitlines() if linha.strip()]
        paragrafo, i = [], 0
        while i < len(linhas):
            tipo, _ = _marca(linhas[i])
            pode_abrir = not paragrafo or paragrafo[-1].endswith(":")
            if tipo and pode_abrir:
                if paragrafo:
                    saida.append(f"<p>{_inline(' '.join(paragrafo))}</p>")
                    paragrafo = []
                itens = []
                while i < len(linhas):
                    tipo_da_linha, fim = _marca(linhas[i])
                    if tipo_da_linha == tipo:
                        itens.append(linhas[i][fim:])
                    else:
                        itens[-1] += " " + linhas[i]
                    i += 1
                saida.append(f"<{tipo}>" + "".join(f"<li>{_inline(item)}</li>" for item in itens)
                             + f"</{tipo}>")
            else:
                paragrafo.append(linhas[i])
                i += 1
        if paragrafo:
            saida.append(f"<p>{_inline(' '.join(paragrafo))}</p>")
    return "".join(saida)


def _rich(text):
    """Subconjunto de markdown da remediação: parágrafo, lista, bloco de código, negrito e
    código inline. Tudo é ESCAPADO antes — o conteúdo vem de arquivo, e nada nele abre tag.

    O template sempre teve CSS para `.fix ol` e `.fix pre`. O renderizador achatava tudo num
    parágrafo só, com as crases e o "1." no meio do texto corrido: o desenho existia para um
    HTML que nunca era gerado.
    """
    if text is None:
        return ""
    escapado = _e(str(text))
    # O bloco de código é fatiado primeiro: dentro dele, "-" e "1." são código, não lista.
    pedacos = re.split(r"```[a-zA-Z0-9_-]*\n?(.*?)```", escapado, flags=re.S)
    partes = []
    for i, pedaco in enumerate(pedacos):
        if i % 2:
            partes.append(f"<pre>{pedaco.rstrip()}</pre>")
        else:
            partes.append(_blocos_de_texto(pedaco))
    return "".join(parte for parte in partes if parte)


def _list(items):
    items = [i for i in (items or []) if i]
    if not items:
        return '<p class="muted">—</p>'
    return "<ul>" + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>"


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
        return ('<h4 class="hsub">Disco</h4>'
                f'<p class="muted">não coletado — {_e(disk.get("reason"))}</p>')
    if not disk:
        return ""
    rows = [[_e(d.get("tipo")), _e(d.get("total")), _e(d.get("ativo")),
             _e(d.get("tamanho")), _e(d.get("recuperavel"))] for d in disk]
    return ('<h4 class="hsub">Disco — nó conectado</h4>'
            + _table(["Tipo", "Total", "Ativos", "Tamanho", "Recuperável"], rows,
                     [None, "num", "num", "num", "num"]))


def _tls(tls):
    """Validade dos certificados TLS do context — sempre exibida quando há TLS."""
    if isinstance(tls, dict) and tls.get("status") == "n/a":
        return ('<h4 class="hsub">Certificados TLS</h4>'
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
    if not rows:
        return ""                          # tabela só com cabeçalho não informa nada
    return ('<h4 class="hsub">Certificados TLS do acesso ao cluster</h4>'
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
        for s in sorted(g.get("services") or [], key=lambda x: x.get("name") or ""):
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
        rotas = g.get("routes") or []
        routes = " · ".join(rotas[:3]) + (f" +{len(rotas) - 3}" if len(rotas) > 3 else "")
        badges = ""
        if g.get("findings_high"):
            badges += (f'<span class="badge high">'
                       f'{_plural(g["findings_high"], "crítico", "críticos")}</span>')
        if g.get("findings_med"):
            badges += (f'<span class="badge med">'
                       f'{_plural(g["findings_med"], "médio", "médios")}</span>')
        if g.get("spofs"):
            badges += f'<span class="badge low">{len(g["spofs"])} sem HA</span>'
        notes = [comp_an.get(s.get("name")) for s in g["services"] if comp_an.get(s.get("name"))]
        note_html = ('<div class="an">' + " ".join(_e(n) for n in notes) + "</div>") if notes else ""
        out.append(
            f'<div class="card stack {g.get("note", "")}"><div class="sh"><span class="dot"></span>'
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

# 60s bastavam para um relatório pequeno; o de 213 achados converte em ~1,3s, mas um
# relatório muito maior não tem por que morrer por causa de um número apertado.
PDF_TIMEOUT = 180


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

    pdf_path, pdf_motivo = None, None
    if formato == "html+pdf":
        chrome = find_chromium()
        if not chrome:
            pdf_motivo = ("Chromium não encontrado nesta máquina — instale o chromium "
                          "ou o google-chrome para gerar o PDF.")
        else:
            destino = os.path.join(out_dir, "relatorio.pdf")
            try:
                subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                                "--no-pdf-header-footer", f"--print-to-pdf={destino}",
                                f"file://{os.path.abspath(html_path)}"],
                               check=True, capture_output=True, timeout=PDF_TIMEOUT)
                pdf_path = destino
            except subprocess.TimeoutExpired:
                # Relatório grande demais para o tempo dado. Dizer "sem Chromium" aqui mandaria
                # o operador instalar o que já está instalado.
                pdf_motivo = (f"o Chromium passou de {PDF_TIMEOUT}s convertendo a página e o "
                              f"tempo esgotou — o HTML está pronto.")
            except (subprocess.SubprocessError, OSError) as erro:
                pdf_motivo = f"a conversão falhou: {type(erro).__name__}: {erro}"
    return {"html": html_path, "pdf": pdf_path, "pdf_motivo": pdf_motivo}


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


def _estado(saude):
    """Estado em PALAVRA, com o ponto colorido ao lado: emoji some na impressão em preto e
    branco e exige legenda que ninguém lê."""
    palavra, classe = ESTADO_EM_PALAVRA.get(saude, (str(saude), "na"))
    return f'<span class="chip {classe}"><i class="dot"></i>{_e(palavra)}</span>'


def _quando(carimbo):
    """`2026-09-19T10:00:00Z` → `19/09/2026 10:00 UTC`. O carimbo ISO é para o histórico
    comparar; quem lê o relatório lê data."""
    from datetime import datetime
    try:
        instante = datetime.fromisoformat(str(carimbo).replace("Z", "+00:00"))
    except ValueError:
        return str(carimbo)
    return instante.strftime("%d/%m/%Y %H:%M UTC")


def _numero(valor):
    """12480 → 12.480. Número grande sem separador é número que ninguém lê.

    Coleção nunca é despejada: o nó da topologia passava a lista de filas inteira por aqui, e o
    PDF ganhava três páginas do `repr` do Python dentro de um cartão.
    """
    if isinstance(valor, (list, dict)):
        return _e(f"{len(valor)} itens")
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return _e(valor)
    if isinstance(valor, int):
        return _e(f"{valor:,}".replace(",", "."))
    return _e(f"{valor:,.2f}".replace(",", "@").replace(".", ",").replace("@", "."))


# O corte de exibição mora aqui, e não na extração: o limiar precisa ver a população INTEIRA
# (com o corte na extração, 300 filas órfãs atrás de 10 filas cheias davam zero achados). O
# relatório mostra as primeiras, na ordem que a extração decidiu, e diz quantas ficaram de fora;
# a lista completa continua no report.json.
LIMITE_NO_RELATORIO = 10
# Campos que existem para o PROGRAMA, não para quem lê: `objeto` é a identidade composta
# (`nome@vhost`) usada em achado e aceite, e repetiria as colunas nome e vhost lado a lado.
_FORA_DA_TABELA = {"objeto"}


def _rodape_do_corte(total):
    fora = total - LIMITE_NO_RELATORIO
    if fora <= 0:
        return ""
    return (f'<p class="corte">e mais {fora} — a lista completa, com todas as {total}, está no '
            f'<code>report.json</code></p>')


def _celula(valor):
    if valor is None:
        return "<td>—</td>"
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return f"<td>{_numero(valor)}</td>"
    return f"<td>{_e(valor)}</td>"


def _tabela_de_campos(itens):
    """Lista cujos itens têm VÁRIOS campos: tabela densa, uma linha por item.

    `_ranking` desenha `{chave, valor}` com barra proporcional — desenhar `{nome, prontas,
    consumidores}` daquele jeito dava rótulo vazio, valor zero e barras iguais: um gráfico
    bonito dizendo nada.
    """
    colunas = [nome for nome in itens[0] if nome not in _FORA_DA_TABELA]
    cabecalho = "".join(f"<th>{_e(nome.replace('_', ' '))}</th>" for nome in colunas)
    linhas = "".join(f"<tr>{''.join(_celula(item.get(nome)) for nome in colunas)}</tr>"
                     for item in itens[:LIMITE_NO_RELATORIO])
    return (f'<table class="campos"><thead><tr>{cabecalho}</tr></thead>'
            f'<tbody>{linhas}</tbody></table>{_rodape_do_corte(len(itens))}')


def _ranking(itens):
    total = len(itens)
    itens = itens[:LIMITE_NO_RELATORIO]
    maior = max((i.get("valor") or 0 for i in itens), default=0) or 1
    linhas = []
    for item in itens:
        largura = 100 * (item.get("valor") or 0) / maior
        linhas.append(f'<div class="rk"><span class="lb">{_e(item.get("chave"))}</span>'
                      f'<span class="vl">{_numero(item.get("valor"))}</span>'
                      f'<span class="bar"><i style="width:{largura:.0f}%"></i></span></div>')
    return f'<div class="rank">{"".join(linhas)}</div>{_rodape_do_corte(total)}'


def _resposta(resposta):
    from lib.perguntas import PERGUNTAS

    pergunta = PERGUNTAS.get(resposta.get("pergunta"), {})
    titulo = _e(pergunta.get("titulo") or resposta.get("pergunta"))
    if resposta.get("sem_dados") or resposta.get("erro_interno"):
        return (f'<div class="semdados"><b>{titulo}</b> — {_e(resposta.get("motivo"))}</div>')
    valor = resposta.get("valor")
    if isinstance(valor, list):
        # numa lista, a unidade vale para cada linha — repeti-la embaixo só confunde.
        # Item de {chave, valor} é ranking com barra; item de vários campos é tabela.
        if not valor:
            corpo = '<p class="muted">nenhuma linha — a consulta respondeu com a lista vazia.</p>'
        elif isinstance(valor[0], dict) and set(valor[0]) <= {"chave", "valor"}:
            corpo = _ranking(valor)
        else:
            corpo = _tabela_de_campos(valor)
    else:
        unidade = pergunta.get("unidade")
        sufixo = f' <span class="un">{_e(unidade)}</span>' if unidade else ""
        corpo = f'<span class="v">{_numero(valor)}</span>{sufixo}'
    return (f'<div class="insight"><div class="ih"><b>{titulo}</b>'
            f'<span class="src">fonte: {_e(resposta.get("fonte"))}</span></div>'
            f'{corpo}</div>')


def _insights_v3(alvos):
    """Um cartão por componente que TEM o que dizer: papel, análise e cada resposta com a FONTE.

    Número sem fonte não entra no relatório — é isso que separa dado de chute, e é o que
    permite ao leitor saber se "0 requisições" quer dizer "não houve tráfego" ou "ninguém
    perguntou".

    Componente sem resposta e sem análise não ganha cartão. Ele ganhava, e o cartão dizia
    "nenhuma pergunta para este papel nesta versão" — numa auditoria de 57 componentes isso
    imprimia a mesma frase 57 vezes, seis páginas A4. A informação não some: ela é contada,
    uma vez, em "O que falta declarar".
    """
    blocos, calados = [], 0
    for alvo in alvos:
        for componente in alvo.get("componentes", []):
            respostas = "".join(_resposta(r) for r in componente.get("respostas", []))
            analise = (f'<p class="an">{_rich(componente["analise"])}</p>'
                       if componente.get("analise") else "")
            if not respostas and not analise:
                calados += 1
                continue
            blocos.append(
                f'<div class="card comp"><div class="sys">'
                f'<span class="tag">{_e(componente.get("papel"))}</span>'
                f'<h3>{_e(componente.get("nome"))}</h3>'
                f'<span class="dono">{_e(alvo.get("nome"))}</span></div>'
                f'{analise}{respostas}</div>')
    rodape = (f'<p class="muted">Outros {calados} componentes não receberam pergunta nesta '
              f'rodada — o motivo de cada um está em <a href="#pendencias">O que falta '
              f'declarar</a>.</p>') if calados else ""
    if not blocos:
        return (rodape or '<p class="muted">nenhum componente respondeu nesta rodada.</p>')
    return "".join(blocos) + rodape


def _remediacao(bloco):
    if not bloco:
        return ""
    return (f'<div class="fix"><p class="fix-h">Como resolver</p>'
            f'{_rich(bloco.get("como_resolver"))}'
            f'<p class="val"><b>Como confirmar:</b> {_rich(bloco.get("como_confirmar"))}</p>'
            f'<p class="nao"><b>Quando não fazer:</b> {_rich(bloco.get("quando_nao_fazer"))}</p>'
            f'</div>')


def agrupar_achados(achados):
    """Achados da mesma regra viram UM bloco, sem que nenhuma ocorrência saia do relatório.

    Uma auditoria real trouxe 213 achados — 75 deles da mesma regra, com um único detalhe
    distinto entre os 75. Desenhados um a um, com a remediação repetida em cada, davam 121
    páginas A4 de repetição. O agrupamento tira a repetição, não o dado.

    A chave é (regra, severidade), não a regra sozinha: um aceite rebaixa a severidade de UMA
    ocorrência, e fundir as duas faria o relatório anunciar gravidade que aquela ocorrência
    não tem.

    `detalhe_comum` só existe quando TODAS as ocorrências dizem a mesma frase — aí ela vale uma
    vez, no cabeçalho. Quando o detalhe varia (`4 tasks falharam` × `20 tasks falharam`), ele é
    o dado, e fica na linha de cada ocorrência.
    """
    grupos = {}
    for achado in achados:
        chave = (achado.get("regra"), achado.get("severidade"))
        grupos.setdefault(chave, []).append(achado)

    saida = []
    for (regra, severidade), itens in grupos.items():
        detalhes = {item.get("detalhe") or "" for item in itens}
        comum = detalhes.pop() if len(detalhes) == 1 else None
        primeira = itens[0].get("como_resolver") or {}
        saida.append({
            "regra": regra,
            "severidade": severidade,
            "titulo": primeira.get("titulo") or regra,
            "por_que_importa": primeira.get("por_que_importa") or "",
            "como_resolver": primeira,
            "detalhe_comum": comum or None,
            "ocorrencias": [{
                "objeto": item.get("objeto"),
                "alvo": item.get("alvo"),
                "componente": item.get("componente"),
                "aceite_vencido": item.get("aceite_vencido"),
                "detalhe_proprio": None if comum else (item.get("detalhe") or ""),
            } for item in itens],
        })

    saida.sort(key=lambda g: (ORDEM_SEVERIDADE.index(g["severidade"])
                              if g["severidade"] in ORDEM_SEVERIDADE else len(ORDEM_SEVERIDADE),
                              -len(g["ocorrencias"]), g["regra"] or ""))
    return saida


def _linha_de_ocorrencia(ocorrencia, mostra_alvo):
    """Uma ocorrência é uma LINHA, não um cartão. É o que faz 75 caberem numa página."""
    onde = _e(ocorrencia.get("objeto") or ocorrencia.get("componente") or "")
    celulas = [f'<td class="oc-o">{onde}</td>']
    if mostra_alvo:
        celulas.append(f'<td class="oc-a">{_e(ocorrencia.get("alvo") or "")}</td>')
    if ocorrencia.get("detalhe_proprio"):
        celulas.append(f'<td class="oc-d">{_e(ocorrencia["detalhe_proprio"])}</td>')
    if ocorrencia.get("aceite_vencido"):
        celulas.append('<td class="oc-v"><span class="chip bad">aceite vencido</span></td>')
    return f'<tr>{"".join(celulas)}</tr>'


def _achados_com_remediacao(achados):
    if not achados:
        return '<p class="muted">nenhum achado nesta rodada.</p>'
    blocos = []
    for grupo in agrupar_achados(achados):
        n = len(grupo["ocorrencias"])
        mostra_alvo = len({oc.get("alvo") for oc in grupo["ocorrencias"]}) > 1
        contagem = "1 ocorrência" if n == 1 else f"{n} ocorrências"
        descricao = grupo["por_que_importa"] or grupo["detalhe_comum"] or ""
        detalhe = (f'<p class="grp-c">{_e(grupo["detalhe_comum"])}</p>'
                   if grupo["detalhe_comum"] and grupo["por_que_importa"] else "")
        linhas = "".join(_linha_de_ocorrencia(oc, mostra_alvo)
                         for oc in grupo["ocorrencias"])
        blocos.append(
            f'<div class="grp {_e(grupo["severidade"])}">'
            f'<div class="grp-h"><b>{_e(grupo["titulo"])}</b>'
            f'<span class="sev">{_e(ROTULO_SEVERIDADE.get(grupo["severidade"], ""))}</span>'
            f'<span class="grp-n">{contagem}</span>'
            f'<code class="grp-r">{_e(grupo["regra"])}</code></div>'
            f'<div class="grp-d">{_rich(descricao)}</div>{detalhe}'
            f'{_remediacao(grupo["como_resolver"])}'
            f'<table class="ocs">{linhas}</table>'
            f'</div>')
    return "".join(blocos)


CAMADAS = (("entrada", "recebe o tráfego"), ("app", "processa"),
           ("fila", "enfileira"), ("banco", "guarda"), ("cache", "guarda"),
           ("busca", "guarda"), ("storage", "guarda"),
           ("observabilidade", "observa"))


def _no_da_topologia(alvo, componente):
    """Um nó: nome, papel, quantos achados abertos e a leitura que tiver."""
    abertos = len(componente.get("achados") or [])
    classe = "bad" if abertos >= 2 else ("at" if abertos else "ok")
    from lib.perguntas import PERGUNTAS

    from lib.perguntas import ORDEM

    respostas = [r for r in componente.get("respostas", []) if not r.get("sem_dados")]
    # A leitura do nó é a primeira resposta ESCALAR; se não houver, a contagem da pergunta que
    # descreve a população do papel (a primeira dele — em `fila`, "Filas"). O tamanho de outra
    # lista qualquer não é contagem de nada: com "Filas" sem dados, o nó dizia "Consumidores por
    # fila: 10" — o tamanho do corte apresentado como fato.
    populacao = (ORDEM.get(componente.get("papel")) or [None])[0]
    escalar = next((r for r in respostas if not isinstance(r.get("valor"), list)), None)
    lista = next((r for r in respostas if r["pergunta"] == populacao
                  and isinstance(r.get("valor"), list)), None)
    leitura = ""
    if escalar or lista:
        escolhida = escalar or lista
        titulo = PERGUNTAS.get(escolhida["pergunta"], {}).get("titulo", "")
        valor = escolhida.get("valor")
        mostrado = _numero(len(valor)) if isinstance(valor, list) else _numero(valor)
        leitura = f'<p class="leitura">{_e(titulo)}: {mostrado}</p>'
    elif componente.get("respostas"):
        leitura = '<p class="leitura vazio">sem leitura nesta rodada</p>'
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


def pendencias_de_declaracao(alvos):
    """Por que o relatório está calado — e o que o dono escreve para ele falar.

    São duas lacunas diferentes, e a segunda é a que passava despercebida:

    1. O componente RECEBEU pergunta e respondeu `sem_dados`. O motivo já vem pronto do
       adaptador ("não declara `metricas_url`").
    2. O componente não recebeu pergunta NENHUMA, porque o papel dele ainda não tem pergunta
       registrada. Isso não gera `sem_dados` — gera lista vazia. O componente aparecia no
       relatório com nome, papel e mais nada, e ninguém sabia se era falta de dado, falta de
       acesso ou defeito da skill.
    """
    from lib.perguntas import do_papel

    por_motivo = {}
    for alvo in alvos:
        for componente in alvo.get("componentes", []):
            papel = componente.get("papel", "app")
            respostas = componente.get("respostas") or []
            if not respostas:
                if not do_papel(papel):
                    motivo = (f"o papel `{papel}` ainda não tem nenhuma pergunta registrada "
                              f"nesta versão da skill")
                    por_motivo.setdefault((motivo, papel), []).append(
                        {"alvo": alvo.get("nome"), "componente": componente.get("nome")})
                continue
            for resposta in respostas:
                if not resposta.get("sem_dados"):
                    continue
                motivo = resposta.get("motivo") or "sem motivo registrado"
                por_motivo.setdefault((motivo, papel), []).append(
                    {"alvo": alvo.get("nome"), "componente": componente.get("nome")})

    pendencias = []
    for (motivo, papel), componentes in por_motivo.items():
        vistos, unicos = set(), []
        for item in componentes:
            chave = (item["alvo"], item["componente"])
            if chave not in vistos:
                vistos.add(chave)
                unicos.append(item)
        pendencias.append({"motivo": motivo, "papel": papel, "componentes": unicos})
    pendencias.sort(key=lambda p: (-len(p["componentes"]), p["papel"], p["motivo"]))
    return pendencias


def _pendencias(alvos):
    pendencias = pendencias_de_declaracao(alvos)
    if not pendencias:
        return ('<p class="muted">todo componente inventariado respondeu às perguntas do seu '
                'papel — não há lacuna de declaração nesta rodada.</p>')
    blocos = []
    for pendencia in pendencias:
        nomes = ", ".join(_e(c["componente"]) for c in pendencia["componentes"][:14])
        resto = len(pendencia["componentes"]) - 14
        if resto > 0:
            nomes += f" <span class=\"muted\">e mais {resto}</span>"
        blocos.append(
            f'<div class="pend">'
            f'<div class="pend-h"><code class="papel">{_e(pendencia["papel"])}</code>'
            f'<span class="grp-n">{_plural(len(pendencia["componentes"]), "componente", "componentes")}</span></div>'
            f'<p class="pend-m">{_inline(_e(pendencia["motivo"]))}</p>'
            f'<p class="pend-c">{nomes}</p></div>')
    return "".join(blocos)


# =====================================================================================
# RELATORIO POR ACAO. O relatorio antigo agrupava achado por gravidade, e quem recebia
# tinha de traduzir "107 medios" em "o que eu faco hoje". Aqui a pergunta ja vem
# respondida: tres faixas de acao, e a faixa e o titulo da secao.
# =====================================================================================

FONTES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "assets", "report-template", "fontes")

# As tres sao variaveis: um arquivo cobre toda a faixa de peso. OFL 1.1 — ver
# assets/report-template/fontes/LICENCAS.md
_FONTES = (("Bricolage Grotesque", "bricolage-grotesque-latin.woff2", "400 800"),
           ("Figtree", "figtree-latin.woff2", "300 900"),
           ("JetBrains Mono", "jetbrains-mono-latin.woff2", "100 800"))


def _fontes():
    """As fontes viajam DENTRO do HTML, em base64: o PDF e gerado por um Chromium sem
    rede, e `@font-face` apontando para fora sairia com a fonte do sistema.

    Faltando um arquivo, o relatorio sai com a fonte do sistema e segue — relatorio nao
    deixa de ser gerado por causa de tipografia.
    """
    regras = []
    for familia, arquivo, pesos in _FONTES:
        try:
            with open(os.path.join(FONTES_DIR, arquivo), "rb") as f:
                dados = base64.b64encode(f.read()).decode("ascii")
        except OSError:
            continue
        regras.append(f"@font-face{{font-family:'{familia}';font-style:normal;"
                      f"font-weight:{pesos};font-display:swap;"
                      f"src:url(data:font/woff2;base64,{dados}) format('woff2')}}")
    return "<style>" + "".join(regras) + "</style>" if regras else ""


def _ic(nome):
    return f'<svg class="ic"><use href="#ic-{nome}"/></svg>'


_CLASSE_FAIXA = {"bom": "bom", "atencao": "mal", "ruim": "mal", "sem_dados": "nao"}


def _alvo_principal(alvos):
    """O alvo que a rodada realmente mediu. Alvo declarado e nao confirmado aparece
    depois, em `.fora` — o inventario nao mente por omissao, mas tambem nao finge
    que ha dado onde nao houve."""
    com_dado = [a for a in alvos if (a.get("fatos") or a.get("dimensoes"))]
    return max(com_dado, key=lambda a: len(a.get("achados") or []), default=None)


def _linha(rotulo, valor, classe="n"):
    return f'<div class="l"><span>{_e(rotulo)}</span><b class="{classe}">{_e(valor)}</b></div>'


def _cartao_estado(alvo):
    """Os tres blocos da capa, na ordem em que a pergunta aparece: a infra esta de pe?
    o fluxo da aplicacao esta andando? e o que NAO afeta o servico agora?

    Separar o terceiro bloco e o ponto: reinicio recuperado e achado de higiene nao
    podem dividir espaco com fila parada, senao tudo vira a mesma urgencia.
    """
    if alvo is None:
        return '<div class="alvo-card"><p class="nome">Sem alvo medido</p></div>'
    fatos = alvo.get("fatos") or {}
    dims = alvo.get("dimensoes") or {}
    op = dims.get("operacao") or {}
    nos = fatos.get("nodes") or []
    prontos = sum(1 for n in nos if str(n.get("state", "")).lower() == "ready")
    fora = op.get("nodes_down", 0)

    infra_ok = not fora and not op.get("failing") and not op.get("stopped")
    blocos = [
        f'<div class="chk {"ok" if infra_ok else "mal"}">'
        f'<p class="ch2">{_ic("bom" if infra_ok else "achado")}<b>Infraestrutura</b>'
        f'<em>{"operando" if infra_ok else "com divergência"}</em></p>'
        + (_linha("Nós prontos", f"{prontos} de {len(nos)}") if nos else "")
        + _linha("Serviços no ar", f'{op.get("services_up", 0)} de {op.get("services_total", 0)}')
        + _linha("Réplicas abaixo do desejado", op.get("stopped", 0))
        + _linha("Nós fora do ar", fora)
        + "</div>"
    ]

    # fluxo da aplicacao: o que esta parado APESAR de a infra estar de pe
    filas = [a for a in (alvo.get("achados") or []) if a.get("regra") == "fila_sem_consumidor"]
    presas = 0
    for a in filas:
        m = re.search(r"acumuladas:\s*(\d+)", str(a.get("detalhe") or ""))
        if m:
            presas += int(m.group(1))
    if filas:
        blocos.append(
            f'<div class="chk mal"><p class="ch2">{_ic("fila")}<b>Fluxo de aplicação</b>'
            f'<em>{_plural(len(filas), "fila parada", "filas paradas")}</em></p>'
            + _linha("Filas sem consumidor", len(filas))
            + _linha("Mensagens acumuladas", _human(presas))
            + "</div>")

    # o que NAO afeta o servico agora — existe para nao virar urgencia
    higiene = [a for a in (alvo.get("achados") or []) if a.get("severidade") in ("low", "info")]
    blocos.append(
        f'<div class="chk nao"><p class="ch2">{_ic("historico")}<b>Não afeta o serviço agora</b></p>'
        + _linha("Achados de higiene", f'{len(higiene)} de {len(alvo.get("achados") or [])}')
        + _linha("Práticas com cobertura", f'{(dims.get("higiene") or {}).get("pinned_pct", 0)}% fixadas')
        + "</div>")

    selos = f'<p class="tags">{_selos_do_alvo(alvo)}</p>'
    blocos.append(selos)
    onde = alvo.get("onde") or ""
    quantos = len(nos)
    ctx = f'{_e(onde)}' + (f' · {quantos} nó{"s" if quantos != 1 else ""}' if quantos else "")
    return (f'<div class="alvo-card"><p class="nome">{_ic("cluster")}{_e(alvo.get("nome"))}</p>'
            f'<p class="ctx">{ctx}</p>' + "".join(blocos) + "</div>")


def _selos_do_alvo(alvo):
    """O estado em PALAVRA. O emoji some na impressao em preto e branco e passa a exigir
    uma legenda que o relatorio nao tem."""
    palavra, classe = ESTADO_EM_PALAVRA.get(alvo.get("saude"), (str(alvo.get("saude")), "na"))
    return f'<span class="tag {classe}">{_e(palavra)}</span>'


def _kpis_novo(alvo, triagem):
    """Os numeros que decidem se vale ler o resto. Verde quando a medida esta cheia,
    vermelho quando falta — a cor aqui e informacao, nao enfeite."""
    if alvo is None:
        return ""
    dims = alvo.get("dimensoes") or {}
    op, hig = dims.get("operacao") or {}, dims.get("higiene") or {}
    total = op.get("services_total", 0)
    agir = len(triagem["faixas"]["agir"]["achados"])
    itens = [
        (f'{op.get("services_up", 0)}/{total}', "Serviços no ar", op.get("services_up") == total and total),
        (str(agir), "Exigem ação hoje", agir == 0),
        (f'{hig.get("nonroot_pct", 0)}%', "Containers não root", hig.get("nonroot_pct", 0) >= 70),
        (f'{hig.get("healthcheck_pct", 0)}%', "Com healthcheck", hig.get("healthcheck_pct", 0) >= 70),
        (f'{hig.get("pinned_pct", 0)}%', "Imagens com versão fixa", hig.get("pinned_pct", 0) >= 70),
    ]
    celulas = "".join(f'<div><p class="v n {"bom" if bom else "mal"}">{_e(v)}</p>'
                      f'<p class="lb">{_e(rot)}</p></div>' for v, rot, bom in itens)
    return f'<div class="kpis">{celulas}</div>'


def _dimensoes_novo(alvo):
    """Quatro barras, cada uma com o veredito em palavra E a evidencia que o sustenta.
    A barra sozinha e um numero sem fonte."""
    from lib.nota import ORDEM, ROTULO, VEREDITO, PISO, pontuacoes
    dims = (alvo or {}).get("dimensoes") or {}
    pts = pontuacoes(dims)
    cartoes = []
    for chave in ORDEM:
        p, d = pts.get(chave), dims.get(chave) or {}
        if p is None:
            cartoes.append(f'<div class="dim nao"><div class="dt"><b>{_e(ROTULO[chave])}</b>'
                           f'<span class="p">—</span></div>'
                           f'<p class="ver">não medido nesta rodada</p></div>')
            continue
        bom, ruim = VEREDITO[chave]
        classe = "bom" if p >= PISO else "mal"
        cartoes.append(
            f'<div class="dim {classe}"><div class="dt"><b>{_e(ROTULO[chave])}</b>'
            f'<span class="p n">{p}</span></div>'
            f'<div class="tr"><i style="width:{p}%"></i></div>'
            f'<p class="ver">{_e(bom if p >= PISO else ruim)}</p>'
            f'<p class="ev">{_evidencia(chave, d)}</p></div>')
    return f'<div class="dgrid">{"".join(cartoes)}</div>'


def _evidencia(chave, d):
    """De onde o numero saiu — escrito por extenso, porque numero sem fonte nao existe."""
    if chave == "operacao":
        return _e(f'{d.get("services_up", 0)} de {d.get("services_total", 0)} serviços no ar · '
                  f'{d.get("nodes_down", 0)} nó fora · {d.get("stopped", 0)} abaixo do desejado')
    if chave == "disponibilidade":
        n = len(d.get("spof_stateful") or []) + len(d.get("spof_critical") or [])
        return _e(f'{d.get("ha_pct", 0)}% com 2+ réplicas · {n} sem reserva')
    if chave == "seguranca":
        return _e(f'{d.get("high", 0)} achados altos · {d.get("med", 0)} médios · '
                  f'{d.get("expected", 0)} esperados')
    return _e(f'{d.get("pinned_pct", 0)}% fixadas · {d.get("nonroot_pct", 0)}% não root · '
              f'{d.get("limits_pct", 0)}% com limite · {d.get("healthcheck_pct", 0)}% com healthcheck')


_DEGRAU_CLASSE = {"total": "k0", "acionaveis": "k3", "registrar": "k3",
                  "programar": "k2", "agir": "k1"}


def _cascata(degraus):
    """O funil do universo coletado ate o que exige acao hoje. A largura e sempre
    relativa ao TOTAL — barra normalizada por degrau faria 7 parecer tanto quanto 219."""
    total = max((d["n"] for d in degraus), default=0) or 1
    barras = "".join(
        f'<div class="b {_DEGRAU_CLASSE.get(d["id"], "k3")}">'
        f'<span class="nm">{_e(d["rotulo"])}</span>'
        f'<span class="tr"><i style="width:{100 * d["n"] / total:.1f}%"></i></span>'
        f'<span class="vl n">{d["n"]}<em>{_e(d["nota"])}</em></span></div>' for d in degraus)
    return f'<div class="casc">{barras}</div>'


def _nos_novo(nos):
    """Um cartao por no. Falha nas ultimas 24h em vermelho: e o numero que separa
    'esta de pe' de 'esta de pe e saudavel'."""
    if not nos:
        return ""
    cartoes = []
    for n in nos:
        # as chaves sao as que o coletor produz (hostname/engine/tasks_running/tasks_failed);
        # inventar `name` e `engine_version` fazia o cartao sair com travessao em tudo
        lider = '<em>líder</em>' if n.get("leader") else ""
        falhas = n.get("tasks_failed")
        pronto = str(n.get("state", "")).lower() == "ready"
        linhas = [_linha("Engine", n.get("engine") or "—")]
        if n.get("capacity"):
            linhas.append(_linha("Capacidade", _fmt_capacity(n.get("capacity"))))
        if n.get("tasks_running") is not None:
            linhas.append(_linha("Tasks", n.get("tasks_running")))
        if falhas is not None:
            linhas.append(f'<div class="l"><span>Tasks falhadas</span>'
                          f'<b class="n{" mal" if falhas else ""}">{_e(falhas)}</b></div>')
        if not pronto:
            linhas.append(f'<div class="l"><span>Estado</span>'
                          f'<b class="mal">{_e(n.get("state") or "?")}</b></div>')
        cartoes.append(f'<div class="no"><p class="nh">{_ic("no")}<b>{_e(n.get("hostname"))}</b>'
                       f'{lider}</p>{"".join(linhas)}</div>')
    return f'<div class="nos">{"".join(cartoes)}</div>'


def _ancora(titulo):
    """Ancora estavel a partir do titulo: sem acento, sem espaco, sem surpresa."""
    import unicodedata
    plano = unicodedata.normalize("NFKD", str(titulo)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-") or "secao"


def _sec(icone, titulo, sub, corpo, classe="", ident=None):
    """Toda secao tem o mesmo cabecalho: icone, titulo e a linha que diz o que ele mede.

    E uma ancora. O sumario do topo e clicavel TAMBEM no PDF — o Chromium converte
    href interno em destino de pagina —, entao quem recebe o arquivo navega sem rolar
    41 paginas. Secao sem id quebra isso calada.
    """
    if not corpo:
        return ""
    return (f'<section class="sec" id="{_e(ident or _ancora(titulo))}">'
            f'<div class="sh {classe}"><span class="box">{_ic(icone)}</span>'
            f'<h2>{_e(titulo)}</h2><span class="sub">{_e(sub)}</span></div>'
            f'<div class="conteudo">{corpo}</div></section>')


_ORDEM_IMPACTO = {"alto": 0, "medio": 1, "médio": 1, "baixo": 2}


def _impacto(pontos):
    """"Se isto falhar": a consequencia a partir do que EXISTE hoje, nao previsao.

    `impact.build` roda desde o v1 e o resultado era descartado — o relatorio calculava
    a consequencia e jogava fora. Aqui ela volta, ordenada por impacto.
    """
    if not pontos:
        return ""
    ordenados = sorted(pontos, key=lambda p: (_ORDEM_IMPACTO.get(str(p.get("impacto")).lower(), 3),
                                              str(p.get("cenario") or "")))
    linhas = []
    for p in ordenados:
        alvos = p.get("alvos") or []
        peso = _plural(len(alvos), "serviço", "serviços") if alvos else (p.get("impacto") or "—")
        linhas.append(f'<div class="cen">{_ic("falhar")}<div>'
                      f'<p class="se">{_e(p.get("cenario"))}</p>'
                      f'<p class="en">{_e(p.get("consequencia"))}</p></div>'
                      f'<span class="pk n">{_e(peso)}</span></div>')
    return f'<div class="cartao">{"".join(linhas)}</div>'


# ---------------------------------------------------------------- por camada
# A ordem das camadas ja existe em CAMADAS (linha ~1195) e e UMA so: duplica-la aqui
# criou um sombreamento silencioso que fazia _topologia estourar ao desempacotar.
# Aqui vai apenas o icone de cada papel.
_ICONE_CAMADA = {"entrada": "rota", "app": "aplicacoes", "fila": "fila", "banco": "banco",
                 "cache": "banco", "busca": "banco", "storage": "disco",
                 "observabilidade": "metrica"}


def _camadas(componentes):
    """Os sistemas agrupados pelo PAPEL que cada um cumpre, e nao pela ordem alfabetica
    do nome do servico. E o que responde "o que esta rodando aqui?" sem exigir que quem
    le ja saiba o que cada nome significa.

    NAO e dependencia medida: a skill observa o papel de cada componente, nao quem chama
    quem. Dizer isso e obrigacao, nao rodape — a legenda sai junto.

    Papel que a skill nao reconhece nao some: cai em "Outros", nomeado.
    """
    if not componentes:
        return '<p class="nao">nenhum componente no inventário desta rodada.</p>'
    porpapel = {}
    for c in componentes:
        porpapel.setdefault(c.get("papel") or "app", []).append(c)

    blocos = []
    for papel, rotulo in CAMADAS:
        itens = porpapel.pop(papel, [])
        if itens:
            blocos.append(_camada_bloco(rotulo.capitalize(), papel,
                                        _ICONE_CAMADA.get(papel, "aplicacoes"), itens))
    for papel in sorted(porpapel):                      # papel fora da ordem conhecida
        blocos.append(_camada_bloco(f"Outros · {papel}", papel, "aplicacoes", porpapel[papel]))
    return ("".join(blocos) +
            '<p class="nota">As camadas agrupam por <b>papel</b> — quem recebe o tráfego, '
            'quem processa, quem guarda. <b>Não é dependência medida</b>: a skill observa '
            'o papel de cada componente, não quem chama quem.</p>')


def _camada_bloco(titulo, papel, icone, itens):
    """Um cartao por sistema da camada.

    As respostas passam por `_resposta()`, que e quem garante o contrato: a FONTE junto
    de cada numero, `sem_dados` virando o motivo em vez de sumir, lista virando ranking
    e medidor so onde ha faixa declarada. Reimplementar isso aqui seria reabrir todas
    essas decisoes de novo, e errar pelo menos uma.
    """
    cartoes = []
    for c in sorted(itens, key=lambda x: str(x.get("nome") or "")):
        achados = c.get("achados") or []
        respostas = "".join(_resposta(r) for r in (c.get("respostas") or []))
        analise = f'<p class="an">{_rich(c["analise"])}</p>' if c.get("analise") else ""
        if not respostas:
            respostas = ('<p class="nao">sem medida nesta rodada — nenhuma fonte declarada '
                         'para este papel</p>')
        marca = (f'<span class="qt">{_plural(len(achados), "achado", "achados")}</span>'
                 if achados else "")
        cartoes.append(f'<div class="sis{" crit" if achados else ""}">'
                       f'<p class="nm2">{_e(c.get("nome"))}{marca}</p>'
                       f'{analise}{respostas}</div>')
    return (f'<div class="camada"><p class="sub2">{_ic(icone)}{_e(titulo)} '
            f'<em>{_plural(len(itens), "sistema", "sistemas")}</em></p>'
            f'<div class="sisgrid">{"".join(cartoes)}</div></div>')


def _rede_e_segredos(fatos):
    """Redes, secrets e configs: INVENTARIO, nao medida.

    O relatorio mostra o NOME de cada secret e a CHAVE de cada config — nunca o valor,
    nunca string de conexao. E o nome que responde "existe um segredo para isto?" sem
    que o relatorio passe a ser, ele proprio, um vazamento.
    """
    fatos = fatos or {}
    partes = []
    redes = fatos.get("networks") or []
    if redes:
        linhas = "".join(
            f'<div class="l"><span>{_e(r.get("name"))}</span>'
            f'<b>{_e(r.get("driver"))} · {_e(r.get("scope"))}</b></div>'
            for r in sorted(redes, key=lambda x: str(x.get("name") or "")))
        partes.append(f'<div class="item"><p class="ch2">{_ic("rede")}'
                      f'<b>{_plural(len(redes), "rede", "redes")}</b></p>{linhas}</div>')

    nomes = ([str(x.get("name")) for x in (fatos.get("secrets") or [])]
             + [str(x.get("name")) for x in (fatos.get("configs") or [])])
    if nomes:
        etiquetas = "".join(f'<span class="tag">{_e(n)}</span>' for n in sorted(nomes))
        partes.append(f'<div class="item"><p class="ch2">{_ic("secret")}'
                      f'<b>{_plural(len(nomes), "secret ou config", "secrets e configs")}</b>'
                      f'<em>só o nome — o valor nunca é coletado</em></p>'
                      f'<div class="tags">{etiquetas}</div></div>')
    return f'<div class="duas">{"".join(partes)}</div>' if partes else ""


def _aplicacoes_stack(fatos, comp_an=None):
    """Uma aplicacao por stack, com as ROTAS que o proxy entrega nela.

    "Como o proxy esta roteando para o app X" e a pergunta que o inventario promete, e
    ela nao se responde com uma lista de servicos em ordem alfabetica. Dentro do bloco o
    servico aparece com o nome curto (`loja_web` vira `web`): o prefixo e a stack, que ja
    esta no titulo.
    """
    grupos = (fatos or {}).get("stacks") or []
    if not grupos:
        return ""
    comp_an = comp_an or {}
    cartoes = []
    for g in sorted(grupos, key=lambda x: str(x.get("stack") or "")):
        servicos = []
        for sv in sorted(g.get("services") or [], key=lambda x: str(x.get("name") or "")):
            sinais = []
            if sv.get("has_healthcheck") is False:
                sinais.append("sem healthcheck")
            lim = sv.get("limits") or {}
            if not lim.get("nano_cpus") and not lim.get("mem_bytes"):
                sinais.append("sem limites")
            if sv.get("tasks_failed"):
                sinais.append(_plural(sv["tasks_failed"], "task falhou", "tasks falharam"))
            img = f'{sv.get("image")}:{sv.get("tag")}' if sv.get("tag") else str(sv.get("image"))
            servicos.append(
                f'<div class="l"><span><b>{_e(stacks.short_name(sv.get("name")))}</b> '
                f'<code>{_e(img)}</code></span>'
                f'<em class="{"mal" if sinais else "ok"}">{_e(" · ".join(sinais) or "ok")}</em></div>')

        selos = ""
        if g.get("findings_high"):
            selos += (f'<span class="tag mal">'
                      f'{_plural(g["findings_high"], "crítico", "críticos")}</span>')
        if g.get("findings_med"):
            selos += (f'<span class="tag">'
                      f'{_plural(g["findings_med"], "médio", "médios")}</span>')
        if g.get("spofs"):
            selos += f'<span class="tag">{_plural(len(g["spofs"]), "sem reserva", "sem reserva")}</span>'

        rotas = g.get("routes") or []
        linha_rotas = (f'<p class="rota">{_ic("rota")}{_e(" · ".join(rotas[:4]))}'
                       + (f' +{len(rotas) - 4}' if len(rotas) > 4 else "") + "</p>") if rotas else ""
        notas = [comp_an.get(sv.get("name")) for sv in (g.get("services") or [])
                 if comp_an.get(sv.get("name"))]
        nota = f'<p class="an">{_e(" ".join(notas))}</p>' if notas else ""
        cartoes.append(
            f'<div class="app{" crit" if g.get("findings_high") else ""}">'
            f'<div class="ah"><span class="box">{_ic("aplicacoes")}</span>'
            f'<div><b>{_e(g.get("stack"))}</b>{selos}</div></div>'
            f'{linha_rotas}{"".join(servicos)}{nota}</div>')
    return f'<div class="apps">{"".join(cartoes)}</div>'


_ICONE_REGRA = {"fila_sem_consumidor": "fila", "tls": "cert", "cert": "cert"}


def _icone_de(regra):
    regra = str(regra or "")
    for chave, icone in _ICONE_REGRA.items():
        if chave in regra:
            return icone
    return "achado"


def _agrupar_por_regra(achados):
    """Um bloco por REGRA, nao por ocorrencia. 114 cartoes identicos nao sao 114
    problemas: sao um problema com 114 ocorrencias, e e assim que se resolve."""
    grupos = {}
    for a in achados:
        grupos.setdefault(a.get("regra"), []).append(a)
    # ordem: a regra que mais ocorre primeiro; empate desempata pelo nome da regra
    return sorted(grupos.items(), key=lambda kv: (-len(kv[1]), str(kv[0])))


# `prontas: 3 · acumuladas: 11663` -> o numero que ordena a lista e desenha a barra.
# A ordem importa: `acumuladas` e o total, e e por ele que a fila travada sobe ao topo.
_GRANDEZAS = ("acumuladas", "mensagens", "prontas", "ocorrencias")


def _peso_do_detalhe(detalhe):
    """O numero que o detalhe carrega, quando carrega um. Sem numero, devolve None —
    inventar zero faria a barra afirmar uma medida que ninguem fez."""
    texto = str(detalhe or "")
    for chave in _GRANDEZAS:
        m = re.search(rf"{chave}\s*[:=]\s*(\d+)", texto)
        if m:
            return int(m.group(1))
    return None


def _ocorrencias(itens, limite=10):
    """As ocorrencias, com teto. O relatorio mostra as primeiras e DIZ quantas ficaram
    de fora — a lista completa continua no report.json.

    Havendo numero no detalhe, a lista e ordenada por ele e ganha barra: e o que faz a
    fila com 11.663 mensagens aparecer antes da que tem 1. Sem numero, o detalhe vira
    legenda embaixo do nome, e nao um texto espremido numa coluna de 66px.
    """
    if not itens:
        return ""
    pesados = [(_peso_do_detalhe(a.get("detalhe")), a) for a in itens]
    tem_peso = any(p is not None for p, _ in pesados)
    if tem_peso:
        pesados.sort(key=lambda x: (-(x[0] or 0), str(x[1].get("objeto") or "")))
    teto = max((p or 0 for p, _ in pesados), default=0) or 1

    linhas = []
    for ordem, (peso, a) in enumerate(pesados[:limite], 1):
        alvo = a.get("objeto") or a.get("componente") or "—"
        if peso is None:
            barra, valor = '<span class="tr"></span>', ""
        else:
            barra = f'<span class="tr"><i style="width:{100 * peso / teto:.1f}%"></i></span>'
            valor = _human(peso)
        extra = ("" if tem_peso else
                 f'<p class="un">{_e(a.get("detalhe") or "")}</p>')
        linhas.append(f'<div class="rk{" topo" if ordem == 1 and peso else ""}">'
                      f'<span class="o n">{ordem}</span>'
                      f'<span class="nm">{_e(alvo)}</span>{barra}'
                      f'<span class="vl n">{_e(valor)}</span></div>{extra}')
    resto = len(itens) - limite
    rodape = (f'<p class="un">e mais {resto} — a lista completa está no '
              f'<code>report.json</code></p>') if resto > 0 else ""
    return f'<div class="rks">{"".join(linhas)}</div>{rodape}'


def _bloco_remediacao(cr, completo=True):
    """Os quatro blocos do catalogo, na ordem em que a duvida aparece: por que importa,
    como resolver, como confirmar e quando NAO fazer.

    O catalogo e versionado e revisado em pull request — nada aqui e escrito na hora.
    """
    if not cr:
        return ('<p class="nota">Esta regra ainda não tem ficha de remediação em '
                '<code>references/remediacao/</code>.</p>')
    partes = []
    if cr.get("como_resolver"):
        partes.append(f'<div class="fix"><p class="fh">{_ic("corrigir")}'
                      f'<b>Como resolver</b></p>{_rich(cr["como_resolver"])}</div>')
    if cr.get("como_confirmar"):
        partes.append(f'<div class="chk ok"><p class="ch2">{_ic("bom")}'
                      f'<b>Como confirmar que resolveu</b></p>{_rich(cr["como_confirmar"])}</div>')
    if cr.get("quando_nao_fazer"):
        partes.append(f'<div class="quando"><p class="ch2">{_ic("historico")}'
                      f'<b>Quando NÃO fazer</b></p>{_rich(cr["quando_nao_fazer"])}</div>')
    return "".join(partes)


def _achado_bloco(regra, itens, completo):
    """Um achado. `completo` traz o runbook inteiro; sem ele fica o cabecalho e as
    ocorrencias — e o que separa 'Agir agora' de 'Programar' na pagina."""
    cr = next((a.get("como_resolver") for a in itens if a.get("como_resolver")), None)
    titulo = (cr or {}).get("titulo") or regra
    classe = "" if completo else " med"
    cabeca = (f'<div class="cab"><span class="sel">{_ic(_icone_de(regra))}</span>'
              f'<div><h3>{_e(titulo)}</h3><p class="regra">{_e(regra)}</p></div>'
              f'<p class="qt n">{len(itens)}'
              f'<em>{"ocorrência" if len(itens) == 1 else "ocorrências"}</em></p></div>')
    corpo = [cabeca]
    if completo and cr and cr.get("por_que_importa"):
        corpo.append(f'<div class="pq">{_rich(cr["por_que_importa"])}</div>')
    corpo.append(_ocorrencias(itens))
    corpo.append(_bloco_remediacao(cr, completo=completo))
    return f'<article class="achado{classe}">{"".join(corpo)}</article>'


def _indice(triagem, presentes=()):
    from lib.triagem import FAIXAS
    """As tres faixas anunciadas antes de comecarem, com o tamanho de cada uma. Quem
    recebe decide onde gastar a atencao antes de rolar 30 paginas."""
    descricao = {
        "agir": "o que custa dinheiro ou disponibilidade enquanto você lê",
        "programar": "tem conserto conhecido e cabe numa janela planejada",
        "registrar": "o retrato do que existe, para comparar na próxima rodada",
    }
    itens = []
    for n, (fid, _, _) in enumerate(FAIXAS, 1):
        faixa = triagem["faixas"][fid]
        quantos = len(faixa["achados"])
        # faixa vazia nao vira link: no PDF, ancora morta e um clique que nao leva a
        # lugar nenhum, e o indice passa a prometer uma secao que nao existe
        rotulo = (f'<a class="t" href="#faixa-{n}">{_e(faixa["rotulo"])}</a>'
                  if n in presentes else f'<span class="t">{_e(faixa["rotulo"])}</span>')
        itens.append(f'<li class="f{n}"><i></i>{rotulo}'
                     f'<span class="d">{_e(descricao[fid])}</span>'
                     f'<span class="v n">{_plural(quantos, "achado", "achados")}</span></li>')
    return f'<ol class="porfaixa">{"".join(itens)}</ol>'


def _faixa(n, rotulo, resumo, quando, corpo):
    """A banda que abre cada faixa de acao. Sem corpo ela nao existe: banda vazia
    anunciando nada e pior que ausencia."""
    if not corpo:
        return ""
    return (f'<div class="faixa f{n}" id="faixa-{n}"><div class="fxh"><h2>{_e(rotulo)}</h2>'
            f'<span class="q">{_e(resumo)}</span>'
            f'<span class="quando">{_e(quando)}</span></div>{corpo}</div>')


def _pontos(fortes, fracos):
    """Positivo e negativo lado a lado. Relatorio que so lista problema ensina quem
    recebe a parar de ler — e o que esta sustentando a infra tambem e informacao."""
    def coluna(titulo, itens, classe, icone):
        if not itens:
            return ""
        li = "".join(f'<li>{_e(i)}</li>' for i in itens if i)
        return (f'<div class="{classe}"><p class="ch2">{_ic(icone)}<b>{_e(titulo)}</b></p>'
                f'<ul class="dl">{li}</ul></div>')
    a = coluna("Sustenta bem", fortes, "bom", "bom")
    b = coluna("Merece atenção", fracos, "neg", "ruim")
    return f'<div class="duas">{a}{b}</div>' if (a or b) else ""


def _fora(alvos):
    """Alvo declarado e NAO confirmado nesta rodada. Ele aparece — inventario que cala
    o que nao mediu mente por omissao — mas longe dos numeros, para nao ser lido como medida."""
    mudos = [a for a in alvos if not (a.get("fatos") or a.get("dimensoes"))]
    if not mudos:
        return ""
    # o estado de cada um sai em PALAVRA, e nao so o nome: "sem dados" e uma afirmacao
    # diferente de "operacional", e e justamente a que o relatorio nao pode engolir
    etiquetas = "".join(
        f'<span class="tag {ESTADO_EM_PALAVRA.get(a.get("saude"), ("", "na"))[1]}">'
        f'{_e(a.get("nome"))} · '
        f'{_e(ESTADO_EM_PALAVRA.get(a.get("saude"), (str(a.get("saude")), "na"))[0].lower())}'
        # o ONDE fica: alvo sem endereco no inventario e so um nome, e nao diz a quem
        # a proxima rodada precisa pedir confirmacao
        f'<em>{_e(a.get("onde"))}</em></span>'
        for a in sorted(mudos, key=lambda x: str(x.get("nome"))))
    return (f'<div class="fora"><p>{_ic("panorama")}<b>'
            f'{_plural(len(mudos), "outro alvo está declarado", "outros alvos estão declarados")}</b> '
            f'no <code>alvos.toml</code> e não foram confirmados nesta rodada, portanto não foram '
            f'tocados nem medidos.</p><div class="tags">{etiquetas}</div></div>')


def _aceites_novo(aceites):
    if not aceites:
        return ""
    itens = "".join(
        f'<div class="item"><div class="dt"><b>{_e(x.get("regra"))}</b>'
        f'<span class="p">revisar em {_e(x.get("revisar_em") or "—")}</span></div>'
        f'<p>{_e(x.get("motivo") or "sem motivo registrado")}</p></div>' for x in aceites)
    return itens


def _pendencias_novo(alvos):
    """O que esta calado e por que. Resolver e editar o alvos.toml — nenhum destes
    itens e um problema da infraestrutura."""
    linhas = []
    for a in alvos:
        for n in (a.get("nao_coletado") or []):
            linhas.append(f'<div class="item"><div class="dt"><b>{_e(n.get("o_que") or n.get("what"))}</b>'
                          f'</div><p>{_e(n.get("motivo") or n.get("reason"))}</p></div>')
    return "".join(linhas)


def _historico_novo(h):
    if not h:
        return ""
    novos, resolvidos = len(h.get("novos") or []), len(h.get("resolvidos") or [])
    vs = h.get("vs")
    return (f'<div class="duas">'
            f'<div class="neg"><p class="ch2">{_ic("achado")}<b>Apareceram</b></p>'
            f'<p class="qt n">{novos}<em>desde {_e(_quando(vs)) if vs else "a rodada anterior"}</em></p></div>'
            f'<div class="bom"><p class="ch2">{_ic("bom")}<b>Sumiram</b></p>'
            f'<p class="qt n">{resolvidos}<em>resolvidos</em></p></div></div>')


def _recomendacoes_novo(recs):
    """Com o comando pronto — e so para EXIBIR. Quem decide aplicar e o dono, depois
    de ler o 'quando nao fazer' da regra."""
    if not recs:
        return ""
    itens = []
    for ordem, r in enumerate(recs, 1):
        cmd = f'<pre>{_e(r.get("comando"))}</pre>' if r.get("comando") else ""
        etiquetas = "".join(f'<span class="tag">{_e(v)}</span>'
                            for v in (r.get("impacto"), r.get("alvo")) if v)
        tags = f'<div class="tags">{etiquetas}</div>' if etiquetas else ""
        # .rec e uma grade de TRES colunas: o numero, o miolo e o esforco a direita.
        # Com dois filhos o miolo caia na coluna de 40px e saia uma palavra por linha.
        itens.append(f'<div class="rec{" top" if ordem == 1 else ""}">'
                     f'<span class="o n">{ordem}</span>'
                     f'<div><h4>{_e(r.get("titulo"))}</h4>'
                     f'<p>{_e(r.get("porque"))}</p>{tags}{cmd}</div>'
                     f'<span class="quando">{_e(r.get("esforco") or "—")}</span></div>')
    return "".join(itens)


def render_html_v3(r):
    """Monta o relatorio por acao. Uma passada de substituicao, sempre: substituir em
    laco reprocessaria o texto ja inserido, e um `%%AGIR%%` escrito pelo agente no
    resumo injetaria uma secao inteira no relatorio."""
    from lib.nota import nota_de_estabilidade
    from lib.triagem import triar, cascata

    ctx = montar_contexto(r)
    alvos = ctx["alvos"]
    principal = _alvo_principal(alvos)
    achados = (principal or {}).get("achados") or ctx["achados"]
    t = triar(achados)
    nota = nota_de_estabilidade((principal or {}).get("dimensoes") or {})

    quantos = len(ctx["inventario"])
    titulo = f'Auditoria de infraestrutura — {_plural(quantos, "alvo", "alvos")}'

    # ---------------------------------------------------------------- topo
    cluster = (
        _sec("cluster", "Cluster", _e(f'{len((principal or {}).get("fatos", {}).get("nodes") or [])} nós · '
                                      f'{t["total"]} achados nesta rodada'),
             _kpis_novo(principal, t) + _dimensoes_novo(principal) + _cascata(cascata(t)))
        + _sec("metrica", "Instrumentos", "mostrador só onde a pergunta declara faixa",
               _instrumentos(alvos))
        + _sec("falhar", "Se isto falhar", "consequência a partir do que existe hoje",
               _impacto(((principal or {}).get("fatos") or {}).get("impact_points")))
        + _sec("no", "Nós e capacidade", "o que cada nó carrega",
               _nos_novo(((principal or {}).get("fatos") or {}).get("nodes"))
               + _node_failures(((principal or {}).get("fatos") or {}).get("nodes") or [])
               + _disk(((principal or {}).get("fatos") or {}).get("disk"))
               + _tls(((principal or {}).get("fatos") or {}).get("tls")))
    )

    # ------------------------------------------------------------- faixa 1
    agir = t["faixas"]["agir"]["achados"]
    corpo_agir = "".join(_achado_bloco(regra, itens, completo=True)
                         for regra, itens in _agrupar_por_regra(agir))
    if corpo_agir:
        corpo_agir = ('<p class="sub2">O achado e o runbook completo</p>' + corpo_agir
                      + ('<p class="sub2">Recomendações</p>'
                         + _recomendacoes_novo(ctx["recomendacoes"])
                         if ctx["recomendacoes"] else ""))
    faixa1 = _faixa(1, "Agir agora",
                    f'{len(_agrupar_por_regra(agir))} regra(s) · {_plural(len(agir), "ocorrência", "ocorrências")}',
                    "o prejuízo cresce enquanto você lê", corpo_agir)

    # ------------------------------------------------------------- faixa 2
    prog = t["faixas"]["programar"]["achados"]
    corpo_prog = "".join(_achado_bloco(regra, itens, completo=False)
                         for regra, itens in _agrupar_por_regra(prog))
    faixa2 = _faixa(2, "Programar",
                    f'{len(_agrupar_por_regra(prog))} regra(s) · {_plural(len(prog), "achado", "achados")}',
                    "tem conserto conhecido e cabe numa janela", corpo_prog)

    # ------------------------------------------------------------- faixa 3
    reg = t["faixas"]["registrar"]["achados"]
    pend, aceites = _pendencias_novo(alvos), _aceites_novo(ctx["aceites"])
    corpo_reg = (
        _sec("bom", "Pontos positivos e negativos", "cada um com a evidência que o sustenta",
             _pontos(ctx["fortes"], ctx["fracos"]))
        + _sec("aplicacoes", "Por aplicação", "as rotas que o proxy entrega em cada stack",
               _aplicacoes_stack((principal or {}).get("fatos"),
                                 (principal or {}).get("components_analysis")))
        + _sec("rede", "Redes, secrets e configs", "inventário — só o nome, nunca o valor",
               _rede_e_segredos((principal or {}).get("fatos")))
        + _sec("aplicacoes", "Topologia — sistemas por camada",
               "recebe · processa · enfileira · guarda · observa",
               _camadas((principal or {}).get("componentes")))
        + _sec("cobertura", "Cobertura das práticas",
               _plural(len(reg), "achado sem prazo", "achados sem prazo"),
               "".join(_achado_bloco(regra, itens, completo=False)
                       for regra, itens in _agrupar_por_regra(reg)))
        + _sec("aceito", "Riscos aceitos", "decididos pelo dono, com data de revisão", aceites)
        + _sec("metrica", "O que falta declarar",
               "silêncio com causa: resolver é editar o alvos.toml", pend)
        + _sec("historico", "Desde a auditoria anterior",
               "o que mudou entre as duas fotografias", _historico_novo(ctx["historico"]))
    )
    faixa3 = _faixa(3, "Registrar e seguir",
                    _plural(len(reg), "achado", "achados"),
                    "o retrato, para comparar na próxima rodada", corpo_reg)

    resumo = (f'<p>{_rich(ctx["resumo"])}</p>' if ctx["resumo"]
              else f'<p>{_e(nota["porque"].capitalize())}.</p>')

    repl = {
        "%%TITLE%%": _e(titulo),
        "%%FONTES%%": _fontes(),
        "%%NOTA_TITULO%%": _e(nota["titulo"]),
        "%%NOTA_TEXTO%%": resumo,
        "%%CARTAO_ESTADO%%": _cartao_estado(principal),
        "%%CLUSTER%%": cluster,
        "%%FORA%%": _fora(alvos),
        "%%INDICE%%": _indice(t, presentes={n for n, faixa in
                                            ((1, faixa1), (2, faixa2), (3, faixa3)) if faixa}),
        "%%AGIR%%": faixa1,
        "%%PROGRAMAR%%": faixa2,
        "%%REGISTRAR%%": faixa3,
    }
    with open(TEMPLATE_V3, encoding="utf-8") as f:
        pagina = f.read()
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
    elif res.get("pdf_motivo"):
        print(f"PDF não gerado: {res['pdf_motivo']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
from collections import Counter

from lib import metrics, stacks
from lib.coletores.docker import USO_POR_NO
from lib.nota import nota_geral
from lib.dados_blocos import nao_coletado_vigente
from lib.html_comum import _e
from lib.redact import scrub_text
from lib.regras import esperada
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


MAXIMO_DE_FRASES_NO_RESUMO = 2
MAXIMO_DE_CARACTERES_NO_RESUMO = 280
_ABREVIACAO = re.compile(r"\b(?:p\.\s?ex|ex|etc|aprox|vs|sr|sra|dr|dra)\.", re.I)
_ITEM_OU_PARAGRAFO = re.compile(r"\n\s*(?:[-*]|\d+[.)])\s+|\n\s*\n")


def _conta_frases(texto):
    """Quebra de linha simples não encerra frase, porque o agente quebra onde quiser; item de
    lista e parágrafo encerram, e `3.650`, `1.2.3` e `4,5 %` não têm espaço depois do ponto."""
    plano = _ABREVIACAO.sub("", _ITEM_OU_PARAGRAFO.sub(". ", "\n" + texto.strip()))
    return sum(1 for frase in re.split(r"[.!?…]+[\"')\]]*\s+", plano) if any(c.isalnum() for c in frase))


def _recusar_resumo_grande(resumo):
    """A capa só cabe em uma folha com o resumo curto. A mensagem não repete o texto do agente."""
    if not resumo:
        return
    texto = str(resumo).strip()
    frases, caracteres = _conta_frases(texto), len(texto)
    if frases > MAXIMO_DE_FRASES_NO_RESUMO or caracteres > MAXIMO_DE_CARACTERES_NO_RESUMO:
        raise ValueError(f"`resumo` com {frases} frases e {caracteres} caracteres; o limite é "
                         f"{MAXIMO_DE_FRASES_NO_RESUMO} frases e {MAXIMO_DE_CARACTERES_NO_RESUMO} "
                         f"caracteres. Reescreva o `resumo` no report.json e gere de novo; "
                         f"nenhum relatório foi gerado.")


_EMOJI_DE_ESTADO = re.compile("[ \t]*([🔴🟡🟢])\ufe0f?[ \t]*")


def _palavra_de_estado(casado):
    """Como marcador de frase, o emoji sai; no meio dela, ele é o dado e vira a palavra."""
    texto = casado.string
    antes, depois = texto[:casado.start()].rstrip(), texto[casado.end():]
    palavra = ESTADO_EM_PALAVRA[casado.group(1)][0].lower()
    separador = " " if antes else ""
    if not antes or antes[-1] in ".!?:\n" or depois.lower().startswith(palavra):
        return separador
    return f"{separador}{palavra}{' ' if depois[:1].isalnum() else ''}"


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
    _recusar_resumo_grande(report.get("resumo"))
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

NOTA_DO_PAPEL = (
    "O papel de cada componente vem da série que ele publica, quando alguma fonte o reconhece; "
    "senão, do nome da imagem, e aí é palpite — a etiqueta ao lado do nome diz qual é o caso. "
    "A saúde e o impacto do alvo <b>classificam pela imagem</b> em qualquer caso: eles não "
    "acompanham a correção do papel nesta versão.")


ORDEM_SEVERIDADE = ("critical", "high", "medium", "low", "info")
ROTULO_SEVERIDADE = {"critical": "Crítico", "high": "Alto", "medium": "Médio",
                     "low": "Baixo", "info": "Informativo"}


def _origem_do_papel(componente):
    """De onde veio o papel, ao lado do nome do componente.

    Toda medida carrega a fonte que respondeu; o papel carrega a dele pelo mesmo motivo. E
    quando a evidência CONTRADIZ a imagem, dizer isso é informação acionável: é a imagem
    mentindo, à vista de quem lê.
    """
    origem = componente.get("papel_origem") or "padrão"
    if origem == "declarado":
        nota = "papel declarado no alvos.toml"
    elif origem.startswith("exporter "):
        nota = f"papel confirmado pelo {_e(origem)}"
        da_imagem = componente.get("papel_da_imagem")
        if da_imagem and da_imagem != componente.get("papel"):
            nota += f"; a imagem sugeria {_e(da_imagem)}"
    elif origem == "imagem":
        nota = "papel sugerido pela imagem, não confirmado"
    else:
        nota = "sem evidência: nenhuma fonte reconheceu este componente"
    return f'<span class="pr-o">{nota}</span>'


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
    for ordem, item in enumerate(itens, 1):
        largura = 100 * (item.get("valor") or 0) / maior
        # A ORDEM das classes aqui não é estilo: `.rk` é uma grade de quatro colunas
        # (ordinal · nome · trilho · valor), e cada filho cai na coluna da sua posição.
        # Com o vocabulário antigo (`lb/vl/bar`) o nome caía na coluna de 20px do ordinal e
        # transbordava POR CIMA do número: o relatório imprimia `notas4` e `emai0s`.
        linhas.append(f'<div class="rk{" topo" if ordem == 1 else ""}">'
                      f'<span class="o">{ordem:02d}</span>'
                      f'<span class="nm">{_e(item.get("chave"))}</span>'
                      f'<span class="tr"><i style="width:{largura:.0f}%"></i></span>'
                      f'<span class="vl">{_numero(item.get("valor"))}</span></div>')
    return f'<div class="rks">{"".join(linhas)}</div>{_rodape_do_corte(total)}'


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


# Quatro papéis compartilhavam o rótulo "guarda", e o relatório saía com seções repetidas:
# `04 Guarda 1 sistema` e `05 Guarda 1 sistema`, uma para o banco e outra para o cache. Era
# invisível enquanto um fork de cache caía em `app` por não ser reconhecido pelo nome — só
# apareceu quando o papel passou a ser provado pela série.
CAMADAS = (("entrada", "recebe o tráfego"), ("app", "processa"),
           ("fila", "enfileira"), ("banco", "guarda em disco"),
           ("cache", "guarda em memória"), ("busca", "indexa para busca"),
           ("storage", "guarda arquivo"), ("observabilidade", "observa"))


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
               '<span><i style="--c:var(--ok)"></i>sem achado aberto</span>'
               '<span><i style="--c:var(--warn)"></i>1 achado</span>'
               '<span><i style="--c:var(--crit)"></i>2 ou mais</span>'
               '</div>'
               f'<p class="nota-legenda">{NOTA_DO_PAPEL}</p>'
               '<p class="nota-legenda">As camadas agrupam por <b>papel</b> — quem recebe o '
               'tráfego, quem processa, quem guarda. <b>Não é dependência medida</b>: a skill '
               'observa o papel de cada componente, não quem chama quem.</p>')
    return f'<div class="mapa">{"".join(camadas)}{legenda}</div>'


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


def _divergencias(alvo):
    """A dimensao traz contadores que o coletor calculou; a lista de achados traz as
    ocorrencias. Quando os dois discordam, o relatorio imprime os DOIS numeros em telas
    diferentes e quem le nao sabe em qual acreditar.

    "Numero sem fonte nao existe" e a regra da skill. Dois numeros que se contradizem sao
    pior que um numero sozinho: calar a contradicao e escolher uma das versoes sem dizer.
    """
    seg = (alvo.get("dimensoes") or {}).get("seguranca") or {}
    if not seg:
        return ""
    # A dimensão `seguranca` é calculada em `metrics.py` filtrando `rule_id` que começa com
    # `SEC_`: ela é sobre POSTURA DE SEGURANÇA, não sobre todos os achados. Comparar contra a
    # lista inteira acusava divergência onde não havia — numa rodada real, "107 declarados ·
    # 114 na lista", porque os 7 extras eram `OPS_TASK_FAILING`, que a dimensão nunca contou.
    # Alarme falso é pior que alarme nenhum: ensina a ignorar a caixa.
    achados = [x for x in (alvo.get("achados") or [])
               if str(x.get("regra") or "").startswith("SEC_")]
    real = {"high": 0, "medium": 0, "esperados": 0}
    for a in achados:
        if a.get("esperada"):
            real["esperados"] += 1
        elif a.get("severidade") in real:
            real[a["severidade"]] += 1

    linhas = []
    for chave, rotulo, visto in (("high", "achados altos", real["high"]),
                                 ("med", "achados médios", real["medium"]),
                                 ("expected", "esperados", real["esperados"])):
        declarado = seg.get(chave)
        if declarado is not None and declarado != visto:
            linhas.append(f'<div class="l"><span>{_e(rotulo)}</span>'
                          f'<b class="n mal">{declarado} declarados · {visto} na lista</b></div>')
    if not linhas:
        return ""
    return (f'<div class="semdados"><b>Os contadores da dimensão não batem com a lista de '
            f'achados desta rodada.</b> Os dois números saem do mesmo <code>report.json</code>; '
            f'enquanto divergirem, prefira a lista, que é a que traz objeto e detalhe.</div>'
            + "".join(linhas))


# ---------------------------------------------------------------- por camada
# A ordem das camadas ja existe em CAMADAS (linha ~1195) e e UMA so: duplica-la aqui
# criou um sombreamento silencioso que fazia _topologia estourar ao desempacotar.
# Aqui vai apenas o icone de cada papel.
_ICONE_CAMADA = {"entrada": "rota", "app": "aplicacoes", "fila": "fila", "banco": "banco",
                 "cache": "banco", "busca": "banco", "storage": "disco",
                 "observabilidade": "metrica"}


def _camadas(componentes):
    """Os sistemas sem bloco proprio, agrupados pelo PAPEL que cumprem.

    NAO e dependencia medida: a skill observa o papel de cada componente, nao quem chama
    quem. Dizer isso e obrigacao, nao rodape — a legenda sai junto.

    Papel que a skill nao reconhece nao some: cai em "Outros", nomeado.
    """
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
            '<p class="nota-legenda">As camadas agrupam por <b>papel</b> — quem recebe o tráfego, '
            'quem processa, quem guarda. <b>Não é dependência medida</b>: a skill observa '
            'o papel de cada componente, não quem chama quem.</p>')


def _respostas_do_cartao(respostas):
    """As respostas de um sistema, com o silencio agrupado pela CAUSA.

    Num cartao real, tres perguntas descartadas pela mesma razao imprimiam o mesmo
    paragrafo de vinte palavras tres vezes seguidas, dentro do mesmo cartao. O motivo
    descreve a FONTE, nao a pergunta: vale uma vez, com os titulos na frente.

    A medida vem primeiro e o silencio depois, de proposito: quem le o cartao quer o
    numero, e o que nao foi medido e nota de rodape — nunca omissao.
    """
    from lib.perguntas import PERGUNTAS

    medidas, mudas = [], {}
    for r in respostas or []:
        if r.get("sem_dados") or r.get("erro_interno"):
            titulo = (PERGUNTAS.get(r.get("pergunta"), {}).get("titulo")
                      or r.get("pergunta") or "—")
            mudas.setdefault(str(r.get("motivo") or "—"), []).append(str(titulo))
        else:
            medidas.append(_resposta(r))
    for motivo, titulos in mudas.items():
        medidas.append(f'<div class="semdados"><b>{_e(" · ".join(titulos))}</b> — '
                       f'{_e(motivo)}</div>')
    return "".join(medidas)


def _so_medidas_simples(componente):
    """O sistema cuja medicao inteira cabe numa linha: sem analise, sem achado, e toda
    resposta e um numero — nenhuma lista, nenhum silencio com motivo proprio."""
    respostas = componente.get("respostas") or []
    if not respostas or componente.get("analise") or componente.get("achados"):
        return False
    return all(not r.get("sem_dados") and not r.get("erro_interno")
               and not isinstance(r.get("valor"), list) for r in respostas)


def _tabela_de_sistemas(itens):
    """Os sistemas cuja medicao e so numero, numa TABELA e nao num cartao cada.

    Numa rodada real, 35 componentes respondiam exatamente `CPU em uso` e `memoria em
    uso` — dois numeros. Cada um ganhava um cartao de 366px: nove paginas para setenta
    numeros, e nenhuma forma de comparar o consumo entre eles, que e a unica pergunta
    que alguem faz olhando essa lista. Em coluna, o maior salta aos olhos.
    """
    from lib.perguntas import PERGUNTAS

    if not itens:
        return ""
    colunas, fontes = [], []
    for c in itens:
        for r in c.get("respostas") or []:
            if r.get("pergunta") not in colunas:
                colunas.append(r.get("pergunta"))
            if r.get("fonte") and r["fonte"] not in fontes:
                fontes.append(r["fonte"])
    cabecalho = ["sistema"]
    for p in colunas:
        pergunta = PERGUNTAS.get(p, {})
        unidade = pergunta.get("unidade")
        cabecalho.append(f'{pergunta.get("titulo") or p}'
                         + (f' ({unidade})' if unidade else ""))
    linhas = []
    for c in sorted(itens, key=lambda x: str(x.get("nome") or "")):
        por_pergunta = {r.get("pergunta"): r for r in (c.get("respostas") or [])}
        celulas = [f'<b>{_e(c.get("nome"))}</b>']
        for p in colunas:
            r = por_pergunta.get(p)
            celulas.append(_numero(r.get("valor")) if r else "—")
        linhas.append(celulas)
    tabela = _table(cabecalho, linhas, aligns=[""] + ["num"] * len(colunas))
    rodape = (f'<p class="corte">fonte: {_e(" · ".join(fontes))}</p>') if fontes else ""
    return tabela.replace("<table>", '<table class="tsis">', 1) + rodape


def _camada_bloco(titulo, papel, icone, itens):
    """Um cartao por sistema da camada.

    As respostas passam por `_resposta()`, que e quem garante o contrato: a FONTE junto
    de cada numero, `sem_dados` virando o motivo em vez de sumir, lista virando ranking
    e medidor so onde ha faixa declarada. Reimplementar isso aqui seria reabrir todas
    essas decisoes de novo, e errar pelo menos uma.
    """
    cartoes, calados, simples = [], 0, []
    for c in sorted(itens, key=lambda x: str(x.get("nome") or "")):
        achados = c.get("achados") or []
        if _so_medidas_simples(c):
            simples.append(c)
            continue
        respostas = _respostas_do_cartao(c.get("respostas"))
        # `_rich` ja devolve <p>; embrulhar em <p> gera paragrafo dentro de paragrafo,
        # que o navegador fecha sozinho e desmonta o bloco
        analise = f'<div class="an">{_rich(c["analise"])}</div>' if c.get("analise") else ""

        # Componente sem resposta, sem analise e sem achado NAO ganha cartao. Ele ganhava,
        # e o cartao repetia "sem medida nesta rodada" — numa auditoria de 57 componentes
        # isso imprimiu a mesma frase 54 vezes, NOVE paginas A4 de ruido. A informacao nao
        # some: ela e contada, uma vez, no rodape da camada e em "O que falta declarar".
        if not respostas and not analise and not achados:
            calados += 1
            continue
        if not respostas:
            respostas = '<p class="semdados">sem medida nesta rodada — nenhuma fonte declarada</p>'
        marca = (f'<span class="qt">{_plural(len(achados), "achado", "achados")}</span>'
                 if achados else "")
        cartoes.append(f'<div class="sis{" crit" if achados else ""}">'
                       f'<p class="nm2">{_e(c.get("nome"))}{_origem_do_papel(c)}{marca}</p>'
                       f'{analise}{respostas}</div>')

    rodape = (f'<p class="corte">Outros {calados} nesta camada não receberam pergunta nesta '
              f'rodada — o motivo de cada um está em '
              f'<a href="#o-que-falta-declarar">O que falta declarar</a>.</p>') if calados else ""
    tabela = _tabela_de_sistemas(simples)
    if not cartoes and not tabela:
        return (f'<div class="camada"><p class="sub2">{_ic(icone)}{_e(titulo)} '
                f'<em>0 de {len(itens)}</em></p>{rodape}</div>')
    # o cabecalho conta o que a camada DESENHA — cartao e linha de tabela —; o resto vai
    # no rodape, dito por extenso. Dizer "3 sistemas" e mostrar 1 cartao e o leitor
    # procurando dois que nao existem.
    desenhados = len(cartoes) + len(simples)
    quantos = (f'{desenhados} de {len(itens)}' if calados
               else _plural(desenhados, "sistema", "sistemas"))
    grade = f'<div class="sisgrid">{"".join(cartoes)}</div>' if cartoes else ""
    return (f'<div class="camada"><p class="sub2">{_ic(icone)}{_e(titulo)} '
            f'<em>{quantos}</em></p>{grade}{tabela}{rodape}</div>')


def _peso_da_gravidade(itens):
    return min(ORDEM_SEVERIDADE.index(a.get("severidade")) if a.get("severidade") in ORDEM_SEVERIDADE
               else len(ORDEM_SEVERIDADE) for a in itens)


def _agrupar_por_regra(achados):
    """Um bloco por REGRA, nao por ocorrencia. 114 cartoes identicos nao sao 114
    problemas: sao um problema com 114 ocorrencias, e e assim que se resolve."""
    grupos = {}
    for a in achados:
        grupos.setdefault(a.get("regra"), []).append(a)
    # ordem: a pior gravidade da regra; empate vai para a que mais ocorre e depois para o nome
    return sorted(grupos.items(), key=lambda kv: (_peso_da_gravidade(kv[1]), -len(kv[1]), str(kv[0])))


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


def _detalhe_comum(itens):
    """O detalhe quando ele e o MESMO em todas as ocorrencias — e entao ele descreve a
    REGRA, nao a ocorrencia, e pertence ao cabecalho do bloco.

    Medido numa rodada real de 61 servicos: em 6 das 9 regras o texto era identico em
    todas as ocorrencias (`container roda como root (user root/uid 0 ou USER ausente)`
    nas 61, `sem HEALTHCHECK definido` nas 49, `sem limite de CPU/memoria definido` nas
    34) — 144 dos 189 achados. A mesma frase dez vezes nao informa dez vezes: ocupa dez
    linhas e ensina quem le a pular o bloco inteiro, inclusive a linha que mudaria.
    """
    textos = {str(a.get("detalhe") or "").strip() for a in itens}
    return textos.pop() if len(textos) == 1 else None


# teto da lista compacta. Alto de proposito: sem barra e sem legenda cada nome ocupa
# uma celula, e 61 deles cabem em 21 linhas de tres colunas — cortar em 10 mandaria
# para o `report.json` uma lista que a pagina comporta inteira.
TETO_DE_NOMES = 60


def _lista_de_nomes(nomes, limite=TETO_DE_NOMES):
    """So os nomes, em colunas. A pagina e A4 PAISAGEM e a lista de uma coluna deixava
    dois tercos da largura em branco."""
    mostra = list(nomes)[:limite]
    etiquetas = "".join(f'<span class="nome">{_e(n)}</span>' for n in mostra)
    resto = len(nomes) - len(mostra)
    rodape = (f'<p class="un">e mais {resto} — a lista completa está no '
              f'<code>report.json</code></p>') if resto > 0 else ""
    return f'<div class="nomes">{etiquetas}</div>{rodape}'


def _ocorrencias(itens, limite=None, detalhe_na_regra=False):
    """As ocorrencias, com teto. O relatorio mostra as primeiras e DIZ quantas ficaram
    de fora — a lista completa continua no report.json.

    Havendo numero no detalhe, a lista e ordenada por ele e ganha barra: e o que faz a
    fila com 11.663 mensagens aparecer antes da que tem 1. Sem numero, o detalhe vira
    legenda embaixo do nome, e nao um texto espremido numa coluna de 66px.

    Com `detalhe_na_regra` a frase ja foi escrita UMA vez no cabecalho (ver
    `_detalhe_comum`): aqui sobra o nome, e a grade de ranking passaria a desenhar uma
    barra vazia por item — uma barra que nao mede nada. Vira lista em colunas.
    """
    if not itens:
        return ""
    pesados = [(_peso_do_detalhe(a.get("detalhe")), a) for a in itens]
    tem_peso = any(p is not None for p, _ in pesados)
    if detalhe_na_regra and not tem_peso:
        return _lista_de_nomes([str(a.get("objeto") or a.get("componente") or "—")
                                for a in itens], limite or TETO_DE_NOMES)
    limite = limite or LIMITE_NO_RELATORIO
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
        extra = ("" if tem_peso or detalhe_na_regra else
                 f'<p class="un">{_e(a.get("detalhe") or "")}</p>')
        linhas.append(f'<div class="rk{" topo" if ordem == 1 and peso else ""}">'
                      f'<span class="o n">{ordem}</span>'
                      f'<span class="nm">{_e(alvo)}</span>{barra}'
                      f'<span class="vl n">{_e(valor)}</span></div>{extra}')
    resto = len(itens) - limite
    rodape = (f'<p class="un">e mais {resto} — a lista completa está no '
              f'<code>report.json</code></p>') if resto > 0 else ""
    return f'<div class="rks">{"".join(linhas)}</div>{rodape}'


def _bloco_remediacao(cr):
    """Os blocos do catalogo, na ordem em que a duvida aparece: o que fazer, como conferir e
    quando NAO fazer. O catalogo e versionado e revisado em pull request — nada aqui e
    escrito na hora.
    """
    if not cr:
        return ('<p class="bl-mini">Esta regra ainda não tem ficha de remediação em '
                '<code>references/remediacao/</code>.</p>')
    partes = []
    for chave, rotulo in (("como_resolver", "O que fazer"), ("como_confirmar", "Como conferir"),
                          ("quando_nao_fazer", "Quando não fazer")):
        if cr.get(chave):
            partes.append(f'<h4>{rotulo}</h4>{_rich(cr[chave])}')
    return "".join(partes)


TOM_DA_SEVERIDADE = {"critical": "crit", "high": "crit", "medium": "warn"}


def _comando(r):
    """A capa só traz as 5 primeiras: fora dela, este bloco é o único lugar do `porque`."""
    porque = f'<p>{_e(r.get("porque"))}</p>' if r.get("porque") else ""
    comando = f'<pre>{_e(r.get("comando"))}</pre>' if r.get("comando") else ""
    esforco = f'<p class="bl-mini">esforço {_e(r.get("esforco"))}</p>' if r.get("esforco") else ""
    return f'<h4>{_e(r.get("titulo"))}</h4>{porque}{comando}{esforco}'


def _comandos(recomendacoes):
    return "".join(_comando(r) for r in recomendacoes)


def _achado_bloco(regra, itens, completo, limite=None, recomendacoes=()):
    """Um problema, na ordem do mockup: a esquerda o que significa e o que fazer, a direita
    quem foi afetado. `completo` traz a explicacao de por que importa."""
    cr = next((a.get("como_resolver") for a in itens if a.get("como_resolver")), None)
    titulo = (cr or {}).get("titulo") or rule_meta(regra).get("label", regra)
    pior = min((a.get("severidade") for a in itens),
               key=lambda sv: ORDEM_SEVERIDADE.index(sv) if sv in ORDEM_SEVERIDADE else 9)
    nivel = (f'<span class="bl-nivel bl-nivel-{TOM_DA_SEVERIDADE.get(pior, "ok")}">'
             f'{_e(ROTULO_SEVERIDADE.get(pior, pior))}</span>')
    # a frase que vale para TODAS as ocorrencias e escrita aqui, uma vez, antes da lista
    comum = _detalhe_comum(itens)
    frase = f'<p class="detalhe-da-regra">{_e(comum)}</p>' if comum else ""
    significa = (f'<h4>O que significa</h4>{_rich(cr["por_que_importa"])}'
                 if completo and cr and cr.get("por_que_importa") else "")
    esquerda = frase + significa + _bloco_remediacao(cr) + _comandos(recomendacoes)
    direita = (f'<h4>Afetados: {_plural(len(itens), "ocorrência", "ocorrências")}</h4>'
               + _ocorrencias(itens, limite, detalhe_na_regra=bool(comum))
               + f'<h4>Fonte da regra</h4><p class="bl-mini regra">{_e(regra)}</p>')
    return (f'<article class="bl-prob">{nivel}<h3>{_e(titulo)}</h3>'
            f'<div class="bl-pgrid"><div>{esquerda}</div><div>{direita}</div></div></article>')


def _aceites_novo(aceites):
    if not aceites:
        return ""
    linhas = []
    for x in aceites:
        # "Vencido volta a contar, com a observacao de que a justificativa expirou"
        # (SKILL.md). Sem a marca, um aceite de 2025 passa por decisao vigente.
        vencido = bool(x.get("vencido"))
        selo = ('<span class="tag mal">aceite vencido</span>' if vencido
                else f'<span class="p">revisar em {_e(x.get("revisar_em") or "—")}</span>')
        quando = (f'<p class="corte">A justificativa expirou em '
                  f'{_e(x.get("revisar_em") or "—")} — este achado voltou a contar.</p>'
                  if vencido else "")
        linhas.append(f'<div class="item{" crit" if vencido else ""}">'
                      f'<div class="dt"><b>{_e(x.get("regra"))}</b>{selo}</div>'
                      f'<p>{_e(x.get("motivo") or "sem motivo registrado")}</p>{quando}</div>')
    return "".join(linhas)


def _mudos_por_motivo(mudos):
    """As perguntas caladas agrupadas pelo MOTIVO, nao uma linha por pergunta.

    Numa rodada real eram 79 linhas carregando 3 motivos: a mesma frase de vinte
    palavras impressa 55, 18 e 6 vezes. O numero de componentes continua na frente de
    cada grupo, entao agrupar nao encolhe lacuna nenhuma — so para de reescrever a causa.
    """
    if not mudos:
        return ""
    grupos = {}
    for m in mudos:
        grupos.setdefault(str(m.get("motivo") or "—"), []).append(
            f'{m.get("componente")} · {m.get("pergunta")}')
    blocos = []
    for motivo, itens in sorted(grupos.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        etiquetas = "".join(f'<span class="nome">{_e(i)}</span>' for i in sorted(itens))
        blocos.append(f'<div class="motivo">'
                      f'<p class="mt"><b class="n">{len(itens)}</b> '
                      f'{"pergunta" if len(itens) == 1 else "perguntas"} · um motivo só'
                      f'</p><p class="mtx">{_e(motivo)}</p>'
                      f'<div class="nomes">{etiquetas}</div></div>')
    return "".join(blocos)


def _pendencias_novo(alvos):
    """O que esta calado e por que. Resolver e editar o alvos.toml — nenhum destes
    itens e um problema da infraestrutura.

    Os componentes que nao receberam pergunta entram AQUI, nomeados. A camada deixou de
    desenhar um cartao para cada um (54 cartoes identicos eram nove paginas de ruido) e
    aponta para esta secao; se ela nao os listasse, o ponteiro seria uma promessa vazia e
    o relatorio ficaria mudo justamente sobre o proprio silencio.
    """
    linhas = []
    for a in alvos:
        if a.get("coletado") is False:
            continue
        for n in nao_coletado_vigente(a):
            # sem `o_que`, o titulo saia VAZIO: tres alvos nao confirmados viravam tres
            # linhas identicas dizendo "alvo nao confirmado nesta execucao" sem dizer
            # qual alvo. O nome do alvo e a resposta obvia, e ele sempre existe.
            o_que = n.get("o_que") or n.get("what") or a.get("nome") or "—"
            linhas.append(f'<div class="item"><div class="dt"><b>{_e(o_que)}</b>'
                          f'</div><p>{_e(n.get("motivo") or n.get("reason"))}</p></div>')
        # as perguntas que a skill SABE fazer e que ficaram sem resposta. Um 🟡 sem nada
        # que o explique inverte o problema que `agravar_saude` documenta: quem lê precisa
        # ver qual componente, qual pergunta e qual motivo.
        cobertura = a.get("cobertura") or {}
        if cobertura.get("mudos"):
            # `<identidade>` não é pergunta: contá-la em "N perguntas sem resposta" faz o
            # número não bater com `perguntadas - respondidas`, e põe uma não-pergunta sob a
            # frase "estas perguntas a skill sabe fazer".
            sem_papel = [m for m in cobertura["mudos"] if m.get("pergunta") == "<identidade>"]
            cobertura = dict(cobertura,
                             mudos=[m for m in cobertura["mudos"]
                                    if m.get("pergunta") != "<identidade>"])
            if sem_papel:
                nomes = ", ".join(_e(m["componente"]) for m in sem_papel)
                linhas.append(
                    f'<div class="item"><div class="dt">'
                    f'<b>{_plural(len(sem_papel), "componente sem papel provado", "componentes sem papel provado")}</b>'
                    f'<span class="p">identidade</span></div>'
                    f'<p>Nenhuma fonte reconheceu o que estes componentes são, então eles '
                    f'receberam as perguntas do palpite da imagem — ou nenhuma. '
                    f'<b>Papel errado faz a pergunta errada:</b> o relatório pode estar medindo '
                    f'a coisa certa no lugar errado.</p>'
                    f'<div class="l"><span>{nomes}</span></div></div>')
            linhas_mudas = _mudos_por_motivo(cobertura["mudos"])
            linhas.append(
                f'<div class="item crit"><div class="dt">'
                f'<b>{_plural(len(cobertura["mudos"]), "pergunta sem resposta", "perguntas sem resposta")}</b>'
                f'<span class="p">cobertura {_e(cobertura.get("pct"))}%</span></div>'
                f'<p>Estas perguntas a skill sabe fazer e não foram respondidas. '
                f'<b>Silêncio não é saúde</b>: enquanto elas não responderem, a auditoria não '
                f'pode assinar que está tudo convergido.</p>{linhas_mudas}</div>')

        # o bloco diz "sem dado"; o motivo de cada resposta vazia fica aqui, agrupado
        ja_ditos = {(m.get("componente"), m.get("pergunta")) for m in (a.get("cobertura") or {}).get("mudos") or []}
        vazias = [{"componente": c.get("nome"), "pergunta": r.get("pergunta"), "motivo": r.get("motivo")}
                  for c in a.get("componentes") or [] if c.get("papel") in PAPEIS_COM_BLOCO
                  for r in c.get("respostas") or [] if r.get("sem_dados") or r.get("erro_interno")
                  if (c.get("nome"), r.get("pergunta")) not in ja_ditos]
        if vazias:
            linhas.append(f'<div class="item"><div class="dt"><b>'
                          f'{_plural(len(vazias), "medida sem resposta", "medidas sem resposta")}</b>'
                          f'<span class="p">{_e(a.get("nome"))}</span></div>{_mudos_por_motivo(vazias)}</div>')

        # `analise` é prosa que o agente escreveu POR CIMA do fato — não é medida. Incluí-la
        # aqui fazia a lacuna encolher conforme o agente falava mais: 54 componentes sem
        # pergunta viravam "44" só porque alguém comentou dez deles.
        calados = sorted(c.get("nome") or "—" for c in (a.get("componentes") or [])
                         if not (c.get("respostas") or c.get("achados")))
        if calados:
            etiquetas = "".join(f'<span class="tag">{_e(n)}</span>' for n in calados)
            linhas.append(
                f'<div class="item"><div class="dt">'
                f'<b>{_plural(len(calados), "componente sem pergunta", "componentes sem pergunta")}</b>'
                f'<span class="p">{_e(a.get("nome"))}</span></div>'
                f'<p>Nenhuma fonte declarada para o papel deles, ou o papel ainda não tem '
                f'pergunta nesta versão. <b>Silêncio não é saúde</b>: não quer dizer que estes '
                f'componentes estejam bem, quer dizer que nada foi observado neles. Declare '
                f'<code>metricas_url</code> ou <code>admin_url</code> no <code>alvos.toml</code> '
                f'para o relatório medi-los.</p>'
                f'<div class="tags">{etiquetas}</div></div>')
    return "".join(linhas)


def _recomendacao_inteira(ordem, r):
    """Com o comando pronto — e so para EXIBIR. Quem decide aplicar e o dono, depois
    de ler o 'quando nao fazer' da regra."""
    cmd = f'<pre>{_e(r.get("comando"))}</pre>' if r.get("comando") else ""
    # `alto` numa etiqueta e `medio` na coluna da direita eram duas palavras soltas:
    # uma e IMPACTO, a outra e ESFORCO, e nada na pagina dizia qual era qual.
    etiquetas = "".join(f'<span class="tag">{rotulo} {_e(v)}</span>'
                        for rotulo, v in (("impacto", r.get("impacto")),
                                          ("alvo", r.get("alvo"))) if v)
    tags = f'<div class="tags">{etiquetas}</div>' if etiquetas else ""
    # .rec e uma grade de TRES colunas: o numero, o miolo e o esforco a direita.
    # Com dois filhos o miolo caia na coluna de 40px e saia uma palavra por linha.
    return (f'<div class="rec{" top" if ordem == 1 else ""}">'
            f'<span class="o n">{ordem}</span>'
            f'<div><h4>{_e(r.get("titulo"))}</h4>'
            f'<p>{_e(r.get("porque"))}</p>{tags}{cmd}</div>'
            f'<span class="quando">esforço'
            f'<em>{_e(r.get("esforco") or "—")}</em></span></div>')


def _so_o_comando(ordem, r):
    """Título e motivo já estão na capa: aqui fica o que ela não traz, ligado pelo número."""
    esforco = f' · esforço {_e(r.get("esforco"))}' if r.get("esforco") else ""
    return f'<div class="bl-cmd"><p class="bl-mini">Prioridade {ordem}{esforco}</p><pre>{_e(r.get("comando"))}</pre></div>'


PAPEIS_COM_BLOCO = {"entrada", "fila", "banco", "cache", "maquina", "app"}


def _parte(ident, titulo, sub, corpo):
    return (f'<section class="bl-parte" id="{_e(ident)}"><div class="bl-parte-t"><h2>{_e(titulo)}</h2>'
            f'<span class="bl-mini">{_e(sub)}</span></div>{corpo}</section>')


def _servicos_de(alvo):
    servicos = (alvo.get("fatos") or {}).get("services")
    return servicos if isinstance(servicos, list) else []


def _conta_sistemas(alvos):
    """A mesma stack em dois alvos são dois sistemas. Sem serviço, a saúde lista os endpoints."""
    sistemas = {(a.get("nome"), stacks.stack_of(s.get("name"))) for a in alvos for s in _servicos_de(a)}
    return len(sistemas) or sum(1 for a in _da_rodada(alvos) if a.get("tipo") == "http")


def _mudos_de(alvos):
    return [m for a in alvos for m in (a.get("cobertura") or {}).get("mudos") or []]


def _certificados_de(alvos):
    """`fatos.certificado` sem `dias` é o motivo de não ter lido: esse vai para as pendências."""
    certificados = []
    for a in alvos:
        certificado = (a.get("fatos") or {}).get("certificado") or {}
        if "dias" in certificado:
            certificados.append({"nome": a.get("nome"), "dias": certificado["dias"]})
    return certificados


CATEGORIA_DO_PAPEL = {"entrada": "proxy", "fila": "filas", "banco": "bancos", "cache": "cache", "busca": "busca",
                      "storage": "armazenamento", "observabilidade": "observabilidade", "maquina": "máquinas"}
MOTIVOS_CURTOS = (("senha_env", "falta a senha no ambiente"),
                  ("etiqueta", "a métrica não identifica o serviço"),
                  ("não expõem o dado", "não há exporter ligado"),
                  ("não declara", "não há fonte declarada"),
                  ("não respondeu", "a fonte não respondeu"),
                  ("orçamento", "o tempo de coleta acabou"))
MOTIVO_GENERICO = "a fonte não trouxe o dado"
# Prefixo do texto do coletor: `na()` só guarda o motivo, e a linha da capa não comporta a frase.
CATEGORIAS_DA_LACUNA = (("métricas", "métricas"), ("tendências", "tendências"),
                        ("tasks", "tarefas"), ("ligação de", "tarefas"),
                        (USO_POR_NO, "máquinas"), ("máquina", "máquinas"),
                        ("containers", "containers"), ("docker", "dados do Docker"),
                        ("o componente declarado", "componentes declarados"),
                        ("componente ignorado", "componentes declarados"))
LACUNA_GENERICA = "outros dados"


def _da_rodada(alvos):
    return [a for a in alvos if a.get("coletado") is not False]


def _filas_lidas(alvo, mudo):
    """Sem o ritmo, as filas continuam medidas: a capa não pode dizer que faltaram."""
    return any(r.get("pergunta") == "fila.filas" and r.get("valor") and not r.get("sem_dados")
               for c in alvo.get("componentes") or [] if c.get("nome") == mudo.get("componente")
               for r in c.get("respostas") or [])


def _medidas_que_faltaram(alvos):
    """`<identidade>` diz que o papel é palpite, não que faltou medida: esse vai para o Registro."""
    faltas = []
    for indice, a in enumerate(alvos):
        papeis = {c.get("nome"): c.get("papel") for c in a.get("componentes") or []}
        faltas += [((indice, m.get("componente")), papeis.get(m.get("componente")), m.get("motivo"))
                   for m in (a.get("cobertura") or {}).get("mudos") or []
                   if m.get("componente") and m.get("pergunta") != "<identidade>"
                   and not (m.get("pergunta") == "fila.taxa_entrada_saida" and _filas_lidas(a, m))]
    return faltas


def _e_fato(valor):
    """`{"status": "n/a"}` e `na()` dizem que o dado faltou: o alvo que só tem isso não trouxe nada."""
    if isinstance(valor, dict) and (valor.get("status") == "n/a" or ("valor" in valor and valor["valor"] is None)):
        return False
    return valor not in (None, "", [], {})


def _trouxe_fatos(alvo):
    return any(_e_fato(v) for v in (alvo.get("fatos") or {}).values())


def _categoria_da_lacuna(lacuna):
    texto = str(lacuna.get("o_que") or lacuna.get("what") or lacuna.get("motivo") or lacuna.get("reason"))
    return next((rotulo for prefixo, rotulo in CATEGORIAS_DA_LACUNA if texto.startswith(prefixo)), LACUNA_GENERICA)


def _faltou(alvos):
    """Categorias e não nomes: uma linha de capa não comporta a lista, que fica no Registro. O alvo
    só é citado quando não trouxe fatos: é a lacuna maior e não pode cair no corte."""
    rodada = _da_rodada(alvos)
    vazios = [a for a in rodada if not _trouxe_fatos(a)]
    sem_dados = sorted({a["nome"] for a in vazios if nao_coletado_vigente(a) and a.get("nome")})
    parciais = dict.fromkeys(_categoria_da_lacuna(n) for a in rodada if _trouxe_fatos(a)
                             for n in nao_coletado_vigente(a))
    por_papel = {}
    for chave, papel, _ in _medidas_que_faltaram(rodada):
        por_papel.setdefault(papel if papel in CATEGORIA_DO_PAPEL else "app", set()).add(chave)
    categorias = list(parciais) + [rotulo for papel, rotulo in CATEGORIA_DO_PAPEL.items()
                                   if papel in por_papel and rotulo not in parciais]
    servicos = len(por_papel.get("app", ()))
    return sem_dados + categorias + ([_plural(servicos, "serviço", "serviços")] if servicos else [])


def _motivo_curto(motivo):
    return next((curto for trecho, curto in MOTIVOS_CURTOS if trecho in str(motivo)), MOTIVO_GENERICO)


def _motivo_do_que_faltou(alvos):
    """Conta componente, não pergunta: um serviço mudo em três perguntas tem um motivo só."""
    rodada = _da_rodada(alvos)
    pares = {(chave, _motivo_curto(motivo)) for chave, _, motivo in _medidas_que_faltaram(rodada)}
    pares |= {((i, "alvo", j), _motivo_curto(n.get("motivo") or n.get("reason")))
              for i, a in enumerate(rodada) for j, n in enumerate(nao_coletado_vigente(a))}
    votos = Counter(curto for _, curto in pares)
    return min(votos, key=lambda curto: (-votos[curto], curto)) if votos else None


def _fora_da_rodada(alvos):
    nomes = [a["nome"] for a in alvos if a.get("coletado") is False]
    return f'<p class="bl-fora">Fora desta rodada: {_e(", ".join(nomes))}</p>' if nomes else ""


def _balanco(alvos, nota, fortes, fracos):
    """Medidas e o que o agente escreveu, em duas colunas curtas."""
    from lib.balanco import pontos
    from lib.capa import _legivel
    from lib.html_comum import painel

    def coluna(titulo, itens):
        linhas = "".join(f"<li>{_e(_legivel(i))}</li>" for i in itens)
        return f"<div><h4>{titulo}</h4><ul>{linhas}</ul></div>" if linhas else ""
    bons, ruins = pontos(alvos, nota, fortes, fracos)
    colunas = coluna("Pontos positivos", bons) + coluna("Pontos de atenção", ruins)
    return painel("Pontos positivos e pontos de atenção", "", f'<div class="bl-livre bl-bal" id="pontos-positivos-e-de-atencao">{colunas}</div>',
                  cheio=True) if colunas else ""


def _inventario_da_rodada(inventario, alvos):
    fora = {a.get("nome") for a in alvos if a.get("coletado") is False}
    return [i for i in inventario if i.get("nome") not in fora]


def _alvos_da_rodada(inventario):
    """Onde cada alvo vive: o inventário saiu da capa, e sem o endereço ele é só um nome."""
    if not inventario:
        return ""
    itens = "".join(f'<span class="nome">{_e(i.get("nome"))} · {_e(i.get("onde"))}</span>'
                    for i in sorted(inventario, key=lambda x: str(x.get("nome"))))
    return f'<h3>Alvos desta rodada</h3><div class="nomes">{itens}</div>'


def _so_em_contagem(itens, corte):
    """Só regra inteira de baixa gravidade: um achado alto nunca some junto com os baixos."""
    return corte["baixos_em_contagem"] and all(x.get("severidade") in ("low", "info") for x in itens)


def _a_cobrar(achados):
    """Esperado descreve o normal: a capa não o cobra, e os Problemas também não."""
    return [a for a in achados if not a.get("esperada") and not esperada(a.get("regra"))]


def _regras_visiveis(achados, corte):
    return {regra for regra, itens in _agrupar_por_regra(_a_cobrar(achados)) if not _so_em_contagem(itens, corte)}


def _problemas(achados, recomendacoes, corte):
    baixos, corpo = [], ""
    for regra, itens in _agrupar_por_regra(_a_cobrar(achados)):
        if _so_em_contagem(itens, corte):
            baixos.append((regra, len(itens)))
            continue
        recs = [r for r in recomendacoes if r.get("regra") == regra]
        corpo += _achado_bloco(regra, itens, completo=True, limite=corte["afetados_max"], recomendacoes=recs)
    if baixos:
        corpo += ('<ul class="bl-baixos">'
                  + "".join(f"<li>{_e(rule_meta(r).get('label', r))}: {n}</li>" for r, n in baixos) + "</ul>")
    return corpo


def _esperados_em_contagem(achados):
    quantos = len(achados) - len(_a_cobrar(achados))
    if not quantos:
        return ""
    texto = "achado esperado não entra aqui: descreve" if quantos == 1 \
        else "achados esperados não entram aqui: descrevem"
    return f'<p class="bl-mini">{quantos} {texto} o funcionamento normal.</p>'


def _texto_de_comando(texto):
    return " ".join(html.unescape(str(texto)).split())


def _comandos_exibidos(problemas):
    """Comparar com o bloco inteiro, e não por trecho: `docker ps` não está dentro de `docker ps -a`."""
    return {_texto_de_comando(t) for t in re.findall(r"<(?:pre|code)>(.*?)</(?:pre|code)>", problemas, re.S)}


def _outras_recomendacoes(recomendacoes, regras, problemas=""):
    """Nenhuma some: a da capa perde o que repete, e só sai daqui quando o comando já está no
    problema agrupado. Sem comando, a capa já a mostra por inteiro. Fora da capa, este é o único
    lugar do texto dela."""
    from lib.capa import MAXIMO_DE_PRIORIDADES
    exibidos = _comandos_exibidos(problemas)
    inteiras, comandos = "", ""
    for ordem, r in enumerate(recomendacoes, 1):
        if r.get("regra") in regras:
            continue
        if ordem > MAXIMO_DE_PRIORIDADES:
            inteiras += _recomendacao_inteira(ordem, r)
        elif r.get("comando") and _texto_de_comando(r["comando"]) not in exibidos:
            comandos += _so_o_comando(ordem, r)
    return f"<h3>Outras recomendações</h3>{comandos}{inteiras}" if comandos or inteiras else ""


SINAL_DA_SAIDA = {"137": "SIGKILL", "143": "SIGTERM"}


def _saidas_do_no(no):
    """Os códigos, sem contagem: `failed_examples` é amostra, e "×3" ao lado de 17 falhadas mentiria."""
    codigos = {_exit_code(exemplo)[1] or "?" for exemplo in no.get("failed_examples") or []}
    return " · ".join(f"exit {codigo}" + (f" ({SINAL_DA_SAIDA[codigo]})" if codigo in SINAL_DA_SAIDA else "")
                      for codigo in sorted(codigos))


def _nos_resumidos(alvos):
    com_nos = [a for a in alvos if (a.get("fatos") or {}).get("nodes")]
    return [{"nome": (f'{a.get("nome")} · {n.get("hostname")}' if len(com_nos) > 1 else n.get("hostname")),
             "lider": n.get("leader"), "estado": n.get("state"), "tarefas": n.get("tasks_running"),
             "falhadas": n.get("tasks_failed"), "saidas": _saidas_do_no(n),
             "capacidade": _fmt_capacity(n.get("capacity")), "engine": n.get("engine")}
            for a in com_nos for n in a["fatos"]["nodes"]]


def _linha_de_disco(nome, disco):
    if isinstance(disco, dict):
        return f'Disco de {nome}: não coletado, {disco.get("reason")}.' if disco.get("status") == "n/a" else ""
    tipos = " · ".join(f'{d.get("tipo")} {d.get("tamanho")} ({d.get("recuperavel")} recuperável)' for d in disco or [])
    return f"Disco do nó conectado em {nome}: {tipos}." if tipos else ""


def _linha_de_tls(nome, tls):
    """Validade do acesso ao cluster. A capa traz o certificado dos endpoints, que é outro."""
    if not isinstance(tls, dict):
        return ""
    if tls.get("status") == "n/a":
        return f'TLS do acesso a {nome}: {tls.get("reason")}.'
    certs = tls.get("certs") or []
    if not certs:
        return ""
    primeiro = min(certs, key=lambda c: c["days_left"])
    dias = primeiro["days_left"]
    prazo = f"vence em {dias} dias" if dias >= 0 else f"venceu há {-dias} dias"
    return (f'TLS do acesso a {nome}: {_plural(len(certs), "certificado", "certificados")}, '
            f'o primeiro ({primeiro.get("file")}) {prazo}.')


def _capacidade(alvos):
    linhas = []
    for a in alvos:
        fatos = a.get("fatos") or {}
        nome = a.get("nome")
        linhas += [_linha_de_disco(nome, fatos.get("disk")), _linha_de_tls(nome, fatos.get("tls"))]
    return [linha for linha in linhas if linha]


def _dados_com_corte(papel, alvos, corte):
    from lib.dados_blocos import dados_do_papel
    dados = dados_do_papel(papel, alvos)
    if papel == "consumo" and dados.get("itens"):
        ordem = sorted(dados["itens"], key=lambda i: (-(i.get("cpu") or 0), i.get("nome") or ""))
        dados["itens"] = ordem[:corte["consumo_max"]]
    if papel == "fila":
        dados["filas_max"] = corte["filas_max"]
    if papel == "entrada":
        dados["top"] = corte["urls_geral"]
    if papel == "urls":
        dados["limites"] = {k: v for k, v in corte.items() if k.startswith("urls_")}
    if papel == "maquinas":
        dados.update(nos=_nos_resumidos(alvos), capacidade=_capacidade(alvos))
    return dados


def _outros_papeis(alvos):
    from lib.html_comum import painel
    outros = [c for a in alvos for c in a.get("componentes") or [] if c.get("papel") not in PAPEIS_COM_BLOCO]
    if not outros:
        return ""
    return painel("Outros sistemas", "sem bloco próprio", f'<div class="bl-livre">{_camadas(outros)}</div>', cheio=True)


def _fontes_das_medidas(alvos):
    """Número sem fonte não existe: os blocos mostram o número, e a fonte vale uma vez, aqui."""
    from lib.blocos.entrada import FAIXA_DE_LATENCIA
    from lib.html_comum import inteiro
    respostas = [r for a in alvos for c in a.get("componentes") or [] for r in c.get("respostas") or []
                 if not r.get("sem_dados")]
    fontes = sorted({str(r["fonte"]) for r in respostas if r.get("fonte")})
    if not fontes:
        return ""
    faixa = ""
    if any(r.get("pergunta") == "entrada.latencia" for r in respostas):
        faixa = (f' Tempo de resposta: bom até {inteiro(FAIXA_DE_LATENCIA["bom_ate"])} ms, '
                 f'ruim a partir de {inteiro(FAIXA_DE_LATENCIA["ruim_a_partir"])} ms.')
    return f'<p class="bl-mini">Fonte das medidas: {_e(" · ".join(fontes))}.{_e(faixa)}</p>'


def _blocos_tecnicos(alvos, corte):
    from lib.blocos import render_bloco

    def blocos(*papeis):
        return "".join(render_bloco(p, _dados_com_corte(p, alvos, corte)) for p in papeis)
    return (blocos("maquinas", "entrada", "urls", "fila")
            + f'<div class="bl-par">{blocos("banco", "cache", "consumo", "falhas")}</div>'
            + _outros_papeis(alvos) + _fontes_das_medidas(alvos))


CAMPOS_DA_RECOMENDACAO = ("alvo", "titulo", "porque", "comando", "impacto", "esforco")


def _sem_segredo(texto):
    """Sem o limite de 200 caracteres de `scrub_text`: comando cortado no meio é comando errado."""
    return scrub_text(texto, limit=None) if texto else texto


def _redigir_texto_do_agente(r):
    """Cópia do report com o que o agente escreveu redigido. Quem escreve por cima dos fatos
    copia URL com credencial do que leu, e a allowlist da coleta não passa por esses campos."""
    def recomendacao(rec):
        return dict(rec, **{k: _sem_segredo(rec[k]) for k in CAMPOS_DA_RECOMENDACAO if k in rec})

    def componente(c):
        return dict(c, analise=_sem_segredo(c.get("analise")))

    def alvo(a):
        analises = {k: _sem_segredo(v) for k, v in (a.get("components_analysis") or {}).items()}
        return dict(a, analise=_sem_segredo(a.get("analise")), components_analysis=analises,
                    componentes=[componente(c) for c in a.get("componentes") or []])
    return dict(r, resumo=_sem_segredo(r.get("resumo")),
                fortes=[_sem_segredo(i) for i in r.get("fortes") or []],
                fracos=[_sem_segredo(i) for i in r.get("fracos") or []],
                recomendacoes=[recomendacao(x) for x in r.get("recomendacoes") or []],
                alvos=[alvo(a) for a in r["alvos"]])


def render_html_v3(r):
    """Monta as cinco partes do relatorio. Uma passada de substituicao, sempre: substituir em
    laco reprocessaria o texto ja inserido, e um `%%CORPO%%` escrito pelo agente no resumo
    injetaria uma secao inteira no relatorio."""
    from lib import orcamento_paginas as op
    from lib.capa import render_capa, saude_por_sistema
    from lib.dados_blocos import dados_do_papel, medidas_por_stack

    if r.get("schema_version") == 3:      # o erro de schema continua sendo o de `montar_contexto`
        r = _redigir_texto_do_agente(r)
    ctx = montar_contexto(r)
    alvos = ctx["alvos"]
    achados = ctx["achados"]
    inventario = _inventario_da_rodada(ctx["inventario"], alvos)
    quantos = len(inventario)
    cobrados = _a_cobrar(achados)
    titulo = f'Auditoria de infraestrutura — {_plural(quantos, "alvo", "alvos")}'

    urls = dados_do_papel("urls", alvos)
    top = (r.get("opcoes") or {}).get("top")   # vale também no aperto de páginas: foi pedido
    corte = op.cortes({"achados": len(cobrados), "regras": len(_agrupar_por_regra(cobrados)),
                       "sistemas": _conta_sistemas(alvos), "aceites": len(ctx["aceites"]),
                       "pendencias": len(_mudos_de(alvos)),
                       "filas": len(dados_do_papel("fila", alvos).get("filas") or []),
                       "recomendacoes": len(ctx["recomendacoes"]),
                       "pontos_de_falha": len(dados_do_papel("falhas", alvos).get("itens") or []),
                       "nos": sum(len((a.get("fatos") or {}).get("nodes") or []) for a in alvos),
                       "consumo": len(dados_do_papel("consumo", alvos).get("itens") or []),
                       "urls": op.linhas_de_urls(urls, top), "urls_sites": len(urls.get("sites") or []),
                       "top": top})
    resumo = _rich(_EMOJI_DE_ESTADO.sub(_palavra_de_estado, ctx["resumo"])) if ctx["resumo"] else ""
    ctx["certificados"] = _certificados_de(alvos)
    por_nome = sorted(alvos, key=lambda x: x.get("nome") or "")
    # O alvo com série vem primeiro: um alvo sem medida, à frente na ordem, apagaria a capa.
    ctx["tendencias"] = next((a["tendencias"] for a in por_nome
                              if any((a.get("tendencias") or {}).values())),
                             next((a["tendencias"] for a in por_nome if a.get("tendencias")), {}))
    ctx["motivo_do_que_faltou"] = _motivo_do_que_faltou(alvos)
    # Report anterior à nota não a traz; afirmar "nenhum serviço foi medido" seria falso.
    nota = r.get("nota_geral") or nota_geral(alvos, r.get("aceites") or [])
    capa = render_capa(ctx, nota, resumo, _faltou(alvos))
    avisos = f'<p class="bl-aviso">{_e(" ".join(corte["avisos"]))}</p>' if corte["avisos"] else ""
    saude = _parte("saude-por-sistema", "Saúde por sistema", "Disponibilidade dos últimos 7 dias",
                   saude_por_sistema(alvos, ctx["aceites"], corte["juntar_online"],
                                     medidas_por_stack(alvos)))
    balanco = _balanco(alvos, nota, ctx["fortes"], ctx["fracos"])
    detalhes = _parte("detalhes-tecnicos", "Detalhes técnicos", "por tipo de sistema",
                      _blocos_tecnicos(alvos, corte))
    agrupados = _problemas(achados, ctx["recomendacoes"], corte)
    problemas = _parte("problemas", "Problemas", "cada um explicado uma vez",
                       ((agrupados + _outras_recomendacoes(ctx["recomendacoes"], _regras_visiveis(achados, corte),
                                                          agrupados))
                       or '<p class="bl-mini">Nenhum problema nesta rodada.</p>') + _esperados_em_contagem(achados))
    registro = _parte("registro", "Registro", "riscos aceitos e o que falta declarar",
                      '<h3 id="riscos-aceitos">Riscos aceitos</h3>'
                      + (_aceites_novo(ctx["aceites"]) or '<p class="bl-mini">Nenhum risco aceito.</p>')
                      + '<h3 id="o-que-falta-declarar">O que falta declarar</h3>'
                      + (_pendencias_novo(alvos) or '<p class="bl-mini">Nada a declarar.</p>')
                      + f'<p class="nota-legenda">{NOTA_DO_PAPEL}</p>'
                      + "".join(_divergencias(a) for a in alvos)
                      + _alvos_da_rodada(inventario))
    repl = {
        "%%TITLE%%": _e(titulo),
        "%%FONTES%%": _fontes(),
        "%%CAPA%%": f'<div id="bl-capa">{capa}</div>{avisos}{_fora_da_rodada(alvos)}',
        "%%CORPO%%": saude + balanco + detalhes + problemas + registro,
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

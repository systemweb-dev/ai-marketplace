#!/usr/bin/env python3
"""
Monta a "apostila viva" de um TEMA como UMA PAGINA POR TOPICO (modo Aprender):
  <dir>/meta.json          -> ver estrutura abaixo
  <dir>/topicos/NN.html    -> fragmento HTML do CONTEUDO de cada TOPICO (so o miolo)

Gera:
  <dir>/topico-<seq>.html  -> uma pagina por topico COM conteudo (sidebar compartilhada,
                              hero, conteudo, e navegacao anterior/proximo)
  <dir>/estudo.html        -> porta de entrada: redireciona pro topico atual

Identidade visual compartilhada em theme.py (tokens/base/blocos). Aqui fica so o LAYOUT
da apostila (sidebar+trilha, reader bar, paginacao).

Hierarquia: TEMA -> MODULO (fase) -> TOPICO (item de estudo = uma pagina).
meta.json:
  { "title","level","known","depth","accent",
    "modules":[ {"n":1,"title":"Fundamentos","topics":[
        {"title":"Setup + primeiro programa","status":"current"} ]} ] }
Topicos numerados globalmente (1..N) na ordem; fragmento = topicos/<seq>.html.
status: "done" | "current" | "pending".
"""
import argparse
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import theme  # noqa: E402

ROOT_EXTRA = "  :root{--side-w:300px;--read-w:880px;}\n  html.collapsed{--side-w:74px;}\n"

LAYOUT = r"""
  .app{display:grid;grid-template-columns:var(--side-w) 1fr;transition:grid-template-columns .3s cubic-bezier(.22,1,.36,1);}
  aside{position:sticky;top:0;height:100vh;overflow:hidden;z-index:40;
    background:linear-gradient(176deg,color-mix(in oklab,var(--side),var(--surface) 55%),var(--side));
    border-right:1px solid var(--side-line);display:flex;flex-direction:column;padding:22px 15px;}
  .side__top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:24px;padding:0 3px;}
  .brand{display:flex;align-items:center;gap:10px;font-family:var(--display);font-weight:700;font-size:16px;letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-decoration:none;color:var(--ink);}
  .brand .dot{flex:0 0 auto;width:12px;height:12px;border-radius:50%;
    background:radial-gradient(circle at 34% 30%,var(--accent-lt),var(--accent-dk));
    box-shadow:0 0 0 4px var(--accent-wash),0 0 14px color-mix(in oklab,var(--accent),transparent 50%);}
  .collapse{flex:0 0 auto;width:32px;height:32px;display:grid;place-items:center;cursor:pointer;border-radius:9px;
    color:var(--muted);background:var(--surface);border:1px solid var(--line);transition:.16s;}
  .collapse:hover{color:var(--accent-dk);border-color:var(--accent);}
  .collapse svg{width:15px;height:15px;transition:transform .3s;}
  html.collapsed .collapse svg{transform:rotate(180deg);}
  .course{margin-bottom:20px;padding:0 3px;}
  .course h1{font-family:var(--display);font-weight:700;font-size:19px;line-height:1.15;letter-spacing:-.015em;margin:0 0 12px;white-space:nowrap;overflow:hidden;}
  .chips{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:16px;}
  .chip{font:600 10px/1.4 var(--mono);letter-spacing:.04em;text-transform:uppercase;padding:4px 9px;border-radius:99px;
    color:var(--ink-soft);background:var(--surface);border:1px solid var(--line);white-space:nowrap;}
  .chip b{color:var(--accent-dk);}
  .prog{display:flex;align-items:center;gap:9px;}
  .prog .track{flex:1;height:6px;border-radius:99px;background:var(--line);overflow:hidden;}
  .prog .track i{display:block;height:100%;width:var(--pct);border-radius:99px;background:linear-gradient(90deg,var(--accent),var(--accent-2));}
  .prog .pc{font:700 11px/1 var(--mono);color:var(--muted);}
  nav{flex:1;overflow-y:auto;margin:10px -3px 0;padding:4px 3px;}
  nav .lbl{font:600 10px/1 var(--mono);letter-spacing:.2em;text-transform:uppercase;color:var(--muted);margin:0 7px 6px;}
  .modgroup{margin-bottom:2px;}
  .grouphead{display:flex;align-items:center;gap:8px;font:700 10px/1 var(--mono);letter-spacing:.13em;text-transform:uppercase;color:var(--muted);padding:13px 9px 7px;}
  .grouphead .gn{color:var(--accent-dk);}
  .topiclist{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:1px;}
  .topitem{position:relative;display:grid;grid-template-columns:26px 1fr;align-items:center;gap:11px;padding:7px 9px;border-radius:11px;transition:background .15s;}
  .topitem .n{width:26px;height:26px;border-radius:8px;display:grid;place-items:center;font:600 11px/1 var(--mono);color:var(--muted);background:var(--tint);border:1px solid transparent;transition:.15s;}
  .topitem .t{font-family:var(--display);font-size:14px;color:var(--ink-soft);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-decoration:none;}
  a.t:hover{color:var(--accent-dk);}
  .topitem:hover{background:var(--tint);} .topitem:hover .n{border-color:var(--line);}
  .topitem.done .n{color:var(--done);background:color-mix(in oklab,var(--done),var(--surface) 80%);}
  .topitem.active{background:linear-gradient(100deg,var(--accent-wash),transparent 80%);}
  .topitem.active .n{color:#fff;background:linear-gradient(135deg,var(--accent),var(--accent-2));box-shadow:0 6px 14px -7px var(--accent);}
  .topitem.active .t{color:var(--ink);font-weight:700;}
  .side__foot{margin-top:8px;padding-top:14px;border-top:1px solid var(--side-line);}
  .seg{display:flex;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:3px;gap:2px;}
  .seg button{flex:1;display:flex;align-items:center;justify-content:center;gap:6px;border:0;background:none;cursor:pointer;
    font:600 11px/1 var(--mono);letter-spacing:.04em;text-transform:uppercase;color:var(--muted);padding:7px 8px;border-radius:7px;transition:.15s;}
  .seg button svg{width:14px;height:14px;} .seg button:hover{color:var(--ink-soft);}
  html:not([data-theme="dark"]) .seg .b-light{background:var(--accent-wash);color:var(--accent-dk);}
  html[data-theme="dark"] .seg .b-dark{background:var(--accent-wash);color:var(--accent-dk);}
  html.collapsed .brand span,html.collapsed .course h1,html.collapsed .chips,
  html.collapsed .prog .pc,html.collapsed nav .lbl,html.collapsed .grouphead,html.collapsed .topitem .t,html.collapsed .seg button span{display:none;}
  html.collapsed .topitem{grid-template-columns:1fr;justify-items:center;padding:7px 0;}
  html.collapsed .prog .track{display:none;} html.collapsed .seg{flex-direction:column;}

  main{min-width:0;position:relative;}
  .reader__bar{position:sticky;top:0;z-index:30;display:flex;align-items:center;justify-content:space-between;gap:16px;
    padding:13px clamp(28px,5vw,72px);background:color-mix(in oklab,var(--bg),transparent 18%);
    border-bottom:1px solid transparent;backdrop-filter:blur(14px) saturate(1.1);transition:border-color .2s,background .2s;}
  .reader__bar.stuck{border-color:var(--line);background:color-mix(in oklab,var(--bg),transparent 8%);}
  .crumbs{display:flex;align-items:center;gap:9px;min-width:0;font:600 11px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);}
  .crumbs .home{color:var(--ink-soft);text-decoration:none;white-space:nowrap;} .crumbs .home:hover{color:var(--accent-dk);} .crumbs .sep{opacity:.5;} .crumbs .pos{color:var(--accent-dk);}
  .crumbs .now{font-family:var(--display);font-weight:600;font-size:13.5px;letter-spacing:-.01em;text-transform:none;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .menu-btn{display:none;width:38px;height:38px;border-radius:11px;place-items:center;cursor:pointer;color:var(--ink-soft);
    background:var(--surface);border:1px solid var(--line);margin-right:4px;transition:.16s;}
  .menu-btn:hover{color:var(--accent-dk);border-color:var(--accent);} .menu-btn svg{width:18px;height:18px;}
  .tools{display:flex;align-items:center;gap:10px;flex:0 0 auto;}
  .iconbtn{width:38px;height:38px;border-radius:11px;display:grid;place-items:center;cursor:pointer;color:var(--ink-soft);
    background:var(--surface);border:1px solid var(--line);transition:.16s;}
  .iconbtn:hover{color:var(--accent-dk);border-color:var(--accent);}
  .iconbtn svg{width:17px;height:17px;} .iconbtn .sun{display:none;}
  html[data-theme="dark"] .iconbtn .moon{display:none;} html[data-theme="dark"] .iconbtn .sun{display:block;}
  .askwrap{position:relative;}
  .ask{display:inline-flex;align-items:center;gap:7px;color:#fff;background:linear-gradient(135deg,var(--accent),var(--accent-2));border:0;
    padding:10px 16px;border-radius:99px;cursor:pointer;font-family:var(--display);font-weight:600;font-size:13px;
    box-shadow:0 8px 18px -9px var(--accent);transition:.15s;}
  .ask:hover{transform:translateY(-1px);box-shadow:0 12px 22px -10px var(--accent);}
  .askpop{position:absolute;right:0;top:50px;width:344px;background:var(--surface);border:1px solid var(--line);border-radius:16px;
    box-shadow:0 28px 60px -26px rgba(var(--shadow),.4);padding:16px;opacity:0;visibility:hidden;transform:translateY(-6px);transition:.18s;z-index:50;}
  .askpop.open{opacity:1;visibility:visible;transform:none;}
  .askpop .h{font-family:var(--display);font-weight:700;font-size:14px;color:var(--ink);margin:0 0 4px;}
  .askpop .s{font-family:var(--body);font-size:13px;line-height:1.5;color:var(--ink-soft);margin:0 0 12px;}
  .askpop .q{display:block;width:100%;text-align:left;font-family:var(--body);font-size:13.5px;color:var(--ink);
    background:var(--tint);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:6px 0;cursor:pointer;transition:.14s;}
  .askpop .q:hover{border-color:var(--accent);background:var(--accent-wash);}
  .askpop .q small{display:block;font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:3px;}
  .askpop .copied{color:var(--done);font-weight:600;}

  .read{max-width:var(--read-w);margin:0 auto;padding:6px clamp(28px,5vw,40px) 120px;}
  .top{animation:rise .5s cubic-bezier(.22,1,.36,1) both;padding-top:24px;}

  .paginate{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:52px 0 0;}
  .pg{display:flex;flex-direction:column;gap:5px;padding:18px 22px;border:1px solid var(--line);border-radius:16px;text-decoration:none;
    background:var(--surface);box-shadow:0 1px 2px rgba(var(--shadow),.05);transition:.16s;}
  .pg.next{align-items:flex-end;text-align:right;}
  a.pg:hover{border-color:color-mix(in oklab,var(--accent),transparent 50%);transform:translateY(-2px);box-shadow:0 18px 40px -26px rgba(var(--shadow),.5);}
  .pg .dir{font:700 10.5px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--accent-dk);}
  .pg .tt{font-family:var(--display);font-weight:700;font-size:17px;color:var(--ink);letter-spacing:-.01em;}
  .pg.empty{opacity:.45;pointer-events:none;} .pg.teaser{cursor:default;} .pg.teaser .tt{color:var(--muted);}
  @media(max-width:600px){.paginate{grid-template-columns:1fr;}}

  .scrim{position:fixed;inset:0;background:rgba(8,12,26,.5);opacity:0;visibility:hidden;z-index:38;transition:.25s;}
  @media(max-width:880px){.app{grid-template-columns:1fr;}
    aside{position:fixed;width:288px;z-index:45;transform:translateX(-100%);transition:transform .3s;box-shadow:0 0 60px -10px rgba(0,0,0,.4);}
    body.mobnav aside{transform:none;} body.mobnav .scrim{opacity:1;visibility:visible;} .menu-btn{display:grid;}}
"""

BODY = r"""
<div class="topline"></div>
<div class="scrim" onclick="document.body.classList.remove('mobnav')"></div>
<div class="app">
  <aside>
    <div class="side__top">
      <a class="brand" href="estudo.html"><span class="dot"></span><span>Study Buddy</span></a>
      <div class="collapse" onclick="toggleNav()" title="Recolher / expandir">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
      </div>
    </div>
    <div class="course">
      <h1>%%TITLE%%</h1>
      <div class="chips">%%CHIPS%%</div>
      <div class="prog" style="--pct:%%PCT%%%"><div class="track"><i></i></div><span class="pc">%%DONE%%/%%TOTAL%%</span></div>
    </div>
    <nav><div class="lbl">Trilha</div>%%NAV%%</nav>
    <div class="side__foot">
      <div class="seg">
        <button class="b-light" onclick="setTheme('light')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6L19 19M19 5l-1.4 1.4M6.4 17.6L5 19"/></svg><span>Claro</span></button>
        <button class="b-dark" onclick="setTheme('dark')"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg><span>Escuro</span></button>
      </div>
    </div>
  </aside>

  <main>
    <div class="reader__bar" id="rbar">
      <div class="crumbs">
        <div class="menu-btn" onclick="document.body.classList.toggle('mobnav')" title="Trilha">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
        </div>
        <a class="home" href="estudo.html">%%TITLE%%</a><span class="sep">/</span>
        <span class="pos">%%CRUMBMOD%%</span>
        <span class="now">· %%PTITLE%%</span>
      </div>
      <div class="tools">
        <div class="iconbtn" onclick="setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark')" title="Alternar tema">
          <svg class="moon" viewBox="0 0 24 24" fill="currentColor"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
          <svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6L19 19M19 5l-1.4 1.4M6.4 17.6L5 19"/></svg>
        </div>
        <div class="askwrap">
          <span class="ask" onclick="document.querySelector('.askpop').classList.toggle('open')">✦ Perguntar sobre isto</span>
          <div class="askpop">
            <p class="h">Pergunte no chat do Claude</p>
            <p class="s">A página é o material; a tutoria acontece no chat. Clique numa pergunta pra <b>copiar</b> e colar lá — ou digite a sua.</p>
            <button class="q" onclick="sbcopy(this,'Não entendi um trecho deste tópico — me explica de outro jeito.')">Me explica de outro jeito<small>copiar pro chat</small></button>
            <button class="q" onclick="sbcopy(this,'Me dá um exercício pra fixar este tópico.')">Me dá um exercício pra fixar<small>copiar pro chat</small></button>
            <button class="q" onclick="sbcopy(this,'Roda um exemplo deste tópico pra mim e mostra a saída.')">Roda um exemplo pra mim<small>copiar pro chat</small></button>
          </div>
        </div>
      </div>
    </div>
    <article class="read">
      <section class="top">%%CONTENT%%</section>
      %%PAGINATE%%
    </article>
  </main>
</div>
"""

APOSTILA_JS = (
    "<script>\n"
    "function toggleNav(){const c=document.documentElement.classList.toggle('collapsed');try{localStorage.setItem('sb-nav',c?'collapsed':'open');}catch(e){}}\n"
    "document.addEventListener('click',e=>{ if(!e.target.closest('.askwrap')) document.querySelector('.askpop').classList.remove('open'); });\n"
    "const _bar=document.getElementById('rbar');\n"
    "addEventListener('scroll',()=>{const h=document.documentElement,m=h.scrollHeight-h.clientHeight;"
    "document.querySelector('.topline').style.width=(m>0?h.scrollTop/m*100:0)+'%';"
    "_bar.classList.toggle('stuck',h.scrollTop>120);},{passive:true});\n"
    "</script>"
)

PAGE = (
    theme.head("%%PTITLE%% — %%TITLE%%")
    + "\n<style>" + theme.TOKENS + ROOT_EXTRA + theme.BASE + theme.BLOCKS + LAYOUT
    + "</style>\n</head>\n<body>\n" + BODY + theme.JS + "\n" + APOSTILA_JS + "\n</body>\n</html>"
)

REDIRECT = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>%%TITLE%% — Study Buddy</title>
<script>location.replace("%%TARGET%%");</script>
<meta http-equiv="refresh" content="0;url=%%TARGET%%">
<style>body{font-family:system-ui,sans-serif;background:#0c1220;color:#aab4c8;display:grid;place-items:center;height:100vh;margin:0}</style>
</head><body><p>Abrindo seu tópico atual… <a href="%%TARGET%%" style="color:#5b86f5">continuar</a></p></body></html>
"""

DEFAULT_ACCENT = "#2f6bf0"


def _reading_time(frag):
    return max(1, round(len(re.sub(r"<[^>]+>", " ", frag).split()) / 180))


def _chips(meta):
    chips = []
    lvl = str(meta.get("level", "")).strip()
    if lvl:
        chips.append(f'<span class="chip">{html.escape(lvl)}</span>')
    known = str(meta.get("known", "")).strip()
    if known:
        chips.append(f'<span class="chip">base <b>{html.escape(known)}</b></span>')
    depth = str(meta.get("depth", "")).strip()
    if depth:
        chips.append(f'<span class="chip">{html.escape(depth)}</span>')
    return "".join(chips)


def _nav(groups, have, active_seq):
    out = []
    for g in groups:
        items = []
        for t in g["topics"]:
            s = t["seq"]
            cls = t["status"] + (" active" if s == active_seq else "")
            if s in have:
                lab = f'<a class="t" href="topico-{s}.html">{html.escape(t["title"])}</a>'
            else:
                lab = f'<span class="t" title="ainda não disponível">{html.escape(t["title"])}</span>'
            items.append(f'<li class="topitem {cls}"><span class="n">{s:02d}</span>{lab}</li>')
        head = f'<div class="grouphead"><span class="gn">{int(g["n"]):02d}</span>{html.escape(g["title"])}</div>'
        out.append(f'<div class="modgroup">{head}<ul class="topiclist">{"".join(items)}</ul></div>')
    return "".join(out)


def build(d):
    with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)

    groups, seq = [], 0
    for mi, m in enumerate(meta.get("modules", []), 1):
        gt = []
        for t in m.get("topics", []):
            seq += 1
            gt.append({"seq": seq, "title": t.get("title", ""),
                       "status": t.get("status", "pending"), "mod": m.get("title", "")})
        groups.append({"n": m.get("n", mi), "title": m.get("title", ""), "topics": gt})
    all_t = [t for g in groups for t in g["topics"]]
    total = len(all_t)
    done = sum(1 for t in all_t if t["status"] == "done")
    pct = round(done / total * 100) if total else 0

    topdir = os.path.join(d, "topicos")
    frags = {}
    if os.path.isdir(topdir):
        for fn in sorted(os.listdir(topdir)):
            if fn.endswith(".html"):
                frags[int(fn.split(".")[0])] = open(os.path.join(topdir, fn), encoding="utf-8").read()
    have = set(frags)
    content_seqs = [t["seq"] for t in all_t if t["seq"] in have]
    by_seq = {t["seq"]: t for t in all_t}

    title_esc = html.escape(meta.get("title", "Estudo"))
    accent = meta.get("accent", DEFAULT_ACCENT)
    chips = _chips(meta)
    known = str(meta.get("known", "")).strip()
    base = {"%%TITLE%%": title_esc, "%%ACCENT%%": accent, "%%CHIPS%%": chips,
            "%%PCT%%": f"{pct}", "%%DONE%%": str(done), "%%TOTAL%%": str(total)}

    written = []
    for i, s in enumerate(content_seqs):
        t = by_seq[s]
        frag = frags[s]
        rt = _reading_time(frag)
        meta_row = [f'<span class="d"><b>Tópico {s:02d}</b> de {total}</span>',
                    '<span class="dotmark"></span>', f'<span class="d">~{rt} min de leitura</span>']
        if known:
            meta_row += ['<span class="dotmark"></span>', f'<span class="d">base <b>{html.escape(known)}</b></span>']
        hero = (f'<header class="hero"><span class="eyebrow">{html.escape(t["mod"])}</span>'
                f'<h2>{html.escape(t["title"])}</h2><div class="herometa">{"".join(meta_row)}</div></header>')
        content = hero + "\n" + frag

        prev_s = content_seqs[i - 1] if i > 0 else None
        if prev_s:
            pt = by_seq[prev_s]
            prev_html = (f'<a class="pg prev" href="topico-{prev_s}.html"><span class="dir">← Anterior</span>'
                         f'<span class="tt">{html.escape(pt["title"])}</span></a>')
        else:
            prev_html = '<span class="pg prev empty"><span class="dir">← Anterior</span><span class="tt">Início da trilha</span></span>'
        next_s = content_seqs[i + 1] if i + 1 < len(content_seqs) else None
        if next_s:
            nt = by_seq[next_s]
            next_html = (f'<a class="pg next" href="topico-{next_s}.html"><span class="dir">Próximo →</span>'
                         f'<span class="tt">{html.escape(nt["title"])}</span></a>')
        else:
            pend = next((x for x in all_t if x["seq"] > s and x["seq"] not in have), None)
            if pend:
                next_html = (f'<span class="pg next teaser"><span class="dir">Próximo · em breve</span>'
                             f'<span class="tt">{html.escape(pend["title"])}</span></span>')
            else:
                next_html = '<span class="pg next teaser"><span class="dir">Fim</span><span class="tt">✓ Trilha concluída</span></span>'

        page = PAGE
        repl = dict(base)
        repl["%%PTITLE%%"] = html.escape(t["title"])
        repl["%%CRUMBMOD%%"] = html.escape(t["mod"])
        repl["%%NAV%%"] = _nav(groups, have, s)
        repl["%%CONTENT%%"] = content
        repl["%%PAGINATE%%"] = f'<nav class="paginate">{prev_html}{next_html}</nav>'
        for k, v in repl.items():
            page = page.replace(k, v)
        out = os.path.join(d, f"topico-{s}.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(page)
        written.append(out)

    cur = next((t["seq"] for t in all_t if t["status"] == "current" and t["seq"] in have), None) \
        or (content_seqs[0] if content_seqs else None)
    estudo = os.path.join(d, "estudo.html")
    if cur:
        page = REDIRECT.replace("%%TITLE%%", title_esc).replace("%%TARGET%%", f"topico-{cur}.html")
    else:
        page = ("<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'><title>"
                + title_esc + "</title></head><body style='font-family:system-ui;padding:40px'>"
                "<p>Ainda sem tópicos com conteúdo. Comece o primeiro no chat.</p></body></html>")
    with open(estudo, "w", encoding="utf-8") as f:
        f.write(page)

    print(estudo)
    for w in written:
        print(w)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="diretorio do tema (com meta.json e topicos/)")
    args = ap.parse_args()
    d = os.path.expanduser(args.dir)
    if not os.path.isfile(os.path.join(d, "meta.json")):
        sys.exit(f"meta.json nao encontrado em {d}")
    build(d)

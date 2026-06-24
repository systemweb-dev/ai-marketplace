#!/usr/bin/env python3
"""
Gera/atualiza uma FICHA (modos Explicar e Praticar) com a identidade visual compartilhada
(theme.py). A ficha e' um documento VIVO: a cada pedido, o fragmento de conteudo cresce
(novas secoes <h3>) e a pagina e' regenerada — com um INDICE lateral que aparece quando ha
2+ secoes (scroll-spy). Build idempotente: rode de novo apos editar o fragmento.

Uso:
  python3 build_ficha.py --kind explicar --title "O que e closure?" \
      --content <fragmento.html> --dir <dir-do-tema-ou-scratch> [--tema "JavaScript"] [--accent "#2f6bf0"]

Estruture a explicacao em secoes com <h3>Titulo da secao</h3> — viram o indice lateral.
Saida: <dir>/explicacoes/<slug>.html  (ou praticas/<slug>.html).
"""
import argparse
import html
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import theme  # noqa: E402

LAYOUT = r"""
  .topbar{position:sticky;top:0;z-index:35;display:flex;align-items:center;justify-content:space-between;gap:14px;
    padding:12px clamp(18px,4vw,28px);background:color-mix(in oklab,var(--bg),transparent 14%);backdrop-filter:blur(14px) saturate(1.1);
    border-bottom:1px solid transparent;transition:border-color .2s;}
  .topbar.stuck{border-color:var(--line);}
  .topbar .lead{display:flex;align-items:center;gap:10px;min-width:0;font:600 11px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);}
  .topbar .lead .dot{width:11px;height:11px;border-radius:50%;background:radial-gradient(circle at 34% 30%,var(--accent-lt),var(--accent-dk));box-shadow:0 0 0 4px var(--accent-wash);}
  .topbar .back{display:inline-flex;align-items:center;gap:7px;color:var(--ink-soft);text-decoration:none;} .topbar .back:hover{color:var(--accent-dk);}
  .menu-btn{display:none;width:36px;height:36px;border-radius:10px;place-items:center;cursor:pointer;color:var(--ink-soft);background:var(--surface);border:1px solid var(--line);}
  .menu-btn svg{width:18px;height:18px;}
  .iconbtn{width:36px;height:36px;border-radius:10px;display:grid;place-items:center;cursor:pointer;color:var(--ink-soft);background:var(--surface);border:1px solid var(--line);transition:.16s;}
  .iconbtn:hover{color:var(--accent-dk);border-color:var(--accent);} .iconbtn svg{width:17px;height:17px;} .iconbtn .sun{display:none;}
  html[data-theme="dark"] .iconbtn .moon{display:none;} html[data-theme="dark"] .iconbtn .sun{display:block;}

  .shell{display:grid;grid-template-columns:1fr;max-width:1480px;margin:0 auto;}
  .shell.withnav{grid-template-columns:280px 1fr;}
  aside.toc{position:sticky;top:57px;align-self:start;height:calc(100vh - 57px);overflow-y:auto;padding:26px 18px;border-right:1px solid var(--line);}
  aside.toc .tochead{font:600 10px/1 var(--mono);letter-spacing:.18em;text-transform:uppercase;color:var(--muted);margin:0 8px 14px;}
  aside.toc ol{list-style:none;margin:0;padding:0;counter-reset:s;display:flex;flex-direction:column;gap:1px;}
  aside.toc li{counter-increment:s;}
  aside.toc a{position:relative;display:grid;grid-template-columns:22px 1fr;gap:9px;align-items:start;padding:8px 9px;border-radius:9px;
    text-decoration:none;font-family:var(--display);font-size:14px;color:var(--ink-soft);transition:background .15s,color .15s;}
  aside.toc a::before{content:counter(s,decimal-leading-zero);font:600 11px/1.5 var(--mono);color:var(--muted);}
  aside.toc a:hover{background:var(--tint);color:var(--accent-dk);}
  aside.toc a.active{background:linear-gradient(100deg,var(--accent-wash),transparent 80%);color:var(--ink);font-weight:700;}
  aside.toc a.active::before{color:var(--accent-dk);}

  main.wrap{min-width:0;padding:30px clamp(22px,5vw,44px) 120px;animation:rise .5s cubic-bezier(.22,1,.36,1) both;}
  .shell:not(.withnav) main.wrap{max-width:760px;margin:0 auto;}
  .shell.withnav main.wrap{max-width:900px;margin:0 auto;padding-left:clamp(22px,4vw,64px);padding-right:clamp(22px,4vw,64px);}
  main.wrap h1{font-family:var(--display);font-weight:800;font-size:clamp(34px,5vw,50px);line-height:1.05;letter-spacing:-.03em;margin:14px 0 22px;}
  .cta{margin:46px 0 0;padding-top:26px;border-top:1px solid var(--line);}
  .cta .lbl{font:700 11px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:14px;}
  .cta .row{display:flex;flex-wrap:wrap;gap:10px;}
  .cta button{font-family:var(--display);font-weight:600;font-size:14px;color:var(--ink);background:var(--surface);border:1px solid var(--line);
    border-radius:12px;padding:12px 16px;cursor:pointer;transition:.15s;display:flex;flex-direction:column;gap:3px;}
  .cta button:hover{border-color:var(--accent);transform:translateY(-1px);box-shadow:0 12px 26px -18px rgba(var(--shadow),.6);}
  .cta button small{font-family:var(--mono);font-size:10px;color:var(--muted);} .cta button .copied{color:var(--done);font-weight:700;}

  .scrim{position:fixed;inset:0;background:rgba(8,12,26,.5);opacity:0;visibility:hidden;z-index:34;transition:.25s;}
  @media(max-width:820px){.shell.withnav{grid-template-columns:1fr;}
    aside.toc{position:fixed;top:0;left:0;width:280px;height:100vh;z-index:40;background:var(--surface);transform:translateX(-100%);transition:transform .3s;box-shadow:0 0 60px -10px rgba(0,0,0,.4);}
    body.mobnav aside.toc{transform:none;} body.mobnav .scrim{opacity:1;visibility:visible;} .shell.withnav .menu-btn{display:grid;}}
"""

BODY = r"""
<div class="topline"></div>
<div class="scrim" onclick="document.body.classList.remove('mobnav')"></div>
<header class="topbar" id="topbar">
  <div class="lead">
    <div class="menu-btn" onclick="document.body.classList.toggle('mobnav')" title="Índice"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg></div>
    %%BACK%%
  </div>
  <div class="iconbtn" onclick="setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark')" title="Alternar tema">
    <svg class="moon" viewBox="0 0 24 24" fill="currentColor"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
    <svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6L19 19M19 5l-1.4 1.4M6.4 17.6L5 19"/></svg>
  </div>
</header>
<div class="shell %%APPCLASS%%">
  %%ASIDE%%
  <main class="wrap">
    <span class="eyebrow">%%KIND%%</span>
    <h1>%%TITLE%%</h1>
    <div class="top">%%CONTENT%%</div>
    <div class="cta"><div class="lbl">Continuar no chat</div><div class="row">%%CTA%%</div></div>
  </main>
</div>
"""

JS = (
    "<script>const _tb=document.getElementById('topbar');"
    "addEventListener('scroll',()=>{const h=document.documentElement,m=h.scrollHeight-h.clientHeight;"
    "document.querySelector('.topline').style.width=(m>0?h.scrollTop/m*100:0)+'%';"
    "_tb.classList.toggle('stuck',h.scrollTop>40);},{passive:true});"
    "const _tl={};document.querySelectorAll('aside.toc a[href^=\"#sec-\"]').forEach(a=>{_tl[a.getAttribute('href').slice(1)]=a;});"
    "if('IntersectionObserver' in window){const o=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting){"
    "Object.values(_tl).forEach(a=>a.classList.remove('active'));const a=_tl[e.target.id];if(a)a.classList.add('active');}});},"
    "{rootMargin:'-20% 0px -70% 0px',threshold:0});document.querySelectorAll('.top h3[id]').forEach(s=>o.observe(s));}</script>"
)

PAGE = (
    theme.head("%%TITLE%% — Study Buddy")
    + "\n<style>" + theme.TOKENS + theme.BASE + theme.BLOCKS + LAYOUT
    + "</style>\n</head>\n<body>\n" + BODY + theme.JS + "\n" + JS + "\n</body>\n</html>"
)

DEFAULT_ACCENT = "#2f6bf0"
KIND_LABEL = {"explicar": "Explicação", "praticar": "Prática"}
SUBDIR = {"explicar": "explicacoes", "praticar": "praticas"}


def _slug(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s or "ficha")[:60]


def _sections(content):
    """Da id a cada <h3> (secao) e devolve (html_com_ids, [(id, texto), ...]) p/ o indice."""
    secs, i = [], [0]

    def repl(m):
        i[0] += 1
        sid = f"sec-{i[0]}"
        attrs, inner = m.group(1) or "", m.group(2)
        secs.append((sid, re.sub(r"<[^>]+>", "", inner).strip()))
        return f'<h3 id="{sid}"{attrs}>{inner}</h3>'

    return re.sub(r"<h3([^>]*)>(.*?)</h3>", repl, content, flags=re.S), secs


def _cta(kind, title):
    t = title.replace("'", "")
    if kind == "explicar":
        items = [("Praticar isto", f"Me dá uns exercícios sobre: {t}"),
                 ("Virar uma trilha", f"Quero aprender do zero o tema por trás de: {t} — monta uma trilha"),
                 ("Aprofundar", f"Aprofunda mais: {t}")]
    else:
        items = [("Corrigir minha resposta", "Corrige minha resposta do desafio (vou colar abaixo)."),
                 ("Outro desafio", f"Me dá outro desafio sobre: {t}"),
                 ("Mudar a dificuldade", "Deixa o próximo desafio mais difícil (ou mais fácil).")]
    return "".join(
        f'<button onclick="sbcopy(this,{json.dumps(prompt, ensure_ascii=False)})">'
        f'{html.escape(label)}<small>copiar pro chat</small></button>'
        for label, prompt in items
    )


def build(kind, title, content, d, tema, accent):
    sub = os.path.join(d, SUBDIR[kind])
    os.makedirs(sub, exist_ok=True)
    content, secs = _sections(content)
    withnav = len(secs) >= 2

    if os.path.isfile(os.path.join(d, "estudo.html")):
        lab = html.escape(tema) if tema else "trilha"
        back = f'<a class="back" href="../estudo.html"><span class="dot"></span>← {lab}</a>'
    elif tema:
        back = f'<span class="dot"></span>{html.escape(tema)}'
    else:
        back = '<span class="dot"></span>Study Buddy'

    if withnav:
        toc = "".join(f'<li><a href="#{sid}">{html.escape(txt)}</a></li>' for sid, txt in secs)
        aside = f'<aside class="toc"><div class="tochead">Nesta explicação</div><ol>{toc}</ol></aside>'
    else:
        aside = ""

    page = PAGE
    for k, v in {
        "%%TITLE%%": html.escape(title),
        "%%ACCENT%%": accent,
        "%%KIND%%": KIND_LABEL.get(kind, kind),
        "%%BACK%%": back,
        "%%APPCLASS%%": "withnav" if withnav else "",
        "%%ASIDE%%": aside,
        "%%CONTENT%%": content,
        "%%CTA%%": _cta(kind, title),
    }.items():
        page = page.replace(k, v)

    out = os.path.join(sub, _slug(title) + ".html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=["explicar", "praticar"])
    ap.add_argument("--title", required=True, help="a pergunta (explicar) ou o foco (praticar)")
    ap.add_argument("--content", required=True, help="caminho do fragmento HTML (cresce a cada pedido)")
    ap.add_argument("--dir", required=True, help="dir do tema (com estudo.html) ou scratch")
    ap.add_argument("--tema", default="", help="nome do tema, p/ link de volta e contexto")
    ap.add_argument("--accent", default=DEFAULT_ACCENT)
    args = ap.parse_args()
    cpath = os.path.expanduser(args.content)
    if not os.path.isfile(cpath):
        sys.exit(f"fragmento nao encontrado: {cpath}")
    with open(cpath, encoding="utf-8") as f:
        content = f.read()
    build(args.kind, args.title, content, os.path.expanduser(args.dir), args.tema, args.accent)

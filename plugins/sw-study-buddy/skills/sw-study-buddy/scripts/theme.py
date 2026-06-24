#!/usr/bin/env python3
"""
Identidade visual compartilhada do Study Buddy.

Fonte CANONICA de tokens, base, blocos, fontes e JS comum — usada tanto pela apostila
(build_study_page.py, modo Aprender) quanto pelas fichas (build_ficha.py, Explicar/Praticar).
Mudou cor/fonte/estilo de bloco? Mude AQUI e os dois geradores acompanham.

O layout especifico (sidebar+trilha da apostila vs casca enxuta da ficha) fica em cada gerador.
A cor de accent entra via o placeholder %%ACCENT%% (cada gerador faz o .replace).
"""

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700;800'
    '&family=Literata:ital,opsz,wght@0,7..72,400..600;1,7..72,400'
    '&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">\n'
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">\n'
    '<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>'
)

# Aplica tema/estado salvos antes do render (evita flash). Le 'sb-theme' e 'sb-nav'.
THEME_INIT = (
    "<script>(function(){try{var d=document.documentElement;"
    "if(localStorage.getItem('sb-theme')==='dark')d.dataset.theme='dark';"
    "if(localStorage.getItem('sb-nav')==='collapsed')d.classList.add('collapsed');"
    "}catch(e){}})();</script>"
)

# Tokens de cor/tipografia (claro + escuro). %%ACCENT%% e' substituido por cada gerador.
TOKENS = r"""
  :root{
    --bg:#f7f9fd;--bg2:#eef3fb;--surface:#ffffff;--tint:#eef2f9;
    --ink:#141d33;--ink-soft:#4c5772;--muted:#909cb4;--line:#e4eaf4;--line-soft:#eef2f8;
    --side:#f3f6fc;--side-line:#e3eaf5;
    --accent-base:%%ACCENT%%;
    --accent:var(--accent-base);
    --accent-2:color-mix(in oklab,var(--accent),#6a4ff2 36%);
    --accent-dk:color-mix(in oklab,var(--accent),#000 26%);
    --accent-lt:color-mix(in oklab,var(--accent),#fff 16%);
    --accent-wash:color-mix(in oklab,var(--accent),transparent 90%);
    --done:#2f9e7a;--code-bg:#0e1a30;--code-bg2:#13213c;--code-fg:#dde7f6;
    --shadow:32,60,140;
    --display:'Hanken Grotesk',system-ui,sans-serif;--body:'Literata',Georgia,serif;--mono:'JetBrains Mono',monospace;
  }
  html[data-theme="dark"]{
    --bg:#0c1220;--bg2:#080d18;--surface:#141c2e;--tint:#1b2439;
    --ink:#e9eef8;--ink-soft:#aab4c8;--muted:#6f7c95;--line:#26314a;--line-soft:#1c273e;
    --side:#0f1626;--side-line:#222e45;
    --accent:color-mix(in oklab,var(--accent-base),#fff 22%);
    --accent-2:color-mix(in oklab,var(--accent),#8a6ff7 32%);
    --accent-dk:color-mix(in oklab,var(--accent),#fff 30%);
    --accent-lt:color-mix(in oklab,var(--accent),#fff 14%);
    --accent-wash:color-mix(in oklab,var(--accent),transparent 84%);
    --done:#46c79a;--code-bg:#0a1120;--code-bg2:#0e1828;--code-fg:#dde7f6;
    --shadow:0,0,0;
  }
"""

# Reset + body + barra de leitura + keyframe/reduced-motion compartilhados.
BASE = r"""
  *{box-sizing:border-box;}
  html{scroll-behavior:smooth;}
  body{margin:0;color:var(--ink);font:18px/1.8 var(--body);
    background:radial-gradient(1200px 600px at 88% -14%,var(--accent-wash),transparent 56%),
      radial-gradient(800px 500px at 0% 8%,color-mix(in oklab,var(--accent),transparent 92%),transparent 60%),
      linear-gradient(180deg,var(--bg),var(--bg2));}
  .topline{position:fixed;top:0;left:0;height:3px;width:0;z-index:60;
    background:linear-gradient(90deg,var(--accent-lt),var(--accent),var(--accent-2));box-shadow:0 0 14px var(--accent-wash);transition:width .1s linear;}
  @keyframes rise{from{opacity:0;transform:translateY(12px);}to{opacity:1;transform:none;}}
  @media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;}html{scroll-behavior:auto;}}
"""

# Cabecalho de conteudo (hero) + tipografia + os blocos reutilizaveis. Funcionam dentro de `.top`.
BLOCKS = r"""
  .hero{padding:18px 0 0;margin-bottom:8px;}
  .eyebrow{display:inline-flex;align-items:center;gap:10px;font:700 12px/1 var(--mono);letter-spacing:.18em;text-transform:uppercase;color:var(--accent-dk);}
  .eyebrow::before{content:"";width:30px;height:2px;border-radius:2px;background:linear-gradient(90deg,var(--accent),var(--accent-2));}
  .hero h2{font-family:var(--display);font-weight:800;font-size:clamp(38px,5.4vw,58px);line-height:1.03;letter-spacing:-.03em;margin:16px 0 12px;}
  .lede{font-size:22px;color:var(--ink-soft);margin:0 0 22px;max-width:44ch;}
  .herometa{display:flex;align-items:center;flex-wrap:wrap;gap:10px 18px;padding-bottom:22px;border-bottom:1px solid var(--line);
    font:600 11.5px/1 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);}
  .herometa .d b{color:var(--ink-soft);font-weight:700;} .herometa .dotmark{width:5px;height:5px;border-radius:99px;background:var(--accent);}
  .top p{margin:22px 0;} .hero+p,.herometa+p{margin-top:26px;}
  .top code{font:.84em var(--mono);background:var(--tint);padding:.13em .42em;border-radius:5px;border:1px solid var(--line-soft);color:var(--accent-dk);}
  .top a{color:var(--accent-dk);}
  .top h3{font-family:var(--display);font-weight:700;font-size:23px;letter-spacing:-.015em;margin:42px 0 10px;}

  .keyconcept{position:relative;margin:38px 0;padding:26px 30px 26px 32px;border-radius:18px;overflow:hidden;
    background:linear-gradient(135deg,color-mix(in oklab,var(--accent),var(--surface) 88%),var(--surface));
    border:1px solid color-mix(in oklab,var(--accent),transparent 80%);box-shadow:0 22px 50px -34px rgba(var(--shadow),.4);}
  .keyconcept::after{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:linear-gradient(180deg,var(--accent-lt),var(--accent-2));}
  .keyconcept::before{content:"\201C";position:absolute;top:-20px;right:18px;font-family:var(--display);font-weight:800;font-size:130px;color:var(--accent);opacity:.1;}
  .keyconcept .label{font:700 11px/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--accent-dk);display:block;margin-bottom:11px;}
  .keyconcept p{font-family:var(--display);font-weight:500;font-size:21px;line-height:1.5;margin:0;position:relative;z-index:1;}

  .codeblock{margin:30px 0;border-radius:16px;overflow:hidden;box-shadow:0 26px 54px -30px rgba(10,25,60,.6);border:1px solid rgba(255,255,255,.05);}
  .codeblock__file{display:flex;align-items:center;gap:10px;padding:12px 18px;background:color-mix(in oklab,var(--code-bg),#fff 6%);
    border-bottom:1px solid rgba(255,255,255,.07);font:500 12px/1 var(--mono);color:#aeb9d0;}
  .codeblock__file::before{content:"";width:9px;height:9px;border-radius:99px;background:var(--accent);box-shadow:0 0 10px var(--accent);}
  .codeblock__file .dots{margin-left:auto;display:flex;gap:6px;} .codeblock__file .dots i{width:9px;height:9px;border-radius:99px;background:rgba(255,255,255,.12);}
  pre{margin:0;background:linear-gradient(180deg,var(--code-bg2),var(--code-bg));color:var(--code-fg);padding:20px 22px;overflow-x:auto;}
  .top pre code,.codeblock pre code,pre code{font:14px/1.72 var(--mono);background:none;border:0;padding:0;color:var(--code-fg);}
  .hljs{background:transparent;color:var(--code-fg);}

  .compare{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:30px 0;}
  .compare__side{background:var(--surface);border:1px solid var(--line);border-radius:16px;overflow:hidden;box-shadow:0 1px 2px rgba(var(--shadow),.05);}
  .compare__side.is-accent{border-color:color-mix(in oklab,var(--accent),transparent 55%);box-shadow:0 0 0 1px var(--accent-wash),0 16px 36px -26px rgba(var(--shadow),.45);}
  .compare__head{padding:10px 16px;background:var(--tint);border-bottom:1px solid var(--line);font:600 13px/1 var(--mono);color:var(--ink-soft);}
  .compare__side.is-accent .compare__head{color:var(--accent-dk);background:var(--accent-wash);}
  .compare__body{padding:4px 14px 12px;} .compare__body pre{border-radius:10px;margin:12px 0;}

  .callout{margin:30px 0;padding:17px 20px;border:1px solid var(--line);border-left:3px solid var(--done);border-radius:0 14px 14px 0;
    background:color-mix(in oklab,var(--done),var(--surface) 90%);}
  .callout .label{font:700 11px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--done);display:block;margin-bottom:7px;}
  .callout p{margin:0;}
  .callout.warning{border-left-color:#c9821f;background:color-mix(in oklab,#c9821f,var(--surface) 90%);} .callout.warning .label{color:#b0701a;}

  .exercise{margin:36px 0;padding:28px 30px;background:var(--surface);border:1px solid var(--line);border-radius:20px;
    box-shadow:0 36px 70px -44px rgba(var(--shadow),.4);}
  .exercise .tag,.exercise__tag,.quiz__tag{display:inline-block;font:700 11px/1 var(--mono);letter-spacing:.12em;text-transform:uppercase;color:#fff;
    padding:8px 14px;border-radius:99px;margin-bottom:15px;background:linear-gradient(135deg,var(--accent),var(--accent-2));box-shadow:0 8px 18px -9px var(--accent);}
  .exercise h4,.quiz h4{font-family:var(--display);font-weight:700;font-size:21px;margin:0 0 8px;} .exercise ol{margin:0;padding-left:1.2em;} .exercise li{margin:7px 0;}
  .quiz{margin:32px 0;padding:28px 30px;background:var(--surface);border:1px dashed var(--line);border-radius:20px;}
  .quiz__tag{background:linear-gradient(135deg,var(--ink-soft),var(--ink));}
  .quiz ol.options{list-style:none;padding:0;margin:14px 0 0;counter-reset:opt;}
  .quiz ol.options li{counter-increment:opt;position:relative;padding:12px 14px 12px 48px;border:1px solid var(--line);border-radius:12px;margin:8px 0;background:var(--bg);}
  .quiz ol.options li::before{content:counter(opt,upper-alpha);position:absolute;left:12px;top:50%;transform:translateY(-50%);width:25px;height:25px;border-radius:8px;
    background:var(--surface);border:1px solid var(--line);display:grid;place-items:center;font:600 12px/1 var(--mono);color:var(--ink-soft);}

  details.hint{margin:20px 0;border:1px solid var(--line);border-radius:12px;background:var(--surface);overflow:hidden;}
  details.hint>summary{cursor:pointer;list-style:none;padding:13px 18px;font:700 12px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;
    color:var(--accent-dk);display:flex;align-items:center;gap:9px;}
  details.hint>summary::-webkit-details-marker{display:none;}
  details.hint>summary::before{content:"▸";transition:transform .2s;color:var(--accent);} details.hint[open]>summary::before{transform:rotate(90deg);}
  details.hint .body{padding:2px 18px 16px;} details.hint .body p{margin:10px 0;}
"""

# JS comum: highlight, troca de tema, helper de copiar-pro-chat, live-reload.
JS = (
    "<script>hljs.highlightAll();</script>\n"
    "<script>\n"
    "function setTheme(t){const h=document.documentElement;if(t==='dark')h.dataset.theme='dark';"
    "else h.removeAttribute('data-theme');try{localStorage.setItem('sb-theme',t);}catch(e){}}\n"
    "function sbcopy(btn,txt){navigator.clipboard&&navigator.clipboard.writeText(txt);"
    "const s=btn.querySelector('small');const o=s.textContent;s.textContent='\\u2713 copiado \\u2014 cole no chat';"
    "s.classList.add('copied');setTimeout(()=>{s.textContent=o;s.classList.remove('copied');},1800);}\n"
    "</script>\n"
    "<script>let _lm=null;setInterval(async()=>{try{const r=await fetch(location.pathname,{method:'HEAD',cache:'no-store'});"
    "const lm=r.headers.get('Last-Modified');if(_lm&&lm&&lm!==_lm)location.reload();_lm=lm;}catch(e){}},1500);</script>"
)


def head(title_suffix=""):
    """Abertura de <head> ate antes do <style>, com fontes e init de tema."""
    return (
        '<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{title_suffix}</title>\n' + THEME_INIT + "\n" + FONTS
    )

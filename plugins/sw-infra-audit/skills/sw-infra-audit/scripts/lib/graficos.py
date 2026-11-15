"""Gráficos em SVG inline: sem JS e sem biblioteca, iguais na tela, no escuro e no PDF.

A cor vem só de classe (`gf-*`), e a classe lê os tokens `--g-*` dos dois `:root` do template: cor
literal aqui quebraria o modo escuro. O número vai sempre escrito ao lado, e cada marca tem `<title>`.
Paleta validada (claro #22659e/#b7791f/#b02a37, escuro #3f8fd0/#bf8a17/#cc3b4c).
"""
from lib.html_comum import SEM_DADO, _e

TOM = {"acc": "gf-acc", "ok": "gf-ok", "warn": "gf-warn", "crit": "gf-crit"}
ICONE = {"warn": "achado", "crit": "achado", "ok": "bom"}


def _limitar(pct):
    # nan-ok: o valor vira só largura no SVG; quem chama já passou por resposta numérica
    return max(0.0, min(100.0, float(pct)))


def _svg(partes, alto, titulo):
    return (f'<svg class="gf" width="100%" height="{alto}" role="img" aria-label="{_e(titulo)}">'
            f'<title>{_e(titulo)}</title>{"".join(partes)}</svg>')


def barra(pct, titulo, tom="acc", marca=None, alto=10, trilha=True):
    p = _limitar(pct)
    partes = [f'<rect class="gf-trk" x="0" y="4" width="100%" height="{alto}" rx="4"/>'] if trilha else []
    if p > 0:
        partes.append(f'<rect class="{TOM[tom]}" x="0" y="4" width="{p:.2f}%" height="{alto}" rx="4"/>')
    if marca is not None:
        # sem `translate(-1 0)`: um "-1" no HTML quebra o teste do disco estável (test_blocos.py)
        partes.append(f'<rect class="gf-lim" x="{_limitar(marca):.2f}%" y="0" width="2" height="{alto + 8}"/>')
    return _svg(partes, alto + 8, titulo)


def etiqueta(tom, texto):
    return (f'<span class="bl-tag-{tom}"><svg class="ic"><use href="#ic-{ICONE.get(tom, "ruim")}"/></svg>'
            f'{_e(texto)}</span>')


def medidor(valor, maximo, marca, rotulo, texto, sub="", acima="crit", marca_texto=None):
    """`valor` e `marca` na unidade de `maximo`. Acima da marca a cor é de status, com etiqueta."""
    sub_html = f'<span class="mt-s">{_e(sub)}</span>' if sub else ""
    cabeca = f'<span class="mt-l">{_e(rotulo)}{sub_html}</span>'
    if valor is None:
        return f'<div class="mt"><div class="mt-h">{cabeca}<b class="mt-v">{SEM_DADO}</b></div></div>'
    passou = valor > marca
    tom = acima if passou else "acc"
    pct, pct_marca = valor * 100 / maximo, marca * 100 / maximo
    legenda = marca_texto or f"limite {marca}"
    numero = f' bl-c-{acima}' if passou else ""
    estado = f'<span class="mt-st">{etiqueta(acima, "acima do limite")}</span>' if passou else ""
    return (f'<div class="mt"><div class="mt-h">{cabeca}<b class="mt-v{numero}">{_e(texto)}</b></div>'
            f'<div class="mt-b">{barra(pct, f"{rotulo}: {texto}, {legenda}", tom, pct_marca)}'
            f'<span class="mt-lim" style="left:{_limitar(pct_marca):.2f}%">{_e(legenda)}</span></div>'
            f'{estado}</div>')


def barras(itens, formato, titulo, limite=5):
    com = sorted((i for i in itens if i[1] is not None), key=lambda i: (-i[1], str(i[0])))
    ordem = com + [i for i in itens if i[1] is None]
    maior = com[0][1] if com and com[0][1] > 0 else 1
    linhas = []
    for rotulo, valor in ordem[:limite]:
        if valor is None:
            grafico, texto = '<span class="br-sd">sem dado</span>', '<span class="br-v bl-sd">sem dado</span>'
        else:
            escrito = formato(valor)
            grafico = barra(max(valor * 100 / maior, 1.2), f"{rotulo}: {escrito}", alto=14, trilha=False)
            texto = f'<span class="br-v">{_e(escrito)}</span>'
        linhas.append(f'<div class="br-r" role="listitem"><span class="br-l">{_e(rotulo)}</span>{grafico}{texto}</div>')
    resto = len(ordem) - limite
    mais = f'<p class="br-mais">e mais {resto}</p>' if resto > 0 else ""
    return f'<div class="br" role="list" aria-label="{_e(titulo)}">{"".join(linhas)}</div>{mais}'

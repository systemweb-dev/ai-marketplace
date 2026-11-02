import math

from lib.blocos import bloco
from lib.html_comum import inteiro, medido, nao_medido, painel, percentual, plural, tamanho

CIRCUNFERENCIA = 2 * math.pi * 30


def _anel(acerto):
    if acerto is None:
        cheio, texto, rotulo = "", '<text x="38" y="42" text-anchor="middle" class="bl-anum bl-anum-p">sem dado</text>', "acerto sem dado"
    else:
        arco = CIRCUNFERENCIA * min(max(acerto, 0), 100) / 100
        cheio = (f'<circle class="bl-anel-v" cx="38" cy="38" r="30" stroke-dasharray="{arco:.1f} '
                 f'{CIRCUNFERENCIA:.1f}" transform="rotate(-90 38 38)"/>')
        texto = f'<text x="38" y="43" text-anchor="middle" class="bl-anum">{percentual(acerto)}</text>'
        rotulo = f"{percentual(acerto)} de acerto"
    return (f'<svg class="bl-anel" viewBox="0 0 76 76" role="img" aria-label="{rotulo}">'
            f'<circle class="bl-anel-f" cx="38" cy="38" r="30"/>{cheio}{texto}</svg>')


def _evictions(n):
    if n is None:
        return f"Evicções: {medido(n)}"
    return "sem evicções" if n == 0 else f"{inteiro(n)} {'evicção' if n == 1 else 'evicções'}"


def _item(i):
    acerto = i.get("acerto")
    frase = "Acerto: " + medido(acerto) if acerto is None else f"{percentual(acerto)} das leituras encontradas no cache"
    return (f'<div class="bl-cache">{_anel(acerto)}<div><b>{medido(i.get("nome"))}</b><span>{frase}</span>'
            f'<div class="bl-med"><span>Memória</span><b>{medido(i.get("memoria"), tamanho)}</b></div>'
            f'<p class="bl-mini">{_evictions(i.get("evictions"))}</p></div></div>')


@bloco("cache")
def render(dados):
    itens = dados.get("itens")
    if not itens:
        return painel("Cache", "", nao_medido(dados.get("motivo", "sem fonte")))
    return painel("Cache", plural(len(itens), "medido", "medidos"), "".join(_item(i) for i in itens))

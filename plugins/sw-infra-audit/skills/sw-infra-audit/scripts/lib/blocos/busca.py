"""Coleções da busca vetorial (Qdrant): pontos em barra, e o status em ícone e rótulo."""
from lib import cartao, graficos
from lib.blocos import bloco
from lib.html_comum import _e, humano, nao_medido, painel, plural

# o que o Qdrant quer dizer com cada cor: verde pronto, amarelo otimizando, vermelho com erro
STATUS = {"green": ("ok", "Pronta"), "yellow": ("warn", "Otimizando"), "red": ("crit", "Com erro"),
          "grey": ("neutro", "Otimização pendente")}
COLECOES_MAX = 8


def _colecao(c, maior):
    tom, rotulo = STATUS.get(c.get("status"), ("neutro", "sem status"))
    pontos = c.get("pontos")
    titulo = f'{c.get("nome")}: {humano(pontos) if pontos is not None else "sem dado"} pontos'
    grafico = graficos.barra(pontos * 100 / maior if pontos else 0, titulo, alto=12, trilha=False)
    valor = f'{humano(pontos)} pontos' if pontos is not None else "sem dado"
    return (f'<div class="qd-r"><div class="qd-t"><b class="qd-n">{_e(c.get("nome"))}</b>'
            f'<span class="tec">status {_e(c.get("status") or "—")}</span>{graficos.etiqueta(tom, rotulo)}</div>'
            f'<div class="qd-g">{grafico}<span class="br-v">{_e(valor)}</span></div></div>')


def _item(i):
    problemas = "".join(cartao.cartao(p) for p in i.get("problemas") or [])
    cartoes = f'<div class="fxs">{problemas}</div>' if problemas else ""
    colecoes = sorted(i.get("colecoes") or [], key=lambda c: (-(c.get("pontos") or 0), str(c.get("nome"))))
    if not colecoes:
        corpo = nao_medido(i.get("motivo") or "nenhuma coleção respondeu")
    else:
        maior = max((c.get("pontos") or 0) for c in colecoes) or 1
        resto = len(colecoes) - COLECOES_MAX
        mais = f'<p class="br-mais">e mais {resto}</p>' if resto > 0 else ""
        corpo = f'<div class="qd">{"".join(_colecao(c, maior) for c in colecoes[:COLECOES_MAX])}</div>{mais}'
    return f'<div class="bl-db">{cartoes}<b>{_e(i.get("nome"))} · {_e(i.get("alvo"))}</b>{corpo}</div>'


@bloco("busca")
def render(dados):
    itens = dados.get("itens")
    if not itens:
        return ""
    colecoes = sum(len(i.get("colecoes") or []) for i in itens)
    return painel("Busca", plural(colecoes, "coleção", "coleções"), "".join(_item(i) for i in itens), cheio=True)

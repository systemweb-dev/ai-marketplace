from lib.blocos import bloco
from lib.html_comum import medido, nao_medido, painel, plural

TONS_DE_IMPACTO = {"alto": "crit", "baixo": "ok"}


def _linha(p):
    tom = TONS_DE_IMPACTO.get(str(p.get("impacto")).lower(), "warn")
    return (f'<div class="bl-sp"><div><b>{medido(p.get("cenario"))}</b></div><i class="bl-seta"></i>'
            f'<div class="bl-imp bl-imp-{tom}">{medido(p.get("consequencia"))}</div></div>')


@bloco("falhas")
def render(dados):
    itens = dados.get("itens")
    if not itens:
        return painel("Pontos únicos de falha", "", nao_medido(dados.get("motivo", "sem fonte")))
    return painel("Pontos únicos de falha", plural(len(itens), "apontado", "apontados"), "".join(_linha(p) for p in itens))

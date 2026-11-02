from importlib import import_module

from lib.html_comum import _e, medido, painel

BLOCOS = {}


def bloco(papel):
    def registrar(funcao):
        BLOCOS[papel] = funcao
        return funcao
    return registrar


def render_bloco(papel, dados):
    funcao = BLOCOS.get(papel)
    if funcao:
        return funcao(dados)
    linhas = "".join(f"<tr><td>{_e(k)}</td><td>{medido(v)}</td></tr>" for k, v in sorted(dados.items()))
    return painel(papel.capitalize(), "dados coletados", f'<table class="bl-tb">{linhas}</table>')


for _modulo in ("fila", "entrada", "banco", "cache", "maquinas", "consumo", "falhas", "urls"):
    import_module(f"lib.blocos.{_modulo}")

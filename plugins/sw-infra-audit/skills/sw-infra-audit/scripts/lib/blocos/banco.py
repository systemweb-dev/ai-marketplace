from lib.blocos import bloco
from lib.html_comum import inteiro, medido, nao_medido, painel, plural, tamanho


def _conexoes(n):
    return f"Conexões: {medido(n)}" if n is None else f"{inteiro(n)} {'conexão' if n == 1 else 'conexões'}"


@bloco("banco")
def render(dados):
    itens = dados.get("itens")
    if not itens:
        return painel("Bancos de dados", "", nao_medido(dados.get("motivo", "sem fonte")))
    corpo = "".join(f'<div class="bl-db"><b>{medido(i.get("nome"))}</b><span>{_conexoes(i.get("conexoes"))}</span>'
                    f'<dl><dt>Tamanho</dt><dd>{medido(i.get("tamanho"), tamanho)}</dd></dl></div>'
                    for i in itens)
    return painel("Bancos de dados", plural(len(itens), "medido", "medidos"), corpo)

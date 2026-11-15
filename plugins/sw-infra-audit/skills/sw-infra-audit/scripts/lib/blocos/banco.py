from lib import cartao, graficos
from lib.blocos import bloco
from lib.html_comum import inteiro, medido, nao_medido, painel, percentual, plural, tamanho
from lib.limites_produto import LIMITE_DE_CONEXOES


def _conexoes(n):
    return f"Conexões: {medido(n)}" if n is None else f"{inteiro(n)} {'conexão' if n == 1 else 'conexões'}"


def _dias(n):
    return plural(round(n), "dia", "dias")


def _fatos(i):
    """Cada campo só quando existe: banco do cluster não ganha linha de "sem dado" que nunca teria."""
    linhas = [f'<dt>Tamanho</dt><dd>{medido(i.get("tamanho"), tamanho)}</dd>']
    if i.get("lentas") is not None:
        linhas.append(f'<dt>Consultas lentas</dt><dd>{inteiro(i["lentas"])}</dd>')
    if i.get("binlog"):
        total = sum(b.get("bytes") or 0 for b in i["binlog"])
        linhas.append(f'<dt>Binlog</dt><dd>{plural(len(i["binlog"]), "arquivo", "arquivos")} · {tamanho(total)}</dd>')
    return f'<dl>{"".join(linhas)}</dl>'


def _graficos(i):
    partes = []
    if i.get("uso") is not None:
        partes.append(graficos.medidor(i["uso"], 100, LIMITE_DE_CONEXOES, "Conexões em uso",
                                       percentual(i["uso"]), sub="do máximo que o banco aceita",
                                       acima="warn", marca_texto=f"alerta em {LIMITE_DE_CONEXOES}%"))
    if i.get("backup") is not None:
        maximo = max(i["backup_max"] * 2, i["backup"] + 1)
        partes.append(graficos.medidor(i["backup"], maximo, i["backup_max"], "Idade do backup",
                                       _dias(i["backup"]), sub="backup mais novo da pasta",
                                       acima="crit", marca_texto=f'limite {_dias(i["backup_max"])}'))
    if i.get("por_banco"):
        partes.append('<h5 class="sub-h">Tamanho por banco</h5>' + graficos.barras(
            [(b.get("nome"), b.get("bytes")) for b in i["por_banco"]], tamanho,
            f'Tamanho por banco em {i.get("nome")}'))
    return "".join(partes)


def _item(i):
    problemas = "".join(cartao.cartao(p) for p in i.get("problemas") or [])
    cartoes = f'<div class="fxs">{problemas}</div>' if problemas else ""
    return (f'<div class="bl-db">{cartoes}<b>{medido(i.get("nome"))}</b><span>{_conexoes(i.get("conexoes"))}</span>'
            f'{_fatos(i)}{_graficos(i)}</div>')


@bloco("banco")
def render(dados):
    itens = dados.get("itens")
    if not itens:
        return painel("Bancos de dados", "", nao_medido(dados.get("motivo", "sem fonte")))
    corpo = "".join(_item(i) for i in itens)
    if any(i.get(k) for i in itens for k in ("uso", "backup", "por_banco", "problemas")):
        # com gráfico e cartão o painel vai à largura toda, e os bancos ficam lado a lado
        return painel("Bancos de dados", plural(len(itens), "medido", "medidos"),
                      f'<div class="bl-dbs">{corpo}</div>', cheio=True)
    return painel("Bancos de dados", plural(len(itens), "medido", "medidos"), corpo)

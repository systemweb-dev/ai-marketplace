import math

from lib.blocos import bloco
from lib.html_comum import _e, inteiro, medido, nao_medido, painel, percentual, plural
COLUNAS_DOS_NOS = (("Nó", "bl-e"), ("Estado", "bl-e"), ("Tarefas", "bl-d"), ("Falhadas", "bl-d"),
                   ("Saídas", "bl-e"), ("Capacidade", "bl-e"), ("Engine", "bl-e"))


def _tom(uso):
    return "crit" if uso >= 85 else "warn" if uso >= 70 else "ok"


def _medida(rotulo, uso):
    if uso is None:
        return f'<div class="bl-med"><span>{rotulo}</span><b>{medido(uso)}</b></div>'
    tom = _tom(uso)
    largura = min(max(uso, 0), 100)
    return (f'<div class="bl-med"><span>{rotulo}</span><b class="bl-c-{tom}">{percentual(uso)}</b>'
            f'<span class="bl-bar"><i class="bl-fl-{tom}" style="width:{largura:.0f}%"></i></span></div>')


def _previsao(dias):
    """Negativo ou infinito diz que o disco não está enchendo: sem data de fim, é "estável"."""
    if dias is None or math.isnan(dias):
        texto = medido(None)
    elif dias < 0 or math.isinf(dias):
        texto = "estável"
    elif dias < 1:
        texto = "enche em menos de 1 dia"
    else:
        texto = f'enche em {plural(round(dias), "dia", "dias")}'
    return f'<div class="bl-med"><span>Previsão do disco</span><b>{texto}</b></div>'


def _cartao(i):
    return (f'<article class="bl-maq"><header><b>{medido(i.get("nome"))}</b></header>'
            f'{_medida("CPU", i.get("cpu"))}{_medida("Memória", i.get("memoria"))}'
            f'{_medida("Disco", i.get("disco"))}{_previsao(i.get("dias"))}</article>')


def _linha_do_no(n):
    fora = str(n.get("estado") or "").lower() != "ready"
    estado = f'<b class="bl-c-crit">{medido(n.get("estado"))}</b>' if fora else medido(n.get("estado"))
    falhas = n.get("falhadas")
    falhadas = f'<b class="bl-c-warn">{inteiro(falhas)}</b>' if falhas else medido(falhas, inteiro)
    lider = " · líder" if n.get("lider") else ""
    return (f'<tr><td class="bl-e"><b>{medido(n.get("nome"))}</b>{lider}</td><td class="bl-e">{estado}</td>'
            f'<td class="bl-d">{medido(n.get("tarefas"), inteiro)}</td><td class="bl-d">{falhadas}</td>'
            f'<td class="bl-e">{_e(n.get("saidas") or "—")}</td><td class="bl-e">{_e(n.get("capacidade") or "—")}</td>'
            f'<td class="bl-e">{medido(n.get("engine"))}</td></tr>')


def _resumo_dos_nos(dados):
    """Papel do cluster, não medida da máquina: existe mesmo sem exporter."""
    nos = dados.get("nos") or []
    tabela = ""
    if nos:
        titulos = "".join(f'<th class="{classe}">{t}</th>' for t, classe in COLUNAS_DOS_NOS)
        tabela = (f'<table class="bl-tb"><thead><tr>{titulos}</tr></thead>'
                  f'<tbody>{"".join(_linha_do_no(n) for n in nos)}</tbody></table>')
    return tabela + "".join(f'<p class="bl-nocap">{_e(linha)}</p>' for linha in dados.get("capacidade") or [])


@bloco("maquinas")
def render(dados):
    itens = dados.get("itens")
    nos = _resumo_dos_nos(dados)
    if not itens:
        resumo = plural(len(dados.get("nos") or []), "nó", "nós") if dados.get("nos") else ""
        return painel("Máquinas", resumo, nao_medido(dados.get("motivo", "sem fonte")) + nos, cheio=True)
    cheios = sum(1 for i in itens if i.get("disco") is not None and i["disco"] > 85)
    medidas = sum(1 for i in itens if any(i.get(k) is not None for k in ("cpu", "memoria", "disco", "dias")))
    resumo = plural(medidas, "medida", "medidas") + (f" · {cheios} com disco acima de 85%" if cheios else "")
    return painel("Máquinas", resumo, f'<div class="bl-maqs">{"".join(_cartao(i) for i in itens)}</div>{nos}', cheio=True)

"""Um bloco para os servidores host: o índice de problemas no topo, e uma área por servidor com os
grupos "Problemas e o que fazer", "Estado dos serviços" e "Informativo", nesta ordem.

A máquina do servidor (disco, memória, carga) fica no bloco Máquinas, e o banco e a busca nos blocos
deles: aqui entram só os problemas de quem não tem bloco próprio.
"""
import re

from lib import cartao, graficos
from lib.blocos import bloco
from lib.html_comum import SEM_DADO, _e, inteiro, medido, painel, plural, tamanho
from lib.limites_produto import LIMITE_DE_REINICIOS


def _ic(nome, classe="ic"):
    return f'<svg class="{classe}"><use href="#ic-{nome}"/></svg>'


def _grupo(titulo, corpo):
    return f'<div class="grp"><h5>{_e(titulo)}</h5>{corpo}</div>'


def _dias(d):
    return "menos de 1 dia" if d < 1 else plural(round(d), "dia", "dias")


def _estado(sv):
    if sv["ausente"]:
        return f'<span class="bl-tag-crit">{_ic("ruim")}não encontrado</span>'
    if sv["ativo"] is None:
        return f'<span class="bl-tag-neutro">{_ic("ruim")}não medido</span>'
    if sv["ativo"] == "ativo":
        return f'<span class="st-ok">{_ic("bom")}ativo</span>'
    return f'<span class="bl-tag-crit">{_ic("ruim")}{_e(sv["ativo"])}</span>'


def _reinicios(n):
    if n is None:
        return SEM_DADO
    if n >= LIMITE_DE_REINICIOS:
        return f'<span class="rei-alto bl-c-warn">{_ic("achado")}{inteiro(n)}</span>'
    return inteiro(n)


def _servico(sv):
    reinicia = sv["reinicios"] is not None and sv["reinicios"] >= LIMITE_DE_REINICIOS
    parado = sv["ausente"] or sv["ativo"] not in (None, "ativo")
    classe = "svc alerta" if reinicia or parado else "svc"
    como = " · ".join(str(x) for x in (sv.get("produto"), sv.get("papel")) if x)
    return (f'<div class="{classe}"><div class="svc-t"><span><b>{_e(sv["nome"])}</b>'
            f'<span class="tec">{_e(como)}</span></span>{_estado(sv)}</div>'
            f'<dl class="fatos"><div><dt>No ar há</dt><dd>{medido(sv["desde"], _dias)}</dd></div>'
            f'<div><dt>Reinícios</dt><dd>{_reinicios(sv["reinicios"])}</dd></div>'
            f'<div><dt>Memória</dt><dd>{medido(sv["memoria"], tamanho)}</dd></div></dl></div>')


def _memoria(s):
    if not any(sv["memoria"] is not None for sv in s["servicos"]):
        return ""
    itens = [(sv["nome"], sv["memoria"]) for sv in s["servicos"]]
    return ('<h5 class="sub-h">Memória por serviço</h5>'
            + graficos.barras(itens, tamanho, f'Memória por serviço em {s["nome"]}', limite=8))


def _informativo(s):
    itens = [(f'Descoberto e não declarado: {d["produto"]}',
              f'Roda em <code>{_e(d["origem"])}</code> e o <code>alvos.toml</code> não o declara. Para medir, '
              f'rode <code>configurar.py descobrir --alvo {_e(s["nome"])}</code>.') for d in s["descobertos"]]
    itens += [("Não medido", f'{_e(m)}. Confira o acesso ao servidor e rode a auditoria de novo; sem a leitura, '
                             'o relatório não afirma que está tudo bem.') for m in s["nao_medido"]]
    return "".join(f'<div class="inf">{_ic("ruim", "ic inf-i")}<div><p class="inf-p">{_e(t)}</p>'
                   f'<p class="inf-f">{texto}</p></div></div>' for t, texto in itens)


def _area(s):
    meta = [("Sistema", " · ".join(x for x in (s["sistema"], s["kernel"]) if x)), ("Acesso", s["acesso"])]
    linhas = "".join(f"<dt>{r}</dt><dd>{_e(v)}</dd>" for r, v in meta if v)
    ident = "srv-" + re.sub(r"[^a-z0-9]+", "-", str(s["nome"]).lower()).strip("-")
    grupos = ""
    if s["problemas"]:
        grupos += _grupo("Problemas e o que fazer",
                         '<div class="fxs">' + "".join(cartao.cartao(a) for a in s["problemas"]) + "</div>")
    if s["servicos"]:
        grupos += _grupo("Estado dos serviços",
                         f'<div class="svcs">{"".join(_servico(sv) for sv in s["servicos"])}</div>{_memoria(s)}')
    informativo = _informativo(s)
    if informativo:
        grupos += _grupo("Informativo", f'<div class="infs">{informativo}</div>')
    return (f'<div class="srv"><header class="srv-h"><h4 id="{ident}">{_e(s["nome"])}</h4>'
            f'<dl class="srv-meta">{linhas}</dl></header>{grupos}</div>')


@bloco("servidores")
def render(dados):
    itens = dados.get("itens")
    if not itens:
        return ""
    todos = [a for s in itens for a in s["todos"]]
    if todos:
        topo = (f'<div class="sv-topo"><h4>{plural(len(todos), "problema", "problemas")} nos servidores</h4>'
                f'{cartao.indice(todos)}</div>')
    else:
        topo = '<p class="sv-topo bl-mini">Nenhum problema nos servidores.</p>'
    servicos = sum(len(s["servicos"]) for s in itens)
    resumo = f'{plural(len(itens), "servidor", "servidores")} · {plural(servicos, "serviço", "serviços")}'
    return painel("Serviços dos servidores", resumo, topo + "".join(_area(s) for s in itens), cheio=True)

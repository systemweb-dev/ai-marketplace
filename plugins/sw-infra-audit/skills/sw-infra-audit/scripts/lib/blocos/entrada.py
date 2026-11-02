from lib.blocos import bloco
from lib.html_comum import _e, humano, inteiro, medido, nao_medido, painel, plural
from lib.perguntas import PERGUNTAS

MAXIMO_DE_SERVICOS = 15
FAIXA_DE_LATENCIA = PERGUNTAS["entrada.latencia"]["faixa"]
LEGENDAS = {"ok": "ok", "warn": "4xx", "crit": "5xx"}


def _classe_do_status(item):
    return {"4": "warn", "5": "crit"}.get(str(item.get("chave"))[:1], "ok")


def _barra_de_status(status):
    somas = {"ok": 0, "warn": 0, "crit": 0}
    for item in status or []:
        somas[_classe_do_status(item)] += item.get("valor") or 0
    total = sum(somas.values())
    if not total:
        return f'<div class="bl-sl"><span>Status: {medido(None)}</span></div>'
    pedacos, legenda = "", ""
    for tom, soma in somas.items():
        parte = 100 * soma / total
        if soma:
            pedacos += f'<i class="bl-fl-{tom}" style="flex:{parte:.1f}"></i>'
        texto = f"{parte:.1f}".replace(".", ",")
        legenda += f'<span><i class="bl-pt bl-fl-{tom}"></i>{texto}% {LEGENDAS[tom]}</span>'
    return f'<div class="bl-stk">{pedacos}</div><div class="bl-sl">{legenda}</div>'


def _ms(n):
    return f"{inteiro(n)} ms"


def _latencia(ms):
    if ms is None:
        return medido(ms)
    tom = ("ok" if ms <= FAIXA_DE_LATENCIA["bom_ate"]
           else "crit" if ms >= FAIXA_DE_LATENCIA["ruim_a_partir"] else "warn")
    return f'<b class="bl-c-{tom}">{_ms(ms)}</b>'


def _acessos(n):
    if n is None:
        return f"Acessos: {medido(n)}"
    if n == 1:
        return "1 acesso"
    texto = humano(n)
    return f"{_e(texto)} {'acessos' if texto[-1].isdigit() else 'de acessos'}"


def _linha(i):
    cobre = f'<span>{_e(i["cobre"])}</span>' if i.get("cobre") else ""
    return (f'<div class="bl-site"><div class="bl-sn"><b>{medido(i.get("nome"))}</b>'
            f'<span>{_acessos(i.get("volume"))}</span>{cobre}</div>'
            f'<div class="bl-sb">{_barra_de_status(i.get("status"))}</div>'
            f'<div class="bl-st">{_latencia(i.get("latencia"))}<span>tempo de resposta</span></div></div>')


def selecionar(servicos, maximo=MAXIMO_DE_SERVICOS):
    """Os maiores em acessos, somando quem teve erro 5xx: erro raro não some da lista."""
    ordem = sorted(servicos, key=lambda s: (-(s.get("acessos") or 0), str(s.get("nome") or "")))
    return ordem[:maximo] + [s for s in ordem[maximo:] if s.get("erros")]


def _erros(servico):
    """Série de 5xx só existe depois do primeiro erro: rota medida sem ela não teve nenhum."""
    falhou = "erros" in (servico.get("nao_respondeu") or [])
    if servico.get("erros") is None and servico.get("acessos") is not None and not falhou:
        return "nenhum"
    return medido(servico.get("erros"), inteiro)


def _servicos(itens, maximo=MAXIMO_DE_SERVICOS):
    servicos = [s for i in itens for s in i.get("servicos") or []]
    if not servicos:
        return ""
    linhas = "".join(f'<tr><td class="bl-e"><b>{medido(s.get("nome"))}</b></td>'
                     f'<td class="bl-d">{medido(s.get("acessos"), humano)}</td>'
                     f'<td class="bl-d">{_erros(s)}</td>'
                     f'<td class="bl-d">{medido(s.get("resposta"), _ms)}</td></tr>' for s in selecionar(servicos, maximo))
    return ('<table class="bl-tb"><colgroup><col style="width:46%"><col style="width:18%"><col style="width:18%">'
            '<col style="width:18%"></colgroup><thead><tr><th class="bl-e">Serviço</th><th class="bl-d">Acessos</th>'
            f'<th class="bl-d">Erros 5xx</th><th class="bl-d">Resposta</th></tr></thead><tbody>{linhas}</tbody></table>')


@bloco("entrada")
def render(dados):
    itens = dados.get("itens")
    if not itens:
        return painel("Serviços web", "", nao_medido(dados.get("motivo", "sem fonte")), cheio=True)
    corpo = "".join(_linha(i) for i in itens) + _servicos(itens, dados.get("top") or MAXIMO_DE_SERVICOS)
    com_dominio = any(s.get("site") for i in itens for s in i.get("servicos") or [])
    titulo = "Sites" if com_dominio else "Serviços web"
    return painel(titulo, plural(len(itens), "medido", "medidos"), corpo, cheio=True)

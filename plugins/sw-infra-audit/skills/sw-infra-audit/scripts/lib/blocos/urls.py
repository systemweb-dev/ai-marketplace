from lib.blocos import bloco
from lib.blocos.entrada import _latencia
from lib.html_comum import _e, humano, inteiro, nao_medido, painel, plural
from lib.orcamento_paginas import SEM_CORTE

LIMITE_DA_JANELA = 5000


def _pct(n):
    tom = "crit" if n else "ok"
    return f'<span class="bl-c-{tom}">{_e(f"{n:.1f}".replace(".", ","))}%</span>'


def _tabela(colunas, linhas):
    larguras = "".join(f'<col style="width:{w}%">' for _, w in colunas)
    titulos = "".join(f'<th class="{"bl-e" if i == 0 else "bl-d"}">{_e(t)}</th>' for i, (t, _) in enumerate(colunas))
    return (f'<table class="bl-tb"><colgroup>{larguras}</colgroup><thead><tr>{titulos}</tr></thead>'
            f'<tbody>{linhas}</tbody></table>')


def _geral(itens):
    linhas = "".join(f'<tr class="bl-url-g"><td class="bl-e"><b>{_e(i["nome"])}</b></td>'
                     f'<td class="bl-d">{_e(humano(i["acessos"]))}</td><td class="bl-d">{_pct(i["pct_5xx"])}</td>'
                     f'<td class="bl-d">{_latencia(i["p95_ms"])}</td></tr>' for i in itens)
    return _tabela((("URL", 58), ("Acessos", 14), ("5xx", 14), ("p95", 14)), linhas)


def _cartao(site, por_site):
    linhas = "".join(f'<div class="bl-url-l"><span>{_e(i["caminho"])}</span><b>{_e(humano(i["acessos"]))}</b></div>'
                     for i in site["urls"][:por_site])
    return (f'<div class="bl-url"><b>{_e(site["site"])}</b><span>{_e(plural(site["acessos"], "acesso", "acessos"))}'
            f'</span>{linhas}</div>')


def _erros(itens):
    if not itens:
        return '<p class="bl-mini bl-url-n">Nenhuma URL com erro 5xx nas linhas lidas.</p>'
    linhas = "".join(f'<tr class="bl-url-e"><td class="bl-e">{_e(i["nome"])}</td>'
                     f'<td class="bl-d">{_e(inteiro(i["erros"]))}</td><td class="bl-d">{_pct(i["pct_5xx"])}</td></tr>'
                     for i in itens)
    return _tabela((("URL", 60), ("5xx", 20), ("% 5xx", 20)), linhas)


def _lentas(itens):
    linhas = "".join(f'<tr class="bl-url-s"><td class="bl-e">{_e(i["nome"])}</td>'
                     f'<td class="bl-d">{_e(humano(i["acessos"]))}</td><td class="bl-d">{_latencia(i["p95_ms"])}</td></tr>'
                     for i in itens)
    return _tabela((("URL", 60), ("Acessos", 20), ("p95", 20)), linhas)


def _amostra(janelas):
    """Devolve (resumo do cabeçalho, nota). Só diz "amostra" quando não cobriu tudo."""
    if not any(j["amostra"] for j in janelas):
        return f"últimas {max(j['total'] for j in janelas)} horas", ""
    total = sum(j["total"] for j in janelas)
    cobertas = sum(len(j["cobertas"]) for j in janelas)
    no_limite = sum(j["amostradas"] for j in janelas)
    falhas = sorted({f for j in janelas for f in j.get("falhas") or []})
    partes = [f"Amostra: {cobertas} de {total} janelas de 1 hora lidas"]
    if no_limite:
        partes.append(f"{plural(no_limite, 'janela bateu', 'janelas bateram')} no limite de "
                      f"{inteiro(LIMITE_DA_JANELA)} linhas")
    if falhas:
        partes.append("; ".join(falhas))
    return f"amostra · {cobertas} de {total} janelas", f'<p class="bl-mini bl-url-n">{_e("; ".join(partes))}.</p>'


@bloco("urls")
def render(dados):
    if not dados.get("geral"):
        return painel("URLs mais acessadas", "", nao_medido(dados.get("motivo", "sem fonte")), cheio=True)
    limites = {**SEM_CORTE, **(dados.get("limites") or {})}
    resumo, nota = _amostra(dados["janelas"])
    cartoes = "".join(_cartao(s, limites["urls_por_site"]) for s in dados["sites"][:limites["urls_sites"]])
    destaques = limites["urls_destaques"]
    faltas = "".join(f'<p class="bl-mini bl-url-n">Não medido em {_e(f["alvo"])}: {_e(f["motivo"])}.</p>'
                     for f in dados.get("faltas") or [])
    geral = _geral(dados["geral"][:limites["urls_geral"]]) + nota + faltas
    corpo = (f'<div class="bl-urls">{cartoes}</div>'
             + '<div class="bl-url-par"><div><h4 class="bl-url-t">URLs com mais erros</h4>'
             + _erros(dados["erros"][:destaques])
             + '</div><div><h4 class="bl-url-t">URLs mais lentas</h4>'
             + _lentas(dados["lentas"][:destaques]) + "</div></div>"
             + '<p class="bl-mini bl-url-n">Só o caminho agregado: identificadores viram :id e tokens viram '
             ':token. Erros e lentidão olham as 50 URLs mais acessadas de cada site.</p>')
    return (painel("URLs mais acessadas", resumo, geral, cheio=True)
            + painel("URLs por site", resumo, corpo, cheio=True))

"""O indice e as ancoras sao duas fontes para a mesma verdade.

Antes as secoes eram escritas a mao no template e o sumario era um registro a parte: se
alguem acrescentava uma secao no HTML e esquecia do registro, o sumario nao a listava — e
o leitor concluia que ela nao existia. Agora as secoes sao GERADAS, entao o registro
duplicado deixou de existir e a trava mudou de lugar: o que pode divergir e o link e o
destino.

Ancora morta nao quebra nada visivelmente — no PDF o clique simplesmente nao leva a lugar
nenhum. Esta trava e o que faz quebrar.
"""
import json
import re

import build_report


def _relatorio():
    """O mesmo esqueleto minimo dos outros testes de relatorio, aqui sem importar o
    modulo vizinho: teste que depende de outro arquivo de teste quebra quando aquele
    e renomeado, e o motivo da quebra nao tem nada a ver com o que se quer provar."""
    return {
        "schema_version": 3, "generated_at": "2026-09-19T10:00:00Z",
        "alvos": [{"nome": "cluster", "tipo": "docker", "onde": "context: ctx",
                   "saude": "🟡", "dimensoes": {"operacao": {"services_up": 1,
                                                             "services_total": 2}},
                   "fatos": {}, "analise": "", "nao_coletado": [],
                   "achados": [{"regra": "spof", "objeto": "proxy", "severidade": "high",
                                "detalhe": "1 réplica", "alvo": "cluster"},
                               {"regra": "cobertura", "objeto": "api", "severidade": "medium",
                                "detalhe": "sem healthcheck", "alvo": "cluster"},
                               {"regra": "higiene", "objeto": "app", "severidade": "low",
                                "detalhe": "sem limite", "alvo": "cluster"}]}],
        "inventario": [{"nome": "cluster", "tipo": "docker", "onde": "context: ctx",
                        "saude": "🟡"}],
        "aceites": [], "historico": None, "resumo": "", "fortes": [], "fracos": [],
        "recomendacoes": []}


def _pagina():
    return build_report.render_html_v3(_relatorio())


def _links(html):
    """Os links de navegacao. `#ic-*` sao referencias ao sprite de icones, nao navegacao."""
    return {a for a in re.findall(r'href="#([a-zA-Z0-9_-]+)"', html) if not a.startswith("ic-")}


def _ancoras(html):
    return {i for i in re.findall(r'id="([a-zA-Z0-9_-]+)"', html) if not i.startswith("ic-")}


def test_todo_link_do_indice_tem_destino():
    """No PDF, ancora morta e um clique que nao leva a lugar nenhum."""
    html = _pagina()
    orfaos = _links(html) - _ancoras(html)
    assert not orfaos, f"link sem destino no relatório: {sorted(orfaos)}"


def test_o_indice_aponta_para_as_tres_faixas():
    """O indice E o sumario deste relatorio: ele promete as tres faixas de acao."""
    assert _links(_pagina()) >= {"faixa-1", "faixa-2", "faixa-3"}


def test_nenhuma_ancora_repetida():
    """Dois `id` iguais fazem o link levar sempre ao primeiro — e o segundo fica inalcancavel."""
    html = _pagina()
    todos = [i for i in re.findall(r'id="([a-zA-Z0-9_-]+)"', html) if not i.startswith("ic-")]
    repetidos = {i for i in todos if todos.count(i) > 1}
    assert not repetidos, f"âncora repetida: {sorted(repetidos)}"


def test_o_indice_nao_promete_numero_de_pagina():
    """Numero de pagina exigiria uma segunda passada dependente de ferramenta externa —
    saida diferente por maquina, e la se vai o determinismo."""
    assert "pág." not in _pagina()


def test_faixa_sem_achado_aparece_no_indice_mas_sem_link():
    """O bug que esta trava pegou: o indice listava "Programar" com link mesmo quando
    nao havia achado medio nenhum, e a faixa nem chegava a ser desenhada."""
    dados = _relatorio()
    dados["alvos"][0]["achados"] = [a for a in dados["alvos"][0]["achados"]
                                    if a["severidade"] != "medium"]
    html = build_report.render_html_v3(dados)

    assert "Programar" in html, "a faixa continua anunciada — zero achado medio e informacao"
    assert "faixa-2" not in _links(html), "sem secao, sem link"

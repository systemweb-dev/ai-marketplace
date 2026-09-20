# tests/test_extracao_declaracao.py
"""A declaração é validada ANTES de olhar o dado.

A primeira versão só reclamava quando havia item para extrair: catálogo quebrado passava verde
enquanto a fila estivesse vazia e explodia no dia em que existisse uma fila. E erro de escrita
no TOML não levantava nada — produzia número errado com cara de certo.

Estes testes cobrem o que o revisor do batch mostrou: o campo cru que ordena como texto, o
`ordem` inválido que inverte o ranking, o `limite = 0` que vira "sem limite", o empate total que
herda a ordem da API e o NaN que aborta a gravação do relatório.
"""
import json
import math

import pytest

from lib.extracao import ExtracaoInvalida, extrair, validar_declaracao

TRES = {"items": [{"name": "pedidos", "n": "9"}, {"name": "emails", "n": "42"},
                  {"name": "morta", "n": "900"}]}


def _decl(**extra):
    return dict({"lista": "/items", "campos": {"nome": "/name", "n": "/n"},
                 "transformar": {"n": "inteiro"}, "ordenar_por": "n", "ordem": "desc",
                 "desempate": "nome"}, **extra)


# --- o typo que produzia ranking errado ---

def test_transformar_que_nao_casa_com_campos_e_recusado():
    """Com `transformar = {prontass = ...}`, o campo ficava CRU e a ordenação virava
    lexicográfica: "9" > "42" > "900", e o "top 2 filas com mais mensagens" entregava a fila de
    9 no lugar da de 42. Sem exceção, sem sem_dados — resposta errada com cara de certa."""
    with pytest.raises(ExtracaoInvalida, match="transformar"):
        validar_declaracao(_decl(transformar={"prontass": "inteiro"}))


def test_o_ranking_certo_sai_quando_a_declaracao_esta_certa():
    itens = extrair(TRES, _decl(limite=2))

    assert [i["nome"] for i in itens] == ["morta", "emails"]


# --- ordem ---

@pytest.mark.parametrize("ordem", ["descending", "DESC", "decrescente", ""])
def test_ordem_invalida_e_recusada(ordem):
    """Qualquer string diferente de "desc" virava crescente: "as 5 filas com mais mensagens"
    mostrava as 5 mais vazias."""
    with pytest.raises(ExtracaoInvalida, match="ordem"):
        validar_declaracao(_decl(ordem=ordem))


def test_ordem_ausente_continua_sendo_desc():
    declarada = _decl()
    del declarada["ordem"]

    assert [i["nome"] for i in extrair(TRES, declarada)] == ["morta", "emails", "pedidos"]


# --- ordenar_por ---

def test_ordenar_por_campo_que_nao_existe_e_recusado():
    """Todos caíam em `ausentes` e a lista saía na ordem da API — apresentada com a legenda
    "os maiores"."""
    with pytest.raises(ExtracaoInvalida, match="ordenar_por"):
        validar_declaracao(_decl(ordenar_por="inexistente"))


def test_ordenar_por_pode_apontar_para_uma_derivacao():
    declarada = {"lista": "/items", "campos": {"nome": "/name"},
                 "derivar": {"dobro": {"tipo": "soma", "parcelas": ["/n", "/n"]}},
                 "ordenar_por": "dobro", "ordem": "desc", "desempate": "nome"}

    assert validar_declaracao(declarada) is None


def test_ordenar_por_exige_desempate():
    """Sem desempate, empate de valor herda a ordem da resposta da API.

    O assert é na MENSAGEM, e não só no tipo da exceção: sem a guarda própria, o `desempate`
    ausente cai na checagem de "campo desconhecido" da linha seguinte e levanta uma exceção que
    também tem a palavra "desempate" — o teste passava pelo motivo errado e a mutação
    sobrevivia. Quem escreve o TOML precisa ler *por que* desempate é obrigatório, não
    "desempate `None` não é um campo".
    """
    declarada = _decl()
    del declarada["desempate"]

    with pytest.raises(ExtracaoInvalida) as erro:
        validar_declaracao(declarada)

    assert "ordem da resposta" in str(erro.value)


def test_desempate_que_nao_existe_e_recusado():
    with pytest.raises(ExtracaoInvalida, match="desempate"):
        validar_declaracao(_decl(desempate="inexistente"))


# --- limite ---

def test_limite_zero_corta_tudo_em_vez_de_virar_sem_limite():
    """O mesmo alçapão do `or` que já mordeu esta skill antes: num módulo cuja tese é "0 não é
    ausência", `if limite` tratava 0 como ausência."""
    assert extrair(TRES, _decl(limite=0)) == []


def test_limite_negativo_e_recusado():
    with pytest.raises(ExtracaoInvalida, match="limite"):
        validar_declaracao(_decl(limite=-1))


def test_limite_que_nao_e_inteiro_e_recusado():
    with pytest.raises(ExtracaoInvalida, match="limite"):
        validar_declaracao(_decl(limite="2"))


# --- empate total ---

def test_empate_total_nao_herda_a_ordem_da_api():
    """`/api/queues` lista filas de TODOS os vhosts, e o mesmo nome em vhosts diferentes é
    comum: valor igual e desempate igual. Sem chave total, `limite: 1` escolheria uma fila
    diferente a cada rodada e o diff acusaria mudança onde nada mudou."""
    ordem_a = {"items": [{"name": "jobs", "vhost": "/a", "n": 10},
                         {"name": "jobs", "vhost": "/b", "n": 10}]}
    ordem_b = {"items": [{"name": "jobs", "vhost": "/b", "n": 10},
                         {"name": "jobs", "vhost": "/a", "n": 10}]}
    declarada = {"lista": "/items", "campos": {"nome": "/name", "vhost": "/vhost", "n": "/n"},
                 "ordenar_por": "n", "ordem": "desc", "desempate": "nome", "limite": 1}

    assert extrair(ordem_a, declarada) == extrair(ordem_b, declarada)


# --- NaN que abortava o relatório ---

def test_nan_em_campo_sem_transformar_nao_chega_ao_json():
    """`json.loads` aceita o literal NaN (Jackson emite), e `collect` grava com
    `allow_nan=False`: um NaN numa fila abortava a gravação e a auditoria inteira se perdia."""
    documento = {"items": [{"name": "a", "n": float("nan")}]}

    itens = extrair(documento, {"lista": "/items", "campos": {"nome": "/name", "n": "/n"}})

    assert itens[0]["n"] is None
    json.dumps(itens, allow_nan=False)


def test_infinito_em_campo_sem_transformar_tambem_some():
    documento = {"items": [{"name": "a", "n": math.inf}]}

    itens = extrair(documento, {"lista": "/items", "campos": {"nome": "/name", "n": "/n"}})

    assert itens[0]["n"] is None


# --- campo que despeja objeto no relatório ---

def test_campo_que_aponta_para_objeto_e_recusado():
    """`/arguments` e `client_properties` carregam credencial com frequência, e o caminho da
    extração não passa por `lib/redact.py`. A linguagem entrega escalar."""
    documento = {"items": [{"name": "a", "arguments": {"senha": "p"}}]}

    with pytest.raises(ExtracaoInvalida, match="escalar"):
        extrair(documento, {"lista": "/items",
                            "campos": {"nome": "/name", "args": "/arguments"}})


# --- declaração estrutural ---

def test_campos_vazio_e_recusado():
    with pytest.raises(ExtracaoInvalida, match="campos"):
        validar_declaracao({"lista": "/items", "campos": {}})


def test_item_da_lista_que_nao_e_objeto_e_recusado():
    """Virava item fantasma: `["a", 5]` produzia `[{"nome": None}, {"nome": None}]`."""
    with pytest.raises(ExtracaoInvalida, match="objeto"):
        extrair({"items": ["a", 5]}, {"lista": "/items", "campos": {"nome": "/name"}})


def test_lista_vazia_ainda_valida_a_declaracao():
    """O catálogo quebrado passava verde enquanto a fila estivesse vazia."""
    with pytest.raises(ExtracaoInvalida):
        extrair({"items": []}, {"lista": "/items", "campos": {"nome": "items/0"}})


# --- derivação malformada ---

@pytest.mark.parametrize("declarada, marca", [
    ({"tipo": "diferenca", "de": "/a"}, "menos"),
    ({"tipo": "razao", "numerador": "/a"}, "denominador_soma"),
    ({"tipo": "percentual_de", "numerador": "/a"}, "denominador"),
])
def test_derivacao_sem_chave_obrigatoria_e_extracao_invalida(declarada, marca):
    """Antes escapava como `KeyError: 'menos'`, sem nome de arquivo nem da derivação."""
    with pytest.raises(ExtracaoInvalida, match=marca):
        validar_declaracao({"campos": {"a": "/a"}, "derivar": {"d": declarada}})


def test_denominador_soma_como_texto_e_recusado():
    """`denominador_soma = "/hits"` (string em vez de array) virava lista de caracteres e
    devolvia None para sempre, sem erro nenhum."""
    with pytest.raises(ExtracaoInvalida, match="lista"):
        validar_declaracao({"campos": {"a": "/a"},
                            "derivar": {"d": {"tipo": "razao", "numerador": "/a",
                                              "denominador_soma": "/hits"}}})


def test_soma_sem_parcelas_e_recusada():
    with pytest.raises(ExtracaoInvalida, match="parcelas"):
        validar_declaracao({"campos": {"a": "/a"},
                            "derivar": {"d": {"tipo": "soma", "parcelas": []}}})

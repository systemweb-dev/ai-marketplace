# tests/test_extracao_derivacoes.py
"""Derivações: a conta que o catálogo pode declarar.

A expressão de limiar não faz aritmética de propósito — abrir uma exceção ali seria abrir a
porta para uma linguagem inteira. O que precisa de conta vira derivação DECLARADA, de um
conjunto fechado, e o limiar compara o resultado.
"""
import pytest

from lib.extracao import ExtracaoInvalida, derivar, extrair


def test_razao_simples():
    assert derivar({"hits": 90, "misses": 10},
                   {"tipo": "razao", "numerador": "/hits",
                    "denominador_soma": ["/hits", "/misses"]}) == 0.9


def test_razao_com_denominador_zero_e_none():
    """Dividir por zero não é 0 nem infinito: é "não dá para dizer". Cache sem acesso nenhum
    não tem taxa de acerto — inventar 0% acusaria um problema que não existe."""
    assert derivar({"hits": 0, "misses": 0},
                   {"tipo": "razao", "numerador": "/hits",
                    "denominador_soma": ["/hits", "/misses"]}) is None


def test_percentual_de():
    assert derivar({"usada": 2, "total": 8},
                   {"tipo": "percentual_de", "numerador": "/usada",
                    "denominador": "/total"}) == 25.0


def test_diferenca():
    assert derivar({"entrada": 10.0, "saida": 4.0},
                   {"tipo": "diferenca", "de": "/entrada", "menos": "/saida"}) == 6.0


def test_diferenca_pode_ser_negativa():
    """Saldo negativo é o caso interessante: sai mais do que entra, a fila está drenando."""
    assert derivar({"entrada": 1.0, "saida": 4.0},
                   {"tipo": "diferenca", "de": "/entrada", "menos": "/saida"}) == -3.0


def test_soma():
    assert derivar({"a": 1, "b": 2, "c": 3},
                   {"tipo": "soma", "parcelas": ["/a", "/b", "/c"]}) == 6.0


def test_campo_ausente_torna_a_derivacao_none():
    assert derivar({"hits": 5},
                   {"tipo": "razao", "numerador": "/hits",
                    "denominador_soma": ["/hits", "/misses"]}) is None


def test_tipo_de_derivacao_desconhecido_e_recusado():
    with pytest.raises(ExtracaoInvalida):
        derivar({"a": 1}, {"tipo": "regressao", "de": "/a"})


def test_derivacao_entra_no_item_extraido():
    documento = {"items": [{"name": "c", "hits": 3, "misses": 1}]}

    itens = extrair(documento, {
        "lista": "/items",
        "campos": {"nome": "/name"},
        "derivar": {"hit_ratio": {"tipo": "razao", "numerador": "/hits",
                                  "denominador_soma": ["/hits", "/misses"]}},
    })

    assert itens[0] == {"nome": "c", "hit_ratio": 0.75}


def test_derivacao_pode_ser_a_chave_de_ordenacao():
    documento = {"items": [{"name": "ruim", "hits": 1, "misses": 9},
                           {"name": "bom", "hits": 9, "misses": 1}]}

    itens = extrair(documento, {
        "lista": "/items", "campos": {"nome": "/name"},
        "derivar": {"hit_ratio": {"tipo": "razao", "numerador": "/hits",
                                  "denominador_soma": ["/hits", "/misses"]}},
        "ordenar_por": "hit_ratio", "ordem": "desc", "desempate": "nome",
    })

    assert [i["nome"] for i in itens] == ["bom", "ruim"]


def test_derivacao_nao_sobrescreve_campo_declarado():
    """Nome repetido entre `campos` e `derivar` é erro de arquivo, não precedência silenciosa."""
    with pytest.raises(ExtracaoInvalida):
        extrair({"items": [{"n": 1}]},
                {"lista": "/items", "campos": {"x": "/n"},
                 "derivar": {"x": {"tipo": "soma", "parcelas": ["/n"]}}})


def test_derivacao_le_o_documento_cru_nao_o_item_ja_extraido():
    """Os caminhos de `derivar` são ponteiros no JSON ORIGINAL, não nomes de campo extraído.
    Confundir os dois faria toda derivação sobre campo renomeado devolver None."""
    documento = {"items": [{"name": "c", "message_stats": {"publish_details": {"rate": 8.0},
                                                           "deliver_get_details": {"rate": 3.0}}}]}

    itens = extrair(documento, {
        "lista": "/items", "campos": {"nome": "/name"},
        "derivar": {"saldo": {"tipo": "diferenca",
                              "de": "/message_stats/publish_details/rate",
                              "menos": "/message_stats/deliver_get_details/rate"}},
    })

    assert itens[0]["saldo"] == 5.0


def test_razao_arredonda_em_quatro_casas():
    """A política de casas decimais não tinha cobertura nenhuma: um mutante que removia o
    `round` passava verde."""
    assert derivar({"a": 1, "b": 3},
                   {"tipo": "razao", "numerador": "/a",
                    "denominador_soma": ["/a", "/b"]}) == 0.25
    assert derivar({"a": 1, "b": 6},
                   {"tipo": "razao", "numerador": "/a",
                    "denominador_soma": ["/a", "/b"]}) == 0.1429


def test_percentual_de_arredonda_em_duas_casas():
    assert derivar({"a": 1, "b": 3},
                   {"tipo": "percentual_de", "numerador": "/a",
                    "denominador": "/b"}) == 33.33


def test_soma_arredonda_em_quatro_casas():
    assert derivar({"a": 0.1, "b": 0.2},
                   {"tipo": "soma", "parcelas": ["/a", "/b"]}) == 0.3


def test_diferenca_arredonda_em_quatro_casas():
    """`0.3 - 0.1` em ponto flutuante dá 0.19999999999999998."""
    assert derivar({"a": 0.3, "b": 0.1},
                   {"tipo": "diferenca", "de": "/a", "menos": "/b"}) == 0.2


def test_soma_de_inteiros_e_inteira():
    """Somar contagens de mensagens dava `80.000,00` no relatório: conta de inteiros é inteira."""
    resultado = derivar({"a": 79990, "b": 10}, {"tipo": "soma", "parcelas": ["/a", "/b"]})

    assert resultado == 80000 and isinstance(resultado, int)


def test_diferenca_de_decimais_continua_decimal():
    resultado = derivar({"a": 12.0, "b": 11.5}, {"tipo": "diferenca", "de": "/a", "menos": "/b"})

    assert resultado == 0.5 and isinstance(resultado, float)

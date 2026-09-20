# tests/test_extracao.py
"""A linguagem fechada de extração.

Regra de ouro do spec: o que não couber aqui NÃO ganha arquivo — vira adaptador com código e
teste. Uma linguagem que aceita expressão arbitrária é `eval` com outro nome, e um arquivo de
catálogo é dado, não código.
"""
import pytest

from lib.extracao import ExtracaoInvalida, extrair, ponteiro, transformar

FILAS = {"items": [
    {"name": "pedidos", "messages_ready": "42", "consumers": 3},
    {"name": "emails", "messages_ready": 7, "consumers": 0},
    {"name": "morta", "messages_ready": 900, "consumers": 0},
]}


# --- ponteiro (RFC 6901) ---

def test_ponteiro_vazio_e_o_documento_inteiro():
    assert ponteiro({"a": 1}, "") == {"a": 1}


def test_ponteiro_navega_objeto_e_indice():
    assert ponteiro(FILAS, "/items/1/name") == "emails"


def test_ponteiro_de_chave_ausente_e_none_nao_erro():
    """Campo que a família não expõe é `sem_dados` daquela pergunta, não exceção."""
    assert ponteiro(FILAS, "/items/0/nao_existe") is None


def test_ponteiro_sem_barra_inicial_e_recusado():
    """`items/0` parece funcionar e não é ponteiro: recusar no carregamento evita um arquivo
    que erra em silêncio."""
    with pytest.raises(ExtracaoInvalida):
        ponteiro(FILAS, "items/0")


def test_ponteiro_escapa_til_e_barra():
    documento = {"a/b": {"c~d": 9}}

    assert ponteiro(documento, "/a~1b/c~0d") == 9


def test_ponteiro_em_escalar_para_de_navegar():
    assert ponteiro({"a": 5}, "/a/b") is None


# --- transformações ---

@pytest.mark.parametrize("tipo, bruto, esperado", [
    ("inteiro", "42", 42),
    ("inteiro", 42.9, 42),
    ("decimal", "3.5", 3.5),
    ("decimal", "3.456", 3.46),          # prova o round(,2); 3.456 != 3.5 != 3
    ("texto", "42", "42"),               # entrada string: `repr` daria "'42'"
    ("bytes", 1536, 1536),
    ("segundos", "90.44", 90.44),        # decimal de verdade: `inteiro` daria 90
    ("percentual", 0.5, 50.0),
    ("percentual", 0.3333, 33.33),       # prova o round(,2)
    ("data_iso", "2026-09-19T10:00:00Z", "2026-09-19T10:00:00+00:00"),
])
def test_transformacoes_permitidas(tipo, bruto, esperado):
    assert transformar(bruto, tipo) == esperado


def test_transformacao_de_valor_impossivel_e_none():
    """"n/a" onde se esperava número não vira 0: 0 é uma medida, None é a ausência dela."""
    assert transformar("n/a", "inteiro") is None


def test_transformacao_desconhecida_e_recusada():
    with pytest.raises(ExtracaoInvalida):
        transformar("1", "sql")


def test_nan_e_infinito_nao_passam():
    """NaN escrito no report.json produz JSON inválido para qualquer leitor fora do Python."""
    assert transformar(float("nan"), "decimal") is None
    assert transformar(float("inf"), "decimal") is None


# --- extração de lista ---

def test_extrai_lista_com_campos_e_transformacoes():
    itens = extrair(FILAS, {
        "lista": "/items",
        "campos": {"nome": "/name", "prontas": "/messages_ready",
                   "consumidores": "/consumers"},
        "transformar": {"prontas": "inteiro", "consumidores": "inteiro"},
    })

    assert itens[0] == {"nome": "pedidos", "prontas": 42, "consumidores": 3}


def test_ordena_e_corta_no_limite():
    itens = extrair(FILAS, {
        "lista": "/items",
        "campos": {"nome": "/name", "prontas": "/messages_ready"},
        "transformar": {"prontas": "inteiro"},
        "ordenar_por": "prontas", "ordem": "desc", "desempate": "nome", "limite": 2,
    })

    assert [i["nome"] for i in itens] == ["morta", "pedidos"]


def test_empate_de_valor_desempata_pelo_nome():
    """Sem desempate, duas rodadas iguais dariam top N em ordens diferentes — e o diff entre
    auditorias acusaria mudança onde nada mudou."""
    documento = {"items": [{"name": "zulu", "n": 5}, {"name": "alfa", "n": 5}]}

    itens = extrair(documento, {
        "lista": "/items", "campos": {"nome": "/name", "n": "/n"},
        "transformar": {"n": "inteiro"}, "ordenar_por": "n", "ordem": "desc",
        "desempate": "nome",
    })

    assert [i["nome"] for i in itens] == ["alfa", "zulu"]


def test_lista_na_raiz_do_documento():
    documento = [{"name": "unica", "n": 1}]

    itens = extrair(documento, {"lista": "", "campos": {"nome": "/name"}})

    assert itens == [{"nome": "unica"}]


def test_lista_que_nao_e_lista_e_recusada():
    with pytest.raises(ExtracaoInvalida):
        extrair({"items": {"nao": "lista"}}, {"lista": "/items",
                                              "campos": {"nome": "/nao"}})


def test_escalar_sem_lista_declarada():
    assert extrair({"total": "17"}, {"campos": {"valor": "/total"},
                                     "transformar": {"valor": "inteiro"}}) == {"valor": 17}


def test_valor_ausente_vai_para_o_fim_mesmo_em_ordem_decrescente():
    """`None` é "não li", e "não li" nunca encabeça um ranking.

    A chave de ordenação usa `(valor is None, valor)`, e `reverse=True` inverte a TUPLA
    inteira — então `True` (ausente) passaria na frente de `False` (presente), e o topo do
    "filas com mais mensagens" seria ocupado pelas filas que não souberam responder.
    """
    documento = {"items": [{"name": "sem-dado", "n": None},
                           {"name": "maior", "n": 90},
                           {"name": "menor", "n": 5}]}

    itens = extrair(documento, {
        "lista": "/items", "campos": {"nome": "/name", "n": "/n"},
        "ordenar_por": "n", "ordem": "desc", "desempate": "nome"})

    assert [i["nome"] for i in itens] == ["maior", "menor", "sem-dado"]


def test_valor_ausente_tambem_vai_para_o_fim_em_ordem_crescente():
    documento = {"items": [{"name": "sem-dado", "n": None},
                           {"name": "menor", "n": 5},
                           {"name": "maior", "n": 90}]}

    itens = extrair(documento, {
        "lista": "/items", "campos": {"nome": "/name", "n": "/n"},
        "ordenar_por": "n", "ordem": "asc", "desempate": "nome"})

    assert [i["nome"] for i in itens] == ["menor", "maior", "sem-dado"]


def test_booleano_nao_passa_por_numero():
    """`float(True)` é 1.0. Um campo booleano viraria a medida "1" sem ninguém notar."""
    assert transformar(True, "inteiro") is None


def test_ordena_por_campo_de_texto():
    """Nem toda chave de ordenação é número; um `-valor` para inverter quebraria aqui."""
    documento = {"items": [{"name": "zulu"}, {"name": "alfa"}]}

    itens = extrair(documento, {"lista": "/items", "campos": {"nome": "/name"},
                                "ordenar_por": "nome", "ordem": "asc", "desempate": "nome"})

    assert [i["nome"] for i in itens] == ["alfa", "zulu"]


def test_zero_nao_e_confundido_com_ausencia_na_ordenacao():
    """`0 or 0` e `None or 0` davam o mesmo na versão antiga: a fila com zero mensagens caía
    junto com a que não respondeu, e as duas coisas são diferentes."""
    documento = {"items": [{"name": "zerada", "n": 0}, {"name": "muda", "n": None},
                           {"name": "cheia", "n": 3}]}

    itens = extrair(documento, {
        "lista": "/items", "campos": {"nome": "/name", "n": "/n"},
        "ordenar_por": "n", "ordem": "desc", "desempate": "nome"})

    assert [i["nome"] for i in itens] == ["cheia", "zerada", "muda"]


def test_escape_de_til_e_barra_na_ordem_certa():
    """`~01` é o único caso em que a ordem dos dois `replace` importa: trocada, `~01` viraria
    `~1` e depois `/`, em vez de `~0` seguido de `1`."""
    assert ponteiro({"~1": 7}, "/~01") == 7


def test_indice_negativo_nao_e_ponteiro_valido():
    """O RFC 6901 só admite `0` ou `[1-9][0-9]*`. `-1` funcionava por acidente do Python e
    devolvia o ÚLTIMO item onde o autor do catálogo quis o primeiro."""
    assert ponteiro({"i": [1, 2, 3]}, "/i/-1") is None


def test_indice_com_zero_a_esquerda_nao_e_ponteiro_valido():
    assert ponteiro({"i": [1, 2, 3]}, "/i/01") is None


def test_indice_valido_continua_funcionando():
    assert ponteiro({"i": [1, 2, 3]}, "/i/0") == 1
    assert ponteiro({"i": [1, 2, 3]}, "/i/2") == 3


def test_data_iso_aceita_o_sufixo_z():
    assert transformar("2026-09-19T10:00:00Z", "data_iso") == "2026-09-19T10:00:00+00:00"


def test_data_iso_com_fuso_explicito_preserva_o_fuso():
    assert transformar("2026-09-19T10:00:00-03:00", "data_iso") == "2026-09-19T10:00:00-03:00"

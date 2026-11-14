# tests/test_extracao_formatos.py
import pytest

from lib.extracao import ExtracaoInvalida, documento, extrair, validar_declaracao

STATUS = "Aborted_clients\t3\nThreads_connected\t12\nSlow_queries\t7\n"
VARIAVEIS = "max_connections\t151\nversion\t11.4.2-MariaDB\n"
INFO = ("# Server\r\nredis_version:7.2.4\r\n\r\n# Memory\r\nused_memory:1048576\r\n"
        "# Stats\r\nkeyspace_hits:90\r\nkeyspace_misses:10\r\nevicted_keys:0\r\n")


def test_chave_valor_le_a_saida_do_mysql():
    assert documento(STATUS, "chave_valor") == {
        "Aborted_clients": "3", "Threads_connected": "12", "Slow_queries": "7"}


def test_chave_valor_do_redis_usa_dois_pontos_tira_o_cr_e_pula_secao():
    doc = documento(INFO, "chave_valor", separador=":")
    assert doc["used_memory"] == "1048576" and doc["keyspace_misses"] == "10"
    assert "# Server" not in doc and doc["redis_version"] == "7.2.4"


def test_tsv_vira_linhas_com_as_colunas_declaradas():
    assert documento("app\t2048\nlogs\tNULL\n", "tsv", colunas=["nome", "bytes"]) == {
        "linhas": [{"nome": "app", "bytes": "2048"}, {"nome": "logs", "bytes": "NULL"}]}


def test_tsv_com_campo_a_menos_e_saida_que_nao_se_entendeu():
    assert documento("so-um-campo\n", "tsv", colunas=["nome", "bytes"]) is None


def test_tsv_com_coluna_a_mais_fica_com_as_declaradas():
    assert documento("binlog.000001\t4096\tNo\n", "tsv", colunas=["nome", "bytes"]) == {
        "linhas": [{"nome": "binlog.000001", "bytes": "4096"}]}


def test_tsv_com_o_separador_do_psql():
    assert documento("12|100\n", "tsv", colunas=["usadas", "limite"], separador="|") == {
        "linhas": [{"usadas": "12", "limite": "100"}]}


def test_json_invalido_e_chave_valor_sem_par_viram_none():
    assert documento("<html>", "json") is None
    assert documento("NOAUTH Authentication required.", "chave_valor", separador=":") is None


def test_formato_desconhecido_e_recusado():
    with pytest.raises(ExtracaoInvalida, match="formato 'xml' não existe"):
        documento("x", "xml")


def test_escalar_de_tsv_aponta_para_a_primeira_linha():
    doc = documento("734003200\n", "tsv", colunas=["valor"])
    assert extrair(doc, {"campos": {"valor": "/linhas/0/valor"},
                         "transformar": {"valor": "bytes"}}) == {"valor": 734003200}


def test_uso_de_conexoes_junta_status_e_variaveis():
    doc = {**documento(STATUS, "chave_valor"), **documento(VARIAVEIS, "chave_valor")}
    declarada = {"derivar": {"valor": {"tipo": "percentual_de", "numerador": "/Threads_connected",
                                       "denominador": "/max_connections"}}}
    assert extrair(doc, declarada) == {"valor": 7.95}


def test_percentual_de_aceita_denominador_somado():
    doc = documento(INFO, "chave_valor", separador=":")
    declarada = {"derivar": {"valor": {"tipo": "percentual_de", "numerador": "/keyspace_hits",
                                       "denominador_soma": ["/keyspace_hits", "/keyspace_misses"]}}}
    assert extrair(doc, declarada) == {"valor": 90.0}


def test_percentual_sem_leitura_nenhuma_nao_e_zero():
    declarada = {"derivar": {"valor": {"tipo": "percentual_de", "numerador": "/h",
                                       "denominador_soma": ["/h", "/m"]}}}
    assert extrair({"h": "0", "m": "0"}, declarada) == {"valor": None}


def test_percentual_com_os_dois_denominadores_e_recusado():
    with pytest.raises(ExtracaoInvalida, match="um dos dois"):
        validar_declaracao({"derivar": {"v": {"tipo": "percentual_de", "numerador": "/a",
                                              "denominador": "/b", "denominador_soma": ["/c"]}}})

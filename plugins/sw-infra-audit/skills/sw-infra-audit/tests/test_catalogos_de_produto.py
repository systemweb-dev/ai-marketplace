# tests/test_catalogos_de_produto.py
import json
import pathlib

import pytest

from apoio_host import Falha, runner_falso
from lib import catalogo_produto
from lib.adaptadores import produto_ssh

STATUS = "Aborted_clients\t3\nSlow_queries\t7\nThreads_connected\t12\n"
VARIAVEIS = "max_connections\t151\nversion\t11.4.2-MariaDB\n"
SQL_TAMANHO = "SELECT SUM(data_length + index_length) FROM information_schema.tables"
SQL_POR_BANCO = ("SELECT table_schema, SUM(data_length + index_length) FROM "
                 "information_schema.tables GROUP BY table_schema")
SAIDAS_MARIADB = {
    "SHOW GLOBAL STATUS": STATUS, "SHOW GLOBAL VARIABLES": VARIAVEIS,
    SQL_TAMANHO: "734003200\n",
    SQL_POR_BANCO: "app\t700000000\ninformation_schema\tNULL\nmysql\t34003200\n",
    "SHOW BINARY LOGS": "binlog.000001\t1048576\nbinlog.000002\t2048\n",
}
SAIDAS_POSTGRES = {
    "SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend'": "9\n",
    "SELECT count(*), current_setting('max_connections') FROM pg_stat_activity "
    "WHERE backend_type = 'client backend'": "9|100\n",
    "SELECT sum(pg_database_size(datname)) FROM pg_database": "52428800\n",
    "SELECT datname, pg_database_size(datname) FROM pg_database WHERE NOT datistemplate":
        "app|41943040\npostgres|10485760\n",
}
INFO = ("# Server\r\nredis_version:7.2.4\r\n\r\n# Memory\r\nused_memory:1048576\r\n\r\n"
        "# Stats\r\nkeyspace_hits:90\r\nkeyspace_misses:10\r\nevicted_keys:3\r\n")
SAIDAS_QDRANT = {
    "/collections": json.dumps({"result": {"collections": [{"name": "docs"}, {"name": "faq"}]},
                                "status": "ok", "time": 0.0001}),
    "/collections/docs": json.dumps({"result": {"status": "green", "points_count": 1200,
                                                "segments_count": 2}, "status": "ok"}),
    "/collections/faq": json.dumps({"result": {"status": "yellow", "points_count": 30},
                                    "status": "ok"}),
}


def _respostas(monkeypatch, produto, saidas, papel="banco", **campos):
    componente = {"nome": produto, "papel": papel, "produto": produto, "leitura": "socket",
                  "origem": f"processo:{produto}", "ssh_destino": "root@10.0.0.10", "porta": None,
                  **campos}
    monkeypatch.setattr(produto_ssh.runner, "run_ssh", runner_falso(saidas))
    contexto = {"timeout": 20, "cache": {}, "alvo": "banco-01"}
    catalogo = catalogo_produto.do_produto(produto)
    return {p["id"]: produto_ssh.perguntar(p["id"], componente, contexto)
            for p in catalogo["pergunta"]}


def _valores(monkeypatch, produto, saidas, **opcoes):
    respostas = _respostas(monkeypatch, produto, saidas, **opcoes)
    mudas = {p: r["motivo"] for p, r in respostas.items() if r.get("sem_dados")}
    assert mudas == {}
    return {p: r["valor"] for p, r in respostas.items()}


def test_os_cinco_catalogos_carregam():
    assert {c["produto"] for c in catalogo_produto.todos()} == \
        {"mariadb", "mysql", "postgres", "redis", "qdrant"}


def test_senha_so_no_mariadb_e_no_mysql():
    assert {c["produto"] for c in catalogo_produto.todos() if "senha" in c["cliente"]} == \
        {"mariadb", "mysql"}


def test_mariadb_responde_as_seis_perguntas(monkeypatch):
    assert _valores(monkeypatch, "mariadb", SAIDAS_MARIADB) == {
        "banco.conexoes": 12, "banco.consultas_lentas": 7, "banco.uso_de_conexoes": 7.95,
        "banco.tamanho": 734003200,
        "banco.tamanho_por_banco": [{"nome": "app", "bytes": 700000000},
                                    {"nome": "mysql", "bytes": 34003200},
                                    {"nome": "information_schema", "bytes": None}],
        "banco.binlog": [{"nome": "binlog.000001", "bytes": 1048576},
                         {"nome": "binlog.000002", "bytes": 2048}],
    }


def test_mysql_usa_o_binario_mysql_com_as_mesmas_consultas(monkeypatch):
    mysql = catalogo_produto.do_produto("mysql")
    assert {m.split()[0] for m in mysql["cliente"].values()} == {"mysql", "docker"}
    assert _valores(monkeypatch, "mysql", SAIDAS_MARIADB)["banco.uso_de_conexoes"] == 7.95


def test_binlog_desligado_e_nao_medido_por_desenho(monkeypatch):
    saidas = {**SAIDAS_MARIADB, "SHOW BINARY LOGS": Falha(
        "ERROR 1381 (HY000) at line 1: You are not using binary logging")}
    binlog = _respostas(monkeypatch, "mariadb", saidas)["banco.binlog"]
    assert binlog["nao_publica"] and binlog["motivo"] == "o binlog está desligado neste servidor"


def test_postgres_separa_por_barra_vertical(monkeypatch):
    assert _valores(monkeypatch, "postgres", SAIDAS_POSTGRES) == {
        "banco.conexoes": 9, "banco.uso_de_conexoes": 9.0, "banco.tamanho": 52428800,
        "banco.tamanho_por_banco": [{"nome": "app", "bytes": 41943040},
                                    {"nome": "postgres", "bytes": 10485760}]}


def test_postgres_conta_so_conexoes_de_cliente():
    """pg_stat_activity inteiro inclui autovacuum, checkpointer e outros processos de fundo."""
    perguntas = {p["id"]: p for p in catalogo_produto.do_produto("postgres")["pergunta"]}
    for id_ in ("banco.conexoes", "banco.uso_de_conexoes"):
        assert perguntas[id_]["sql"] == [s for s in perguntas[id_]["sql"]
                                        if "WHERE backend_type = 'client backend'" in s], id_


def test_postgres_sem_root_diz_o_motivo(monkeypatch):
    saidas = {"SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend'":
              Falha("runuser: may not be used by non-root users")}
    conexoes = _respostas(monkeypatch, "postgres", saidas)["banco.conexoes"]
    assert "exige o SSH como root" in conexoes["motivo"]


def test_redis_le_o_info(monkeypatch):
    assert _valores(monkeypatch, "redis", {"INFO": INFO}, papel="cache") == {
        "cache.memoria_usada": 1048576, "cache.evicções": 3, "cache.acerto": 90.0}


def test_redis_com_senha_fica_para_depois(monkeypatch):
    respostas = _respostas(monkeypatch, "redis", {"INFO": "NOAUTH Authentication required.\n"},
                           papel="cache")
    assert "Redis pede senha" in respostas["cache.memoria_usada"]["motivo"]


def test_qdrant_enumera_as_colecoes(monkeypatch):
    assert _valores(monkeypatch, "qdrant", SAIDAS_QDRANT, papel="busca", portas=[6333, 6334]) == {
        "busca.colecoes": [{"nome": "docs", "pontos": 1200, "status": "green"},
                           {"nome": "faq", "pontos": 30, "status": "yellow"}]}


def test_qdrant_com_chave_fica_para_depois(monkeypatch):
    respostas = _respostas(monkeypatch, "qdrant", {"/collections": Falha("", 22)}, papel="busca")
    assert "chave de API" in respostas["busca.colecoes"]["motivo"]


@pytest.mark.parametrize("pergunta", ["banco.tamanho_por_banco", "banco.uso_de_conexoes",
                                      "banco.consultas_lentas", "banco.binlog", "busca.colecoes"])
def test_perguntas_de_catalogo_sao_opcionais_e_fora_do_papel(pergunta):
    from lib.perguntas import ORDEM, PERGUNTAS

    assert PERGUNTAS[pergunta]["opcional"] and PERGUNTAS[pergunta]["limiar"] is None
    assert not any(pergunta in ids for ids in ORDEM.values())


FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "produto" / "mariadb"


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="spike da Task 1 não executado")
def test_saidas_reais_do_spike_viram_numero(monkeypatch):
    ler = lambda nome: (FIXTURES / nome).read_text(encoding="utf-8")
    saidas = {"SHOW GLOBAL STATUS": ler("status.txt"), "SHOW GLOBAL VARIABLES": ler("variaveis.txt"),
              SQL_TAMANHO: ler("tamanho.txt"), SQL_POR_BANCO: ler("tamanho_por_banco.txt")}
    respostas = _respostas(monkeypatch, "mariadb", saidas)
    for pergunta in ("banco.conexoes", "banco.consultas_lentas", "banco.uso_de_conexoes",
                     "banco.tamanho", "banco.tamanho_por_banco"):
        assert not respostas[pergunta].get("sem_dados"), (pergunta, respostas[pergunta])

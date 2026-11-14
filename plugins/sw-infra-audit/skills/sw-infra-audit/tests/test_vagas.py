import pytest

from lib import vagas


def test_vaga_e_nome_entre_uma_chave_e_o_formato_do_docker_nao_e():
    assert vagas.nomes("docker inspect --format '{{json .State}}' {container}") == {"container"}
    assert vagas.nomes('curl -s "http://127.0.0.1:{porta}{sql}"') == {"porta", "sql"}
    assert vagas.nomes("id -un") == set()


@pytest.mark.parametrize("pasta,aceita", [
    ("/var/backups/mysql", True), ("/srv/dump_2026.d", True), ("var/backups", False),
    ("/var/../etc", False), ("/var/back ups", False), ("/var/$HOME", False),
    ("/var/backups;reboot", False), ("/" + "a" * 300, False), (None, False)])
def test_pasta_de_backup_e_absoluta_e_nao_sobe_diretorio(pasta, aceita):
    assert vagas.pasta_valida(pasta) is aceita


@pytest.mark.parametrize("sql", ['SELECT "a"', "SELECT $HOME", "SELECT `id`", "SELECT 1 \\ 2",
                                 "SELECT 1 % 2", "SELECT 1 < 2", "SELECT 1 > 2",
                                 "SELECT 1\nSELECT 2", "", "   "])
def test_consulta_com_caractere_que_o_shell_interpreta_e_recusada(sql):
    assert vagas.sql_valido(sql) is False


def test_consulta_comum_e_aceita():
    assert vagas.sql_valido("SELECT table_schema, SUM(data_length + index_length) FROM "
                            "information_schema.tables GROUP BY table_schema") is True
    assert vagas.sql_valido("SELECT count(*), current_setting('max_connections') "
                            "FROM pg_stat_activity") is True

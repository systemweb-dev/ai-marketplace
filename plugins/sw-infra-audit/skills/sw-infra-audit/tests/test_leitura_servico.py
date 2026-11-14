# tests/test_leitura_servico.py
from datetime import date

import pytest

from lib import leitura_servico as ls

SHOW = ("ActiveState=active\nActiveEnterTimestampMonotonic=86400000000\nNRestarts=2\n"
        "MemoryCurrent=524288000\n")
UPTIME = "259200.00 1000.00\n"
INSPECT = ('3 {"Status":"running","Running":true,"StartedAt":"2026-11-10T10:00:00.123456789Z",'
           '"Error":"falha antiga com espaço"}')
AGORA = 1794564000   # 2026-11-13T10:00:00Z
PS = ("systemd 1200 900000\nqdrant 524288 86400\nqdrant 1048576 3600\n"
      "meu worker 100 10\n")
LS = ("total 12\n"
      "-rw-r--r-- 1 root root 4096 2026-11-13 01:00:00.000000000 +0000 leia-me.txt\n"
      "-rw-r--r-- 1 root root 9999 2026-11-12 03:00:01.000000000 +0000 dump-2026-11-08.sql.gz\n"
      "-rw-r--r-- 1 root root 8888 2026-11-07 03:00:01.000000000 +0000 dump-20261107.sql.gz\n")


def test_unit_ativa_mede_as_quatro():
    assert ls.de_unidade(SHOW, UPTIME) == {"servico.ativo": "ativo", "servico.desde": 2.0,
                                           "servico.reinicios": 2, "servico.memoria": 524288000}


@pytest.mark.parametrize("memoria", ["[not set]", "18446744073709551615", ""])
def test_unit_sem_contabilidade_de_memoria_e_nao_medido_por_desenho(memoria):
    resposta = ls.de_unidade(SHOW.replace("524288000", memoria), UPTIME)
    assert resposta["servico.memoria"] == ls.SEM_MEMORIA_DA_UNIT


def test_unit_parada_diz_o_estado_e_nao_inventa_tempo_no_ar():
    show = ("ActiveState=failed\nActiveEnterTimestampMonotonic=0\nNRestarts=5\n"
            "MemoryCurrent=[not set]\n")
    resposta = ls.de_unidade(show, UPTIME)
    assert (resposta["servico.ativo"], resposta["servico.desde"], resposta["servico.reinicios"]) == \
        ("failed", ls.NAO_ATIVO, 5)


def test_saida_que_nao_e_do_systemd_e_none():
    assert ls.de_unidade("lixo", UPTIME) is None and ls.de_unidade("", UPTIME) is None


def test_container_rodando_usa_o_instante_da_rodada():
    assert ls.de_container(INSPECT, "512MiB / 2GiB\n", AGORA) == {
        "servico.ativo": "ativo", "servico.reinicios": 3, "servico.desde": 3.0,
        "servico.memoria": 536870912}


def test_container_parado_nao_mede_tempo_nem_memoria():
    resposta = ls.de_container('0 {"Status":"exited","StartedAt":"2026-11-10T10:00:00Z"}', "", AGORA)
    assert resposta == {"servico.ativo": "exited", "servico.reinicios": 0,
                        "servico.desde": ls.NAO_ATIVO, "servico.memoria": ls.NAO_ATIVO}


def test_inspect_fora_do_formato_e_none():
    assert ls.de_container("3 nada", "", AGORA) is None and ls.de_container("", "", AGORA) is None


@pytest.mark.parametrize("saida,bytes_", [("1.5GiB / 4GiB", 1610612736), ("0B / 0B", 0),
                                          ("812kB / 1GB", 812000), ("lixo", None),
                                          ("12XB / 1GB", None), ("nan MiB / 1GiB", None)])
def test_memoria_do_stats_em_varias_unidades(saida, bytes_):
    assert ls.memoria_do_stats(saida) == bytes_


def test_processo_principal_e_o_mais_antigo_nunca_a_soma_dos_workers():
    assert ls.de_processo(PS, "qdrant") == {
        "servico.ativo": "ativo", "servico.desde": 1.0,
        "servico.reinicios": ls.SEM_REINICIOS, "servico.memoria": 524288 * 1024}


def test_processo_com_espaco_no_nome():
    assert ls.de_processo(PS, "meu worker")["servico.memoria"] == 100 * 1024


def test_processo_ausente_e_parado():
    resposta = ls.de_processo(PS, "redis-server")
    assert resposta["servico.ativo"] == "parado" and resposta["servico.desde"] == ls.NAO_ATIVO


def test_ps_sem_saida_e_none():
    assert ls.de_processo("", "qdrant") is None


def test_backup_pela_data_do_nome_mais_novo_nao_pelo_mtime():
    assert ls.idade_do_backup(LS, date(2026, 11, 13)) == 5


def test_sem_data_no_nome_usa_o_mtime():
    saida = "total 4\n-rw-r--r-- 1 root root 10 2026-11-10 03:00:00.000000000 +0000 base.sql.gz\n"
    assert ls.idade_do_backup(saida, date(2026, 11, 13)) == 3


@pytest.mark.parametrize("nome", ["dump-20261399.sql", "dump_1699999999.sql"])
def test_numero_que_nao_e_data_cai_no_mtime(nome):
    saida = f"total 4\n-rw-r--r-- 1 root root 10 2026-11-11 03:00:00.000000000 +0000 {nome}\n"
    assert ls.idade_do_backup(saida, date(2026, 11, 13)) == 2


def test_pasta_vazia_e_none_nunca_atraso():
    assert ls.idade_do_backup("total 0\n", date(2026, 11, 13)) is None

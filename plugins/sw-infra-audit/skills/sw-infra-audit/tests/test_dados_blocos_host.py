from lib.dados_blocos import dados_do_papel
from tests.fixtures.relatorio_docker import relatorio_docker
from tests.fixtures.relatorio_host import alvo_host_banco, alvo_host_sem_vpn


def _por_nome(itens):
    return {i["nome"]: i for i in itens}


def test_banco_do_host_traz_os_campos_do_produto_e_o_problema():
    mariadb = _por_nome(dados_do_papel("banco", [alvo_host_banco()])["itens"])["mariadb"]
    assert (mariadb["uso"], mariadb["lentas"], mariadb["backup"], mariadb["backup_max"]) == (24.7, 12, 5, 2)
    assert [b["nome"] for b in mariadb["por_banco"]][:2] == ["loja", "erp"]
    assert [p["regra"] for p in mariadb["problemas"]] == ["backup_atrasado"]


def test_banco_ausente_aparece_com_o_problema_mesmo_sem_medida():
    pg = _por_nome(dados_do_papel("banco", [alvo_host_banco()])["itens"])["pg"]
    assert [p["regra"] for p in pg["problemas"]] == ["servico_declarado_ausente"]


def test_banco_do_cluster_nao_ganha_problemas():
    item = dados_do_papel("banco", relatorio_docker()["alvos"])["itens"][0]
    assert "problemas" not in item and item["conexoes"] == 18


def test_busca_traz_as_colecoes():
    item = dados_do_papel("busca", [alvo_host_banco()])["itens"][0]
    assert item["nome"] == "qdrant" and [c["nome"] for c in item["colecoes"]] == ["docs", "faq", "vazia"]


def test_sem_busca_o_bloco_tem_so_o_motivo():
    assert set(dados_do_papel("busca", relatorio_docker()["alvos"])) == {"motivo"}


def test_maquina_do_host_traz_carga_boot_e_problema():
    item = _por_nome(dados_do_papel("maquinas", [alvo_host_banco()])["itens"])["banco-01"]
    assert (item["carga"], item["boot"]) == (24.0, 41.0)
    assert [p["regra"] for p in item["problemas"]] == ["disco_quase_cheio"]


def test_servidores_separa_os_problemas_que_tem_bloco_proprio():
    item = dados_do_papel("servidores", [alvo_host_banco()])["itens"][0]
    assert [p["regra"] for p in item["problemas"]] == ["servico_reiniciando"]
    assert len(item["todos"]) == 4
    assert [s["nome"] for s in item["servicos"]] == ["mariadb", "qdrant", "redis", "pg", "loja-api"]
    pg = _por_nome(item["servicos"])["pg"]
    assert pg["ausente"] is True and pg["ativo"] is None
    assert item["descobertos"] == [{"produto": "postgres", "origem": "unidade:postgresql.service"}]
    assert item["nao_medido"] == []


def test_servidor_sem_vpn_diz_por_que_nao_foi_medido():
    item = dados_do_papel("servidores", [alvo_host_sem_vpn()])["itens"][0]
    assert item["servicos"] == [] and "VPN" in item["nao_medido"][0]


def test_sem_host_nao_ha_servidores():
    assert dados_do_papel("servidores", relatorio_docker()["alvos"]) == {}

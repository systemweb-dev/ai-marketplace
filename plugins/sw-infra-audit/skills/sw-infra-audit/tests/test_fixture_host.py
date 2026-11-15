from tests.fixtures.relatorio_host import alvo_host_banco, relatorio_com_hosts


def test_fixture_host_tem_os_casos_que_o_relatorio_precisa_mostrar():
    alvo = alvo_host_banco()
    regras = sorted(a["regra"] for a in alvo["achados"])
    assert regras == ["backup_atrasado", "disco_quase_cheio", "servico_declarado_ausente", "servico_reiniciando"]
    assert all(a.get("como_resolver") for a in alvo["achados"])
    assert {c["papel"] for c in alvo["componentes"]} == {"maquina", "banco", "busca", "cache", "app"}
    assert alvo["fatos"]["descobertos"] == [{"produto": "postgres", "origem": "unidade:postgresql.service"}]


def test_relatorio_com_hosts_soma_dois_alvos_ao_inventario():
    r = relatorio_com_hosts()
    assert [a["nome"] for a in r["alvos"]] == ["banco-01", "cache-02"]
    assert len(r["inventario"]) == 2 and r["schema_version"] == 3

from lib.estado_servico import contar, estado_de


def svc(replicas, falhas=0, nome="a_b", **extra):
    return {"name": nome, "replicas": replicas, "tasks_failed": falhas, **extra}


def test_estados_da_tabela_do_spec():
    assert estado_de(svc("3/3"), set()) == "online"
    assert estado_de(svc("3/3", falhas=2), set()) == "online"
    assert estado_de(svc("1/3"), set()) == "parcial"
    assert estado_de(svc("0/1"), set()) == "fora"
    assert estado_de(svc("0/0"), set()) == "proposital"
    assert estado_de(svc("0/1", nome="migrate_job", mode="replicated-job"), set()) == "proposital"
    assert estado_de(svc("0/1", falhas=1, nome="migrate_job", mode="replicated-job"), set()) == "fora"
    assert estado_de(svc("0/1"), {"a_b"}) == "proposital"
    assert estado_de(svc(None), set()) == "sem_dado"
    assert estado_de(svc("3/3"), {"a_b"}) == "online"
    assert estado_de(svc("0/2 (max 1 per node)"), set()) == "fora"


def test_contagem_ignora_lista_invalida_do_coletor():
    assert contar({"status": "n/a"}, set())["base"] == 0


def test_contagem_tira_proposital_e_sem_dado_do_denominador():
    r = contar([svc("3/3"), svc("0/1", nome="x"), svc("0/0", nome="y"), svc(None, nome="z")], set())
    assert (r["online"], r["base"], r["fora"]) == (1, 2, 1)


def test_nome_parecido_com_job_nao_tira_servico_em_execucao_da_conta():
    """`is_job_service` casa por substring do nome: `seed` em `x_seed_api` sairia da base."""
    assert estado_de(svc("3/3", nome="x_seed_api"), set()) == "online"
    assert estado_de(svc("1/3", nome="x_seed_api"), set()) == "parcial"


def test_nome_parecido_com_job_parado_continua_fora():
    assert estado_de(svc("0/3", nome="x_seed_api"), set()) == "fora"


def test_job_concluido_sem_modo_de_job_e_proposital():
    assert estado_de(svc("0/1", nome="x_flyway", completed_job=True), set()) == "proposital"


def test_banco_concluido_nao_e_proposital():
    assert estado_de(svc("0/1", completed_job=True, kind="banco"), set()) == "fora"


def test_aceite_sem_objeto_vale_para_o_alvo():
    assert estado_de(svc("0/1"), {None}) == "proposital"


def test_falhas_desconhecidas_nao_escondem_as_replicas():
    assert estado_de(svc("0/1", falhas=None), set()) == "fora"
    assert estado_de(svc("1/3", falhas=None), set()) == "parcial"
    assert estado_de(svc("3/3", falhas=None), set()) == "online"


def test_job_com_falhas_desconhecidas_nao_prova_que_concluiu():
    assert estado_de(svc("0/1", falhas=None, nome="x_seed", mode="replicated-job"), set()) == "fora"


def test_sem_dado_fica_para_replicas_desconhecidas():
    assert estado_de(svc(None, falhas=None), set()) == "sem_dado"


def test_contar_expoe_falhas_desconhecidas_so_de_quem_esta_na_base():
    r = contar([svc("3/3", falhas=None, nome="a"), svc("0/1", falhas=None, nome="b"), svc("3/3", nome="c"),
                svc("0/0", falhas=None, nome="d"), svc(None, falhas=None, nome="e"),
                svc("0/1", falhas=None, nome="f")], {"f"})
    assert r["falhas_desconhecidas"] == 2 and r["base"] == 3


def test_servico_sem_o_campo_nao_conta_como_falha_desconhecida():
    assert contar([{"name": "a", "replicas": "1/1"}], set())["falhas_desconhecidas"] == 0


def test_instavel_saiu_dos_estados():
    from lib.estado_servico import ESTADOS, NA_BASE
    assert "instavel" not in ESTADOS and "instavel" not in NA_BASE


def test_contar_expoe_com_alerta_e_conta_como_online():
    r = contar([svc("3/3", falhas=2, nome="a"), svc("2/2", nome="b"), svc("1/3", falhas=1, nome="c"),
                svc("0/1", falhas=4, nome="d"), svc("3/3", falhas=None, nome="e")], set())
    assert (r["online"], r["com_alerta"], r["parcial"], r["fora"], r["base"]) == (3, 1, 1, 1, 5)
    assert "instavel" not in r

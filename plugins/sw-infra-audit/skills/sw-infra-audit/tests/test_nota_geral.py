from lib.cobertura import teto_por_cobertura
from lib.nota import nota_geral, pontuacoes


def alvo(servicos, dimensoes=None, achados=(), nome="c"):
    return {"nome": nome, "tipo": "docker", "coletado": True, "achados": list(achados),
            "fatos": {"services": servicos}, "dimensoes": dimensoes or {}}


BOM = {"disponibilidade": {"ha_pct": 100}, "seguranca": {"high": 0, "med": 0},
       "higiene": {"pinned_pct": 100, "nonroot_pct": 100, "limits_pct": 100, "healthcheck_pct": 100}}


def test_servico_fora_limita_a_59():
    servicos = [{"name": f"s{i}", "replicas": "1/1"} for i in range(99)]
    servicos.append({"name": "x", "replicas": "0/1"})
    assert nota_geral([alvo(servicos, BOM)], [])["valor"] == 59


def test_no_fora_com_aceite_continua_limitando():
    d = dict(BOM, operacao={"nodes_down": 1})
    assert nota_geral([alvo([{"name": "s", "replicas": "1/1"}], d)], [])["valor"] == 59


def test_parado_com_aceite_vigente_sai_da_conta():
    a = alvo([{"name": "s", "replicas": "1/1"}, {"name": "x", "replicas": "0/1"}], BOM)
    aceites = [{"alvo": "c", "regra": "OPS_SERVICE_STOPPED", "objeto": "x", "vencido": False}]
    r = nota_geral([a], aceites)
    assert (r["online"], r["base"], r["valor"]) == (1, 1, 100)


def test_problema_alto_limita_a_79():
    r = nota_geral([alvo([{"name": "s", "replicas": "1/1"}], BOM,
                         [{"regra": "r", "severidade": "high"}])], [])
    assert r["valor"] == 79 and r["faixa"] == "atencao"


def test_parcela_nao_medida_sai_da_conta():
    r = nota_geral([alvo([{"name": "s", "replicas": "1/1"}])], [])
    assert r["valor"] == 100 and r["parcial"] is True and r["faixa"] == "atencao"


def test_falhas_desconhecidas_com_servico_fora_limitam_a_59():
    servicos = [{"name": f"s{i}", "replicas": "3/3", "tasks_failed": None} for i in range(5)]
    servicos.append({"name": "x", "replicas": "0/1", "tasks_failed": None})
    r = nota_geral([alvo(servicos, BOM)], [])
    assert (r["teto"], r["valor"], r["online"], r["base"]) == (59, 59, 5, 6)
    assert r["parcial"] is True and r["faixa"] == "critico"


def test_falhas_desconhecidas_nao_dao_verde():
    r = nota_geral([alvo([{"name": "s", "replicas": "3/3", "tasks_failed": None}], BOM)], [])
    assert r["valor"] == 100 and r["parcial"] is True and r["faixa"] == "atencao"


def test_sem_servico_medido_nao_ha_nota():
    assert nota_geral([alvo([{"name": "s", "replicas": None}])], []) is None


def test_endpoint_fora_conta_como_servico_fora():
    http = {"nome": "h", "tipo": "http", "coletado": True, "fatos": {"codigo": 503}, "dimensoes": {},
            "achados": [{"regra": "http_fora_do_ar", "severidade": "critical"}]}
    r = nota_geral([alvo([{"name": "s", "replicas": "1/1"}], BOM), http], [])
    assert r["base"] == 2 and r["valor"] <= 59


def test_endpoint_sem_resposta_conta_como_fora():
    http = {"nome": "h", "tipo": "http", "coletado": True, "fatos": {"certificado": {"valor": None}},
            "dimensoes": {}, "achados": []}
    r = nota_geral([alvo([{"name": "s", "replicas": "1/1"}], BOM), http], [])
    assert r["online"] == 1 and r["base"] == 2 and r["valor"] <= 59


def test_aceite_sem_objeto_vale_para_o_alvo_inteiro():
    a = alvo([{"name": "x", "replicas": "0/1"}, {"name": "s", "replicas": "1/1"}], BOM)
    r = nota_geral([a], [{"alvo": "c", "regra": "OPS_SERVICE_STOPPED", "vencido": False}])
    assert r["teto"] is None


def test_trava_de_cobertura_impede_o_verde():
    a = alvo([{"name": "s", "replicas": "1/1"}], BOM)
    a["trava_cobertura"] = True
    assert nota_geral([a], [])["faixa"] == "atencao"


def test_dimensao_sem_dado_do_coletor_nao_vira_pontuacao():
    desconhecida = {"note": "unknown"}
    pts = pontuacoes({"disponibilidade": desconhecida, "seguranca": desconhecida})
    assert pts["disponibilidade"] is None and pts["seguranca"] is None


def _alvo_com_pergunta_muda(saude):
    return {"saude": saude, "componentes": [{"nome": "b", "papel": "fila", "respostas": []}]}


def test_pergunta_muda_grava_a_trava_mesmo_sem_mudar_a_saude():
    amarelo, sem_dados = _alvo_com_pergunta_muda("🟡"), _alvo_com_pergunta_muda("sem dados")
    teto_por_cobertura(amarelo)
    teto_por_cobertura(sem_dados)
    assert amarelo["trava_cobertura"] is True and sem_dados["trava_cobertura"] is True
    assert sem_dados["saude"] == "sem dados"


def test_endpoint_5xx_com_aceite_continua_fora():
    http = {"nome": "h", "tipo": "http", "coletado": True, "fatos": {"codigo": 503},
            "dimensoes": {}, "achados": []}
    assert nota_geral([http], [])["teto"] == 59


def test_aceite_por_componente_nao_casa_achado_de_alvo():
    a = alvo([{"name": "x", "replicas": "0/1"}, {"name": "s", "replicas": "1/1"}], BOM)
    r = nota_geral([a], [{"alvo": "c", "regra": "OPS_SERVICE_STOPPED", "componente": "x", "vencido": False}])
    assert r["base"] == 2 and r["teto"] == 59


def test_aceite_vencido_nao_tira_da_conta():
    a = alvo([{"name": "x", "replicas": "0/1"}, {"name": "s", "replicas": "1/1"}], BOM)
    r = nota_geral([a], [{"alvo": "c", "regra": "OPS_SERVICE_STOPPED", "objeto": "x", "vencido": True}])
    assert r["base"] == 2 and r["teto"] == 59


def test_erro_interno_do_coletor_nao_vira_servico_fora():
    http = {"nome": "h", "tipo": "http", "coletado": True, "fatos": {}, "dimensoes": {}, "achados": [],
            "erro_interno": True}
    r = nota_geral([alvo([{"name": "s", "replicas": "1/1"}], BOM), http], [])
    assert (r["base"], r["teto"], r["parcial"], r["faixa"]) == (1, None, True, "atencao")


def test_alvo_docker_sem_servicos_marca_parcial():
    r = nota_geral([alvo([{"name": "s", "replicas": "1/1"}], BOM), alvo([], nome="d")], [])
    assert r["parcial"] is True and r["faixa"] == "atencao"


def test_critical_limita_a_79():
    r = nota_geral([alvo([{"name": "s", "replicas": "1/1"}], BOM,
                         [{"regra": "r", "severidade": "critical"}])], [])
    assert r["valor"] == 79


def test_parcial_limita_a_79():
    r = nota_geral([alvo([{"name": "a", "replicas": "1/2"}, {"name": "s", "replicas": "1/1"}], dict(BOM))], [])
    assert r["teto"] == 79


def test_alerta_nao_tem_teto_e_fica_gravado():
    servicos = [{"name": "a", "replicas": "1/1", "tasks_failed": 3}, {"name": "s", "replicas": "1/1"}]
    r = nota_geral([alvo(servicos, BOM)], [])
    assert (r["teto"], r["valor"], r["online"], r["base"], r["com_alerta"]) == (None, 100, 2, 2, 1)


def test_pendencias_sao_os_pontos_que_faltam_em_cada_parcela():
    d = dict(BOM, disponibilidade={"ha_pct": 39})
    r = nota_geral([alvo([{"name": "s", "replicas": "1/2"}, {"name": "t", "replicas": "1/1"}], d)], [])
    assert r["pendencias"] == {"online": 50, "estabilidade": 61, "praticas": 0}


def test_parcela_nao_medida_nao_tem_pendencia_inventada():
    r = nota_geral([alvo([{"name": "s", "replicas": "1/1"}])], [])
    assert r["pendencias"] == {"online": 0, "estabilidade": None, "praticas": None}


def test_limites_guardam_a_causa_de_cada_teto():
    d = dict(BOM, operacao={"nodes_down": 1})
    servicos = [{"name": "a", "replicas": "0/1"}, {"name": "b", "replicas": "1/2"}, {"name": "c", "replicas": "1/1"}]
    achados = [{"regra": "SEC_Z", "severidade": "high"}, {"regra": "SEC_A", "severidade": "critical"},
               {"regra": "SEC_A", "severidade": "high"}, {"regra": "SEC_M", "severidade": "medium"}]
    r = nota_geral([alvo(servicos, d, achados)], [])
    assert r["limites"] == {"fora": 1, "parciais": 1, "nos_fora": 1, "altos": 3, "regras_altas": ["SEC_A", "SEC_Z"]}


def test_pesos_exatos_70_20_10():
    d = {"disponibilidade": {"ha_pct": 50},
         "seguranca": {"high": 0, "med": 100},
         "higiene": {"pinned_pct": 0, "nonroot_pct": 0, "limits_pct": 0, "healthcheck_pct": 0}}
    assert nota_geral([alvo([{"name": "s", "replicas": "1/1"}], d)], [])["valor"] == 80


def test_limiar_do_endpoint_e_500():
    base = {"nome": "h", "tipo": "http", "coletado": True, "dimensoes": {}, "achados": []}
    assert nota_geral([{**base, "fatos": {"codigo": 499}}], [])["online"] == 1
    assert nota_geral([{**base, "fatos": {"codigo": 500}}], [])["online"] == 0

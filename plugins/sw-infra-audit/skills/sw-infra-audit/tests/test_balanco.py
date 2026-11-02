from lib.balanco import pontos


def alvo(**dimensoes):
    return {"nome": "c", "componentes": [], "dimensoes": dimensoes}


def test_medidas_viram_positivos_e_atencao():
    a = alvo(operacao={"nodes_down": 0}, seguranca={"high": 0},
             disponibilidade={"ha_pct": 39, "spof_stateful": ["db", "fila"]}, higiene={"healthcheck_pct": 19, "limits_pct": 80})
    bons, ruins = pontos([a], {"online": 5, "base": 5, "com_alerta": 2, "limites": {"altos": 1}})
    assert "5 de 5 serviços online." in bons and "Nenhuma máquina fora do cluster." in bons
    assert "80% dos serviços têm limite de CPU e memória." in bons
    assert "39% dos serviços têm réplica de reserva." in ruins
    assert "2 serviços com dados não têm réplica de reserva." in ruins
    assert "19% dos serviços têm verificação de saúde." in ruins
    assert "2 serviços online com alerta de falhas recentes." in ruins
    assert "1 ocorrência de gravidade alta para agir agora." in ruins


def test_o_que_nao_foi_medido_nao_vira_ponto():
    assert pontos([alvo()], None) == ([], [])


def test_alvo_fora_da_rodada_nao_conta():
    a = dict(alvo(operacao={"nodes_down": 0}), coletado=False)
    assert pontos([a], {}) == ([], [])


def test_servico_fora_do_ar_e_ponto_de_atencao():
    bons, ruins = pontos([alvo()], {"online": 4, "base": 5})
    assert not bons and "4 de 5 serviços online." in ruins


def test_o_agente_acrescenta_sem_substituir():
    bons, ruins = pontos([alvo()], {"online": 1, "base": 1}, ["Backup testado"], ["Plano de resposta ausente"])
    assert bons == ["1 de 1 serviços online.", "Backup testado"] and ruins == ["Plano de resposta ausente"]


def test_varios_alvos_dizem_de_quem_e():
    a, b = alvo(operacao={"nodes_down": 0}), dict(alvo(operacao={"nodes_down": 0}), nome="d")
    assert "d: Nenhuma máquina fora do cluster." in pontos([a, b], {})[0]


def test_disco_estavel_nao_vira_ponto_de_atencao():
    componentes = [{"nome": "n", "papel": "maquina", "respostas": [{"pergunta": "maquina.disco_dias", "valor": v, "fonte": "f"}]}
                   for v in (-1, 24)]
    a = dict(alvo(), componentes=componentes)
    assert pontos([a], {})[1] == ["O disco de n enche em 24 dias, se o ritmo continuar."]

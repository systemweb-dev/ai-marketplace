# tests/test_limiar_vira_achado.py
"""A ponte entre insight e achado.

O campo `limiar` existe no registro de perguntas desde o plano 1 e nada nunca o avaliou: a
skill colecionava respostas e nenhuma delas virava achado. Esta é a primeira regra que nasce de
uma medida em vez de nascer de uma inspeção de configuração.
"""
from collect import achados_da_resposta


def _resposta(valor):
    return {"pergunta": "fila.filas", "fonte": "admin_http:amqp-mgmt",
            "valor": valor}


# A regra precisa existir em `lib/regras.py` — `fila_sem_consumidor` entra na Task 8, e um
# teste desta task não pode depender da seguinte. `OPS_NODE_DOWN` já está registrada.
LIMIAR = {"quando": "consumidores == 0 e prontas > 0",
          "regra": "OPS_NODE_DOWN", "severidade": "high"}


def test_item_que_cruza_o_limiar_vira_achado():
    resposta = _resposta([{"nome": "emails", "prontas": 7, "consumidores": 0}])

    achados = achados_da_resposta(resposta, LIMIAR, componente="broker")

    assert len(achados) == 1
    assert achados[0]["regra"] == "OPS_NODE_DOWN"
    assert achados[0]["severidade"] == "high"


def test_o_objeto_do_achado_identifica_o_item():
    """Sem o objeto, 30 filas com acúmulo viram 30 achados indistinguíveis — e o agrupamento
    do relatório (v0.8.0) mostraria 30 linhas iguais."""
    resposta = _resposta([{"nome": "emails", "prontas": 7, "consumidores": 0}])

    achados = achados_da_resposta(resposta, LIMIAR, componente="broker")

    assert achados[0]["objeto"] == "emails"


def test_item_que_nao_cruza_nao_vira_achado():
    resposta = _resposta([{"nome": "pedidos", "prontas": 42, "consumidores": 3}])

    assert achados_da_resposta(resposta, LIMIAR, componente="broker") == []


def test_cada_item_que_cruza_gera_o_seu():
    resposta = _resposta([{"nome": "a", "prontas": 1, "consumidores": 0},
                          {"nome": "b", "prontas": 2, "consumidores": 2},
                          {"nome": "c", "prontas": 3, "consumidores": 0}])

    achados = achados_da_resposta(resposta, LIMIAR, componente="broker")

    assert [a["objeto"] for a in achados] == ["a", "c"]


def test_resposta_sem_dados_nunca_vira_achado():
    """A regra mais importante da skill: achado nasce de fato presente, nunca de ausência."""
    resposta = {"pergunta": "fila.filas", "sem_dados": True,
                "motivo": "a API não respondeu"}

    assert achados_da_resposta(resposta, LIMIAR, componente="broker") == []


def test_sem_dados_com_valor_residual_tambem_nao_vira_achado():
    """O caso que a versão anterior deste teste NÃO cobria, e por isso a trava era decorativa.

    Com `valor = None`, o parser de limiar já recusa sozinho — então remover a guarda de
    `sem_dados` não derrubava teste nenhum. A guarda só existe de verdade para a resposta
    MISTA: um adaptador que marca `sem_dados` e deixa um valor parcial para trás. Sem ela,
    dado residual de uma coleta que falhou viraria achado.
    """
    resposta = {"pergunta": "fila.filas", "sem_dados": True,
                "motivo": "a API respondeu pela metade",
                "valor": [{"nome": "emails", "prontas": 7, "consumidores": 0}]}

    assert achados_da_resposta(resposta, LIMIAR, componente="broker") == []


def test_erro_interno_nunca_vira_achado():
    resposta = {"pergunta": "fila.filas", "erro_interno": True,
                "motivo": "admin_http: KeyError: x"}

    assert achados_da_resposta(resposta, LIMIAR, componente="broker") == []


def test_erro_interno_com_valor_residual_tambem_nao_vira_achado():
    """Mesma coisa pelo outro lado: o adaptador estourou no meio e deixou o que já tinha."""
    resposta = {"pergunta": "fila.filas", "erro_interno": True,
                "motivo": "admin_http: KeyError: x",
                "valor": [{"nome": "emails", "prontas": 7, "consumidores": 0}]}

    assert achados_da_resposta(resposta, LIMIAR, componente="broker") == []


def test_sem_limiar_declarado_nao_ha_achado():
    resposta = _resposta([{"nome": "a", "prontas": 1, "consumidores": 0}])

    assert achados_da_resposta(resposta, None, componente="broker") == []


def test_detalhe_do_achado_cita_os_numeros():
    resposta = _resposta([{"nome": "emails", "prontas": 7, "consumidores": 0}])

    achados = achados_da_resposta(resposta, LIMIAR, componente="broker")

    assert "7" in achados[0]["detalhe"]


def test_o_detalhe_nao_repete_o_nome_que_ja_e_o_objeto():
    resposta = _resposta([{"nome": "emails", "prontas": 7, "consumidores": 0}])

    achados = achados_da_resposta(resposta, LIMIAR, componente="broker")

    assert "emails" not in achados[0]["detalhe"]


def test_expressao_invalida_nao_derruba_a_coleta():
    """Arquivo de catálogo errado é bug da skill, e bug da skill não pode apagar o inventário
    de um alvo inteiro."""
    resposta = _resposta([{"nome": "a", "prontas": 1, "consumidores": 0}])
    quebrado = dict(LIMIAR, quando="prontas / consumidores > 2")

    assert achados_da_resposta(resposta, quebrado, componente="broker") == []


def test_limiar_sem_regra_nao_gera_achado_anonimo():
    """Achado sem regra não acha remediação e não entra no agrupamento do relatório."""
    resposta = _resposta([{"nome": "a", "prontas": 1, "consumidores": 0}])

    assert achados_da_resposta(resposta, {"quando": "prontas > 0"}, componente="broker") == []


def test_escalar_tambem_pode_cruzar_limiar():
    """Nem toda pergunta é lista: um escalar compara contra o campo `valor`.

    Nenhuma pergunta do papel `fila` usa este caminho nesta versão — ele existe porque os
    planos 3 e 4 trazem escalares com limiar, e uma ponte que só funciona para lista viraria
    surpresa lá na frente.
    """
    resposta = {"pergunta": "papel.escalar", "fonte": "admin_http:exemplo", "valor": 900}
    limiar = {"quando": "valor > 0", "regra": "OPS_NODE_DRAIN", "severidade": "medium"}

    achados = achados_da_resposta(resposta, limiar, componente="broker")

    assert len(achados) == 1 and achados[0]["objeto"] == "broker"


def test_severidade_ausente_cai_no_padrao_da_regra():
    """Dois lugares declaram severidade; quando o catálogo cala, quem manda é o registro."""
    resposta = _resposta([{"nome": "a", "prontas": 1, "consumidores": 0}])
    sem_severidade = {"quando": "consumidores == 0 e prontas > 0",
                      "regra": "SEC_USER_ROOT"}

    achados = achados_da_resposta(resposta, sem_severidade, componente="broker")

    assert achados[0]["severidade"] == "medium"    # a padrão de SEC_USER_ROOT em lib/regras.py


def test_a_resposta_nao_e_modificada():
    """A resposta vai para o report.json; o cálculo do achado não pode sujá-la."""
    resposta = _resposta([{"nome": "a", "prontas": 1, "consumidores": 0}])
    antes = repr(resposta)

    achados_da_resposta(resposta, LIMIAR, componente="broker")

    assert repr(resposta) == antes

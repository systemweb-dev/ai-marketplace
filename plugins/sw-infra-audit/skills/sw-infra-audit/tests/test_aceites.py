# tests/test_aceites.py
from lib.aceites import aplicar

HOJE = "2026-09-19"


def achado(regra="sem_replica", alvo="banco", objeto="principal"):
    return {"regra": regra, "objeto": objeto, "severidade": "high", "alvo": alvo}


def aceite(**extra):
    base = {"alvo": "banco", "regra": "sem_replica", "motivo": "base de cache",
            "desde": "2026-01-01", "revisar_em": "2027-01-01", "origem": "projeto"}
    base.update(extra)
    return base


def test_achado_aceito_sai_dos_achados_e_vai_para_a_lista():
    alvos = [{"nome": "banco", "achados": [achado()]}]

    aceitos = aplicar(alvos, [aceite()], hoje=HOJE)

    assert alvos[0]["achados"] == []
    assert aceitos[0]["regra"] == "sem_replica" and aceitos[0]["origem"] == "projeto"
    assert aceitos[0]["motivo"] == "base de cache"


def test_aceite_de_outro_alvo_nao_vale():
    alvos = [{"nome": "banco", "achados": [achado()]}]

    aceitos = aplicar(alvos, [aceite(alvo="cluster")], hoje=HOJE)

    assert len(alvos[0]["achados"]) == 1 and aceitos == []


def test_aceite_vencido_nao_silencia_e_marca_o_achado():
    alvos = [{"nome": "banco", "achados": [achado()]}]

    aceitos = aplicar(alvos, [aceite(revisar_em="2026-01-01")], hoje=HOJE)

    assert len(alvos[0]["achados"]) == 1
    assert alvos[0]["achados"][0]["aceite_vencido"] is True
    assert aceitos[0]["vencido"] is True


def test_aceite_sem_data_de_revisao_vale_mas_fica_marcado():
    alvos = [{"nome": "banco", "achados": [achado()]}]

    aceitos = aplicar(alvos, [aceite(revisar_em=None)], hoje=HOJE)

    assert alvos[0]["achados"] == []
    assert aceitos[0]["revisar_em"] is None


def test_projeto_vence_infra_quando_os_dois_existem():
    alvos = [{"nome": "banco", "achados": [achado()]}]

    aceitos = aplicar(alvos, [aceite(origem="infra", motivo="decisão de infra"),
                              aceite(origem="projeto", motivo="decisão do produto")], hoje=HOJE)

    assert len(aceitos) == 1
    assert aceitos[0]["origem"] == "projeto" and aceitos[0]["sobrepoe"] == "infra"


def test_aceite_pode_mirar_um_objeto_especifico():
    alvos = [{"nome": "banco", "achados": [achado(objeto="principal"), achado(objeto="relatorios")]}]

    aplicar(alvos, [aceite(objeto="principal")], hoje=HOJE)

    assert [a["objeto"] for a in alvos[0]["achados"]] == ["relatorios"]


def test_aceite_que_nao_casa_com_nada_e_reportado_como_obsoleto():
    alvos = [{"nome": "banco", "achados": []}]

    aceitos = aplicar(alvos, [aceite()], hoje=HOJE)

    assert aceitos[0]["obsoleto"] is True, "o problema sumiu: a justificativa não é mais necessária"


import pytest


@pytest.mark.parametrize("data", ["31/12/2026", "2026-13-01", "amanhã", ""])
def test_data_de_revisao_fora_do_formato_e_recusada(data):
    """Comparação de texto: "31/12/2026" nunca vencia e "19/09/2026" vencia sempre."""
    alvos = [{"nome": "banco", "achados": [achado()], "coletado": True}]

    with pytest.raises(ValueError):
        aplicar(alvos, [aceite(revisar_em=data)], hoje=HOJE)


def test_aceite_de_alvo_que_nao_foi_coletado_nao_vira_obsoleto():
    """Sem achados porque ninguém coletou ≠ o problema acabou. Marcar obsoleto faria o usuário
    apagar uma justificativa que continua válida."""
    alvos = [{"nome": "banco", "achados": [], "coletado": False}]

    aceitos = aplicar(alvos, [aceite()], hoje=HOJE)

    assert aceitos[0]["obsoleto"] is False


def test_aceite_sem_alvo_e_recusado():
    with pytest.raises(ValueError):
        aplicar([{"nome": "banco", "achados": [], "coletado": True}], [aceite(alvo=None)], hoje=HOJE)


def test_aceite_com_componente_so_apaga_o_achado_daquele_componente():
    """Duas filas com o mesmo problema: aceitar o risco de uma não pode silenciar a outra."""
    def achado(componente):
        return {"regra": "fila_sem_consumidor", "alvo": "cluster", "componente": componente}

    alvos = [{"nome": "cluster", "coletado": True,
              "achados": [achado("fila_a"), achado("fila_b")],
              "componentes": [{"nome": "fila_a", "achados": [achado("fila_a")]},
                              {"nome": "fila_b", "achados": [achado("fila_b")]}]}]

    saida = aplicar(alvos, [{"alvo": "cluster", "componente": "fila_a",
                                     "regra": "fila_sem_consumidor",
                                     "motivo": "fila de rascunho", "origem": "projeto"}],
                            hoje="2026-09-19")

    assert [a["componente"] for a in alvos[0]["achados"]] == ["fila_b"]
    assert alvos[0]["componentes"][0]["achados"] == []
    assert len(alvos[0]["componentes"][1]["achados"]) == 1
    assert saida[0]["obsoleto"] is False


def test_aceite_sem_componente_continua_valendo_para_o_alvo_inteiro():
    def achado(componente):
        return {"regra": "r", "alvo": "cluster", "componente": componente}

    alvos = [{"nome": "cluster", "coletado": True,
              "achados": [achado("a"), achado("b")],
              "componentes": [{"nome": "a", "achados": [achado("a")]},
                              {"nome": "b", "achados": [achado("b")]}]}]

    aplicar(alvos, [{"alvo": "cluster", "regra": "r", "motivo": "m", "origem": "infra"}],
                    hoje="2026-09-19")

    assert alvos[0]["achados"] == []
    assert all(c["achados"] == [] for c in alvos[0]["componentes"])

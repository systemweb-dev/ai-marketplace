"""O mesmo problema contado como serviço E como container infla o número que a pessoa lê.

O coletor varre os dois níveis: serviços com `scope="cluster-wide"` e containers com o nome
do nó. Um container herda a configuração do serviço, então `SEC_USER_ROOT` nasce duas vezes
para a mesma causa. Numa rodada real isso eram 23 achados de 212 — e a remediação dos dois é
a mesma: você conserta o SERVIÇO.

O que NÃO pode acontecer é perder o achado de container que o serviço não tem: container que
divergiu da especificação é informação nova, não repetição.
"""
from lib.coletores.docker import _para_achados_do_relatorio


def bruto(rule_id, objeto, scope, expected=False):
    return {"rule_id": rule_id, "object": objeto, "severity": "med",
            "evidence": "x", "fix": "y", "scope": scope, "expected": expected}


def test_container_que_repete_o_servico_nao_conta_de_novo():
    brutos = [bruto("SEC_USER_ROOT", "loja_api", "cluster-wide"),
              bruto("SEC_USER_ROOT", "loja_api.1.vsf7k2m9xq3b", "no-1")]

    achados = _para_achados_do_relatorio(brutos)

    assert len(achados) == 1
    assert achados[0]["objeto"] == "loja_api", "fica o nível em que se conserta"


def test_container_com_problema_que_o_servico_nao_tem_e_mantido():
    """Container que divergiu da especificação do serviço é achado novo, não repetição."""
    brutos = [bruto("SEC_USER_ROOT", "loja_api", "cluster-wide"),
              bruto("SEC_PRIVILEGED", "loja_api.1.vsf7k2m9xq3b", "no-1")]

    achados = _para_achados_do_relatorio(brutos)

    assert len(achados) == 2
    assert {a["regra"] for a in achados} == {"SEC_USER_ROOT", "SEC_PRIVILEGED"}


def test_container_de_servico_sem_achado_nenhum_e_mantido():
    brutos = [bruto("SEC_USER_ROOT", "orfao_x.2.abcdefghij12", "no-1")]

    assert len(_para_achados_do_relatorio(brutos)) == 1


def test_dois_containers_do_mesmo_servico_contam_uma_vez_so():
    """Três réplicas do mesmo serviço com o mesmo problema são UM problema."""
    brutos = [bruto("SEC_USER_ROOT", "loja_api.1.aaaaaaaaaa11", "no-1"),
              bruto("SEC_USER_ROOT", "loja_api.2.bbbbbbbbbb22", "no-2"),
              bruto("SEC_USER_ROOT", "loja_api.3.cccccccccc33", "no-3")]

    achados = _para_achados_do_relatorio(brutos)

    assert len(achados) == 1
    assert achados[0]["objeto"] == "loja_api", "o objeto vira o serviço, que é onde se conserta"


def test_a_marca_esperada_sobrevive_a_deduplicacao():
    brutos = [bruto("SEC_DOCKER_SOCK_EXPECTED", "traefik", "cluster-wide", expected=True),
              bruto("SEC_DOCKER_SOCK_EXPECTED", "traefik.1.zzzzzzzzzz99", "no-1", expected=True)]

    achados = _para_achados_do_relatorio(brutos)

    assert len(achados) == 1 and achados[0]["esperada"] is True


def test_servicos_diferentes_nao_se_fundem():
    brutos = [bruto("SEC_USER_ROOT", "loja_api", "cluster-wide"),
              bruto("SEC_USER_ROOT", "loja_web", "cluster-wide")]

    assert len(_para_achados_do_relatorio(brutos)) == 2

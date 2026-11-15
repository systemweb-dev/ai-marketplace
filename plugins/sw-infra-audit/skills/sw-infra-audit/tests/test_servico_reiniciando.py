from lib import limites_produto, regras, remediacao
from lib.rule_meta import meta


def _comp(reinicios):
    return {"nome": "mariadb", "respostas": [
        {"pergunta": "servico.reinicios", "valor": reinicios, "fonte": "ssh"}]}


def test_cinco_reinicios_viram_achado_medio():
    achados = limites_produto.achados(_comp(5))
    assert [(a["regra"], a["severidade"], a["objeto"], a["valor"]) for a in achados] == \
        [("servico_reiniciando", "medium", "mariadb", 5)]


def test_quatro_reinicios_nao_viram_achado():
    assert limites_produto.achados(_comp(4)) == []


def test_reinicio_sem_dado_nao_vira_achado():
    comp = {"nome": "mariadb", "respostas": [{"pergunta": "servico.reinicios", "sem_dados": True}]}
    assert limites_produto.achados(comp) == []


def test_regra_registrada_com_produtor_e_remediacao():
    assert regras.REGRAS["servico_reiniciando"] == {"severidade_padrao": "medium", "origem": "produto",
                                                     "esperada": False}
    assert "servico_reiniciando" in limites_produto.REGRAS_PRODUZIDAS
    assert remediacao.para("servico_reiniciando")["titulo"] == "Serviço reiniciando repetidamente"


def test_regras_de_host_tem_rotulo_proprio():
    for regra in ("servico_declarado_ausente", "SEC_BIND_ALL_INTERFACES", "backup_atrasado",
                  "conexoes_no_limite", "servico_reiniciando"):
        assert meta(regra)["label"] != regra, regra

from lib import limites_produto


def _banco(respostas, **campos):
    return {"nome": "mariadb", "papel": "banco", **campos,
            "respostas": [{"pergunta": p, "fonte": "ssh:mariadb", "valor": v}
                          for p, v in respostas.items()]}


def test_backup_acima_do_limite_padrao_e_high():
    assert limites_produto.achados(_banco({"banco.backup_idade": 3})) == [{
        "regra": "backup_atrasado", "severidade": "high", "objeto": "mariadb", "valor": 3,
        "detalhe": "backup mais novo com 3 dias; o limite é 2"}]


def test_backup_no_limite_ou_semanal_declarado_nao_acusa():
    assert limites_produto.achados(_banco({"banco.backup_idade": 2})) == []
    assert limites_produto.achados(_banco({"banco.backup_idade": 6}, backup_max_dias=7)) == []
    assert limites_produto.achados(_banco({"banco.backup_idade": 8}, backup_max_dias=7))[0][
        "detalhe"] == "backup mais novo com 8 dias; o limite é 7"


def test_conexoes_acima_de_80_por_cento_e_medium():
    assert limites_produto.achados(_banco({"banco.uso_de_conexoes": 85.71})) == [{
        "regra": "conexoes_no_limite", "severidade": "medium", "objeto": "mariadb",
        "valor": 85.71, "detalhe": "85.71% das conexões permitidas em uso"}]
    assert limites_produto.achados(_banco({"banco.uso_de_conexoes": 80})) == []


def test_sem_dados_e_valor_que_nao_e_numero_nunca_viram_achado():
    sem = {"nome": "mariadb", "papel": "banco", "respostas": [
        {"pergunta": "banco.backup_idade", "sem_dados": True, "motivo": "a pasta está vazia",
         "valor": 99}]}
    assert limites_produto.achados(sem) == []
    assert limites_produto.achados(_banco({"banco.backup_idade": True})) == []
    assert limites_produto.achados(_banco({"banco.uso_de_conexoes": "90"})) == []

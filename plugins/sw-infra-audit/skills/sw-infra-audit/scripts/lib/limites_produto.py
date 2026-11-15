"""Achados de produto em host: backup atrasado, conexões no limite e serviço reiniciando.

No molde de `lib/capacidade.py`: as perguntas são opcionais (o catálogo recusa limiar em opcional), e
só resposta COM número produz achado. Pasta vazia, leitura que falhou ou banco sem `backup_pasta`
nunca viram `backup_atrasado`: "não consegui ver" não é "está atrasado".
"""
import math

BACKUP_MAX_DIAS_PADRAO = 2
LIMITE_DE_CONEXOES = 80
LIMITE_DE_REINICIOS = 5
REGRAS_PRODUZIDAS = {"backup_atrasado", "conexoes_no_limite", "servico_reiniciando"}


def _medida(componente, pergunta):
    for resposta in componente.get("respostas", []):
        valor = resposta.get("valor")
        if resposta.get("pergunta") == pergunta and not resposta.get("sem_dados") \
                and type(valor) in (int, float) and math.isfinite(valor):
            return valor
    return None


def achados(componente):
    saida = []
    idade = _medida(componente, "banco.backup_idade")
    maximo = componente.get("backup_max_dias") or BACKUP_MAX_DIAS_PADRAO
    if idade is not None and idade > maximo:
        saida.append({"regra": "backup_atrasado", "severidade": "high", "objeto": componente["nome"],
                      "valor": idade, "detalhe": f"backup mais novo com {idade} dias; o limite é {maximo}"})
    uso = _medida(componente, "banco.uso_de_conexoes")
    if uso is not None and uso > LIMITE_DE_CONEXOES:
        saida.append({"regra": "conexoes_no_limite", "severidade": "medium",
                      "objeto": componente["nome"], "valor": uso,
                      "detalhe": f"{uso}% das conexões permitidas em uso"})
    reinicios = _medida(componente, "servico.reinicios")
    if reinicios is not None and reinicios >= LIMITE_DE_REINICIOS:
        saida.append({"regra": "servico_reiniciando", "severidade": "medium",
                      "objeto": componente["nome"], "valor": reinicios,
                      "detalhe": f"{round(reinicios)} reinícios registrados pelo gerenciador do serviço"})
    return saida

"""Pontos positivos e de atenção. A base sai das medidas; o agente só acrescenta."""
from lib.dados_blocos import dados_do_papel
from lib.html_comum import plural
from lib.perguntas import PERGUNTAS

MINIMO_DE_PRATICA = 50
DIAS_DE_DISCO = 30
FAIXA = PERGUNTAS["entrada.latencia"]["faixa"]
PRATICAS = (("healthcheck_pct", "têm verificação de saúde"), ("limits_pct", "têm limite de CPU e memória"),
            ("nonroot_pct", "rodam sem usuário root"), ("pinned_pct", "usam imagem de versão fixa"))


def _do_alvo(alvo, prefixo, bons, ruins):
    dimensoes = alvo.get("dimensoes") or {}
    operacao, seguranca = dimensoes.get("operacao") or {}, dimensoes.get("seguranca") or {}
    disponibilidade, praticas = dimensoes.get("disponibilidade") or {}, dimensoes.get("higiene") or {}
    if operacao.get("nodes_down") == 0:
        bons.append(f"{prefixo}Nenhuma máquina fora do cluster.")
    if seguranca.get("high") == 0:
        bons.append(f"{prefixo}Nenhum achado de segurança de gravidade alta.")
    ha = disponibilidade.get("ha_pct")
    if ha is not None:
        (bons if ha >= MINIMO_DE_PRATICA else ruins).append(f"{prefixo}{ha}% dos serviços têm réplica de reserva.")
    sem_copia = len(disponibilidade.get("spof_stateful") or [])
    if sem_copia:
        ruins.append(f"{prefixo}{sem_copia} serviços com dados não têm réplica de reserva.")
    for chave, texto in PRATICAS:
        valor = praticas.get(chave)
        if valor is not None:
            (bons if valor >= MINIMO_DE_PRATICA else ruins).append(f"{prefixo}{valor}% dos serviços {texto}.")


def _das_medidas(alvos, bons, ruins):
    for item in dados_do_papel("entrada", alvos).get("itens") or []:
        latencia = item.get("latencia")
        if latencia is not None and latencia <= FAIXA["bom_ate"]:
            bons.append(f"Tempo de resposta de {round(latencia)} ms, dentro da faixa boa.")
        elif latencia is not None:
            ruins.append(f"Tempo de resposta de {round(latencia)} ms, acima da faixa boa.")
    for item in dados_do_papel("maquinas", alvos).get("itens") or []:
        dias = item.get("dias")
        if dias is not None and 0 <= dias <= DIAS_DE_DISCO:   # negativo é disco estável
            ruins.append(f"O disco de {item.get('nome')} enche em {round(dias)} dias, se o ritmo continuar.")


def pontos(alvos, nota, fortes=(), fracos=()):
    """(positivos, atenção). Só afirma o que foi medido: dado ausente não vira ponto nenhum."""
    bons, ruins = [], []
    nota = nota or {}
    if nota.get("base"):
        linha = f"{nota.get('online')} de {nota['base']} serviços online."
        (bons if nota.get("online") == nota["base"] else ruins).append(linha)
    if nota.get("com_alerta"):
        ruins.append(f"{nota['com_alerta']} serviços online com alerta de falhas recentes.")
    altos = (nota.get("limites") or {}).get("altos")
    if altos:
        ruins.append(f"{plural(altos, 'ocorrência', 'ocorrências')} de gravidade alta para agir agora.")
    coletados = [a for a in alvos if a.get("coletado") is not False]
    for alvo in coletados:
        _do_alvo(alvo, f"{alvo.get('nome')}: " if len(coletados) > 1 else "", bons, ruins)
    _das_medidas(coletados, bons, ruins)
    return bons + [i for i in fortes or [] if i], ruins + [i for i in fracos or [] if i]

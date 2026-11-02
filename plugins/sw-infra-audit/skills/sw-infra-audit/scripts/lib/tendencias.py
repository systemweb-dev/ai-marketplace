"""As séries de 24 horas da capa. As consultas moram nos arquivos de família, como toda série."""
from lib import catalogo, report
from lib.adaptadores import promql


def consultas():
    return {t["nome"]: t["query"] for familia in catalogo.familias()
            for t in familia.get("tendencia", [])}


def coletar_tendencias(alvo, at, timeout, prazo=None, nao_coletado=None):
    """Uma série por nome. A que não veio fica `None`, para o cartão dizer "não medido" em vez de
    sumir, e o motivo vai para `nao_coletado`."""
    if not alvo.get("metricas_url"):
        return {}
    base = promql.base_de(alvo["metricas_url"])
    fim = promql.momento(at)
    faltas = [] if nao_coletado is None else nao_coletado
    saida = {}
    for nome, query in sorted(consultas().items()):
        saida[nome] = None
        if prazo is not None and prazo.esgotado():
            faltas.append(report.na(f"tendência {nome}: {prazo.motivo()}"))
            continue
        limite = timeout if prazo is None else prazo.timeout(timeout)
        valores = promql.serie(base, query, fim, limite)
        if valores:
            saida[nome] = valores
        else:
            faltas.append(report.na(f"tendência {nome}: a fonte não devolveu a série de 24 horas"))
    return saida

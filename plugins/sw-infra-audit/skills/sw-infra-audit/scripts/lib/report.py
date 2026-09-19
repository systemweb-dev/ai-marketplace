"""Schema do report.json v2: o ALVO no centro.

Diferença essencial para o v1: não existe mais um cluster no topo. O topo é a lista de alvos,
mais o inventário (o mapa), os aceites e o histórico. Os quatro campos do agente (`resumo`,
`fortes`, `fracos`, `recomendacoes`) e o `analise` de cada alvo nascem vazios — é o script que
grava os fatos, e o agente que escreve a interpretação por cima.
"""
SCHEMA_VERSION = 2

SEVERIDADES = ("critical", "high", "medium", "low", "info")
_PESO = {nome: posicao for posicao, nome in enumerate(SEVERIDADES)}


def novo(generated_at):
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "alvos": [],
        "inventario": [],
        "aceites": [],
        "historico": None,
        # do agente:
        "resumo": "",
        "fortes": [],
        "fracos": [],
        "recomendacoes": [],
    }


def novo_alvo(nome, tipo, onde):
    """`onde` é o texto que identifica o alvo no relatório (context, URL, host:porta)."""
    return {
        "nome": nome, "tipo": tipo, "onde": onde,
        "saude": "sem dados",
        "dimensoes": {},
        "fatos": {},
        "achados": [],
        "nao_coletado": [],
        "analise": "",       # do agente
    }


def na(motivo):
    """Marcador de dado não coletado — o motivo é obrigatório, senão vira buraco sem explicação."""
    return {"valor": None, "motivo": motivo}


def _chave_do_achado(achado):
    return (_PESO.get(achado.get("severidade"), len(SEVERIDADES)), achado.get("alvo", ""),
            achado.get("regra", ""), str(achado.get("objeto", "")))


def ordenar(relatorio):
    """Devolve uma CÓPIA ordenada: alvos na ordem declarada, achados por severidade dentro de cada um.

    Sem o alvo na chave, dois serviços homônimos em alvos diferentes trocariam de lugar entre
    execuções e o histórico viraria ruído. E não muta a entrada: o histórico compara com o
    relatório anterior, e mutar a baseline durante a comparação a corromperia.
    """
    copia = dict(relatorio)
    copia["alvos"] = [dict(alvo, achados=sorted(alvo.get("achados", []), key=_chave_do_achado))
                      for alvo in relatorio.get("alvos", [])]
    copia["aceites"] = sorted(relatorio.get("aceites", []),
                              key=lambda a: (a.get("alvo", ""), a.get("regra", "")))
    return copia


def achados_ordenados(relatorio):
    """Todos os achados numa lista só, do mais grave ao menos — é o que a seção "Achados" mostra.

    Ordenar por alvo primeiro esconderia um crítico do segundo alvo abaixo de um aviso do primeiro.
    """
    achados = [f for alvo in relatorio.get("alvos", []) for f in alvo.get("achados", [])]
    return sorted(achados, key=_chave_do_achado)


def montar_inventario(relatorio):
    """O mapa: o que existe, de que tipo, onde vive e em que estado."""
    return [{"nome": a["nome"], "tipo": a["tipo"], "onde": a["onde"], "saude": a["saude"]}
            for a in relatorio.get("alvos", [])]


def valido(relatorio):
    return (isinstance(relatorio, dict)
            and relatorio.get("schema_version") == SCHEMA_VERSION
            and isinstance(relatorio.get("alvos"), list))

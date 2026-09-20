"""Schema do report.json v3: o ALVO no centro, o COMPONENTE dentro dele.

Do v1 para o v2, o cluster no topo deu lugar à lista de alvos. Do v2 para o v3, cada alvo passa
a ter `componentes[]` — e cada componente guarda as RESPOSTAS das perguntas do seu papel, cada
uma carimbada com a fonte que respondeu. Número sem fonte não entra no relatório.

Os quatro campos do agente (`resumo`, `fortes`, `fracos`, `recomendacoes`) e o `analise` de cada
alvo e componente nascem vazios — é o script que grava os fatos, e o agente que escreve a
interpretação por cima.
"""
SCHEMA_VERSION = 3

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
        "componentes": [],
        "achados": [],
        "nao_coletado": [],
        "analise": "",       # do agente
    }


def novo_componente(nome, papel):
    """Uma unidade dentro do alvo: um serviço, um endpoint.

    `respostas` é o que as perguntas do papel devolveram (com a fonte); `achados` são os dele,
    que depois sobem para o alvo; `analise` é do agente.
    """
    return {"nome": nome, "papel": papel, "respostas": [], "achados": [], "analise": ""}


def na(motivo):
    """Marcador de dado não coletado — o motivo é obrigatório, senão vira buraco sem explicação."""
    return {"valor": None, "motivo": motivo}


def _chave_do_achado(achado):
    return (_PESO.get(achado.get("severidade"), len(SEVERIDADES)), achado.get("alvo", ""),
            achado.get("regra", ""), str(achado.get("objeto", "")))


def _componente_ordenado(componente):
    """Respostas na ordem declarada do catálogo de perguntas — não na ordem em que chegaram.

    A ordem de chegada depende de dicionário e de rede; deixá-la vazar para o arquivo faria
    duas coletas idênticas produzirem bytes diferentes.
    """
    from lib.perguntas import PERGUNTAS

    posicao = {id_: pos for pos, id_ in enumerate(PERGUNTAS)}
    return dict(componente,
                respostas=sorted(componente.get("respostas", []),
                                 key=lambda r: (posicao.get(r.get("pergunta"), len(posicao)),
                                                str(r.get("pergunta")))),
                achados=sorted(componente.get("achados", []), key=_chave_do_achado))


def ordenar(relatorio):
    """Devolve uma CÓPIA ordenada: alvos na ordem declarada, componentes por nome, achados por
    severidade e respostas na ordem do catálogo.

    Sem o alvo na chave, dois serviços homônimos em alvos diferentes trocariam de lugar entre
    execuções e o histórico viraria ruído. E não muta a entrada: o histórico compara com o
    relatório anterior, e mutar a baseline durante a comparação a corromperia.
    """
    copia = dict(relatorio)
    copia["alvos"] = [
        dict(alvo,
             achados=sorted(alvo.get("achados", []), key=_chave_do_achado),
             componentes=[_componente_ordenado(c)
                          for c in sorted(alvo.get("componentes", []),
                                          key=lambda c: (str(c.get("nome", "")),
                                                         str(c.get("papel", ""))))])
        for alvo in relatorio.get("alvos", [])]
    copia["aceites"] = sorted(relatorio.get("aceites", []),
                              key=lambda a: (a.get("alvo", ""), a.get("componente") or "",
                                             a.get("regra", "")))
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

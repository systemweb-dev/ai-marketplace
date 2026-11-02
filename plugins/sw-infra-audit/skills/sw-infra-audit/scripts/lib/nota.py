"""A nota geral da capa, e as pontuacoes por dimensao de que ela sai.

Tudo aqui e deterministico. A capa e a primeira coisa que alguem le, e uma nota que o agente
reinventa a cada rodada torna duas auditorias incomparaveis — que e exatamente o que um
relatorio de auditoria nao pode ser. A interpretacao do agente continua existindo, no
`resumo`, logo abaixo.

A conta soma todos os alvos medidos: 70% servicos online, 20% estabilidade e 10% boas praticas,
com teto de 59 ou 79 e faixas Bom (80+), Atencao (60 a 79) e Critico (abaixo de 60).
"""

import math


def _num(v):
    """Pontuacao chega de JSON: numero fora da escala, None ou texto nao derrubam a capa.

    NaN e infinito tambem nao, e cada um enganava de um jeito diferente. `round(inf)` levanta
    OverflowError, que o `except` daqui nao pegava: a capa inteira morria por causa de uma
    pontuacao. E NaN, se escapasse para `min(100, nan)`, voltava 100 — porque toda comparacao
    com NaN e falsa e o `min` fica com o primeiro. A dimensao corrompida saia com a MELHOR
    nota possivel, que e pior que nao sair.
    """
    try:
        numero = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(numero) or math.isinf(numero):
        return None
    return max(0, min(100, round(numero)))


def _media(valores):
    valores = [v for v in (_num(x) for x in valores) if v is not None]
    return round(sum(valores) / len(valores)) if valores else None


def pontuacoes(dimensoes):
    """0-100 por dimensao, ou None quando a dimensao nao foi medida.

    As formulas sao as que o relatorio ja usava, com UMA diferenca declarada: higiene
    passa a ser a media das quatro praticas que ela mede, em vez de so `nonroot_pct`.
    Uma dimensao de quatro medidas que exibe uma delas como nota nao descreve a dimensao.
    """
    d = dimensoes or {}

    def bloco(k):
        return d.get(k) or {}

    pts = {}

    op = bloco("operacao")
    total = op.get("services_total")
    pts["operacao"] = (round(100 * op.get("services_up", 0) / total) if total else None)

    pts["disponibilidade"] = _num(bloco("disponibilidade").get("ha_pct"))

    seg = bloco("seguranca")
    if "high" in seg:   # o coletor sem servicos devolve so {"note": "unknown"}: nao foi medida
        # alto pesa 12x o medio: uma falha alta vale por uma dezena de pendencias
        pts["seguranca"] = max(0, 100 - min(100, seg.get("high", 0) * 12 + seg.get("med", 0)))
    else:
        pts["seguranca"] = None

    hig = bloco("higiene")
    pts["higiene"] = _media([hig.get(k) for k in
                             ("pinned_pct", "nonroot_pct", "limits_pct", "healthcheck_pct")]) if hig else None
    return pts


PESOS = {"online": 70, "estabilidade": 20, "praticas": 10}


def _aceitos(alvo, aceites):
    return {a.get("objeto") for a in aceites
            if a.get("alvo") == alvo.get("nome") and a.get("regra") == "OPS_SERVICE_STOPPED"
            and not a.get("vencido") and not a.get("componente")}


def _conta_do_alvo(alvo, aceites):
    from lib.estado_servico import contar
    if alvo.get("tipo") == "http":
        fatos = alvo.get("fatos") or {}
        if not fatos:
            return {"online": 0, "base": 0, "fora": 0, "parcial": 0, "com_alerta": 0, "falhas_desconhecidas": 0}
        codigo = fatos.get("codigo")
        fora = codigo is None or codigo >= 500
        return {"online": 0 if fora else 1, "base": 1, "fora": int(fora), "parcial": 0, "com_alerta": 0,
                "falhas_desconhecidas": 0}
    return contar((alvo.get("fatos") or {}).get("services") or [], _aceitos(alvo, aceites))


def nota_geral(alvos, aceites):
    medidos = [a for a in alvos if a.get("coletado", True)]
    contas = [_conta_do_alvo(a, aceites) for a in medidos]
    base = sum(c["base"] for c in contas)
    if not base:
        return None
    online = sum(c["online"] for c in contas)
    pts = [pontuacoes(a.get("dimensoes") or {}) for a in medidos]
    estab = _media([p["disponibilidade"] for p in pts])
    praticas = _media([v for p in pts for v in (p["seguranca"], p["higiene"])])
    parcelas = {"online": round(100 * online / base), "estabilidade": estab, "praticas": praticas}
    medidas = {k: v for k, v in parcelas.items() if v is not None}
    valor = round(sum(v * PESOS[k] for k, v in medidas.items()) / sum(PESOS[k] for k in medidas))
    achados = [x for a in medidos for x in a.get("achados") or []]
    altos = [x for x in achados if x.get("severidade") in ("high", "critical")]
    nos_fora = sum(((a.get("dimensoes") or {}).get("operacao") or {}).get("nodes_down", 0) for a in medidos)
    limites = {"fora": sum(c["fora"] for c in contas), "parciais": sum(c["parcial"] for c in contas),
               "nos_fora": nos_fora, "altos": len(altos),
               "regras_altas": sorted({str(x.get("regra")) for x in altos})}
    teto = 100
    if altos or limites["parciais"]:
        teto = 79
    if nos_fora or limites["fora"]:
        teto = 59
    valor = min(valor, teto)
    parcial = (len(medidas) < len(PESOS) or any(not c["base"] for c in contas)
               or any(c["falhas_desconhecidas"] for c in contas))
    faixa = "bom" if valor >= 80 else ("atencao" if valor >= 60 else "critico")
    if (parcial or any(a.get("trava_cobertura") for a in medidos)) and faixa == "bom":
        faixa = "atencao"
    return {"valor": valor, "faixa": faixa, "parcial": parcial, "parcelas": parcelas,
            "teto": teto if teto < 100 else None, "online": online, "base": base,
            "com_alerta": sum(c["com_alerta"] for c in contas), "limites": limites,
            "pendencias": {k: None if v is None else 100 - v for k, v in parcelas.items()}}

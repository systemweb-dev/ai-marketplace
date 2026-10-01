"""A nota de estabilidade da capa, e as pontuacoes por dimensao de que ela sai.

Tudo aqui e deterministico. A capa e a primeira frase que alguem le, e um titulo
que o agente reinventa a cada rodada torna duas auditorias incomparaveis — que e
exatamente o que um relatorio de auditoria nao pode ser. A interpretacao do agente
continua existindo, no `resumo`, logo abaixo.

NAO existe nota unica da infraestrutura: numero so vira meta, e meta vira teatro.
A faixa daqui e a da CAPA — adjetivo de leitura, nao placar.
"""

ORDEM = ("operacao", "disponibilidade", "seguranca", "higiene")

ROTULO = {"operacao": "Operação", "disponibilidade": "Disponibilidade",
          "seguranca": "Segurança", "higiene": "Higiene"}

# o que cada dimensao quer dizer quando esta cheia e quando esta vazia
VEREDITO = {
    "operacao": ("converge: está rodando o que foi pedido", "há coisa fora do ar agora"),
    "disponibilidade": ("tem reserva: o que cai tem quem assuma", "frágil: o que cai não tem reserva"),
    "seguranca": ("sem pendência de prática relevante", "muita pendência acumulada"),
    "higiene": ("as práticas estão aplicadas", "abaixo do piso nas práticas básicas"),
}

PISO = 70          # daqui para baixo a dimensao entra no titulo
LIMIAR_RUIM = 60   # operacao abaixo disso e "tem coisa fora do ar"


def _num(v):
    """Pontuacao chega de JSON: numero fora da escala, None ou texto nao derrubam a capa."""
    try:
        return max(0, min(100, round(float(v))))
    except (TypeError, ValueError):
        return None


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
    if seg:
        # alto pesa 12x o medio: uma falha alta vale por uma dezena de pendencias
        pts["seguranca"] = max(0, 100 - min(100, seg.get("high", 0) * 12 + seg.get("med", 0)))
    else:
        pts["seguranca"] = None

    hig = bloco("higiene")
    pts["higiene"] = _media([hig.get(k) for k in
                             ("pinned_pct", "nonroot_pct", "limits_pct", "healthcheck_pct")]) if hig else None
    return pts


def _faixa_de(p):
    if p is None:
        return "sem_dados"
    return "bom" if p >= PISO else ("atencao" if p >= LIMIAR_RUIM else "ruim")


def nota_de_estabilidade(dimensoes):
    """A frase da capa: como a infra esta, em uma linha, com a dimensao que puxa para baixo.

    Devolve `titulo`, `faixa`, `pior` e as `pontuacoes` — o relatorio desenha, nao decide.
    """
    pts = pontuacoes(dimensoes)
    medidas = {k: v for k, v in pts.items() if v is not None}
    if not medidas:
        return {"titulo": "Sem dados para avaliar esta infraestrutura.",
                "faixa": "sem_dados", "pior": None, "pontuacoes": pts,
                "porque": "nenhuma dimensão foi medida nesta rodada"}

    pior = min(sorted(medidas), key=lambda k: medidas[k])   # sorted(): empate desempata estavel
    op = medidas.get("operacao")

    if op is not None and op < LIMIAR_RUIM:
        titulo, faixa = "Tem serviço fora do ar agora.", "ruim"
    elif medidas[pior] >= PISO:
        titulo, faixa = "Estável, e com reserva para falhar.", "bom"
    elif pior == "disponibilidade":
        titulo, faixa = "Estável para servir, frágil para falhar.", "atencao"
    elif pior == "higiene":
        titulo, faixa = "No ar e entregando, abaixo do piso nas práticas.", "atencao"
    elif pior == "seguranca":
        titulo, faixa = "Sem falha aberta, com pendência acumulada.", "atencao"
    else:
        titulo, faixa = "No ar, com ponto que merece atenção.", "atencao"

    return {"titulo": titulo, "faixa": faixa, "pior": pior, "pontuacoes": pts,
            "porque": f"{ROTULO[pior].lower()} é a dimensão mais fraca, em {medidas[pior]} de 100"}

"""Triagem dos achados por ACAO, nao por gravidade.

O relatorio antigo listava achado por severidade, e quem recebia tinha de traduzir
"107 medios" em "o que eu faco hoje?". Aqui a pergunta ja vem respondida: cada achado
cai numa das tres faixas, e a faixa e o titulo da secao.

Logica pura de proposito — ordenar e contar achado nao precisa de HTML para ser
verificado, e e o que o grafico de cascata do topo promete que fecha.
"""

ORDEM_SEVERIDADE = ("critical", "high", "medium", "low", "info")

# (id, rotulo, severidades que caem aqui). A ordem e a da leitura: o que da trabalho
# hoje vem antes do que da trabalho no trimestre.
FAIXAS = (
    ("agir", "Agir agora", ("critical", "high")),
    ("programar", "Programar", ("medium",)),
    ("registrar", "Registrar e seguir", ("low", "info")),
)

# severidade que nao reconhecemos cai aqui: perder o achado e pior que classifica-lo mal
_FAIXA_PADRAO = "registrar"

_PESO = {s: i for i, s in enumerate(ORDEM_SEVERIDADE)}
_DE_SEVERIDADE = {s: fid for fid, _, sevs in FAIXAS for s in sevs}


def _chave(achado):
    """Severidade primeiro; depois regra e objeto, para a ordem nao variar entre duas
    execucoes da mesma entrada — senao o diff entre auditorias acusa mudanca que nao houve."""
    sev = achado.get("severidade")
    return (_PESO.get(sev, len(ORDEM_SEVERIDADE)),
            str(achado.get("regra") or ""),
            str(achado.get("objeto") or ""),
            str(achado.get("componente") or ""))


def triar(achados):
    """Separa os achados nas faixas de acao.

    Achado marcado como `esperada` nao entra em faixa nenhuma: ele descreve o normal
    (o proxy que monta o docker.sock porque e assim que ele funciona), e cobrar isso
    gasta a atencao de quem le. Ele continua contado, para a cascata nao mentir.
    """
    achados = list(achados or [])
    baldes = {fid: [] for fid, _, _ in FAIXAS}
    esperados = 0
    for achado in achados:
        if achado.get("esperada"):
            esperados += 1
            continue
        baldes[_DE_SEVERIDADE.get(achado.get("severidade"), _FAIXA_PADRAO)].append(achado)
    return {
        "total": len(achados),
        "esperados": esperados,
        "faixas": {fid: {"rotulo": rotulo, "achados": sorted(baldes[fid], key=_chave)}
                   for fid, rotulo, _ in FAIXAS},
    }


def cascata(t):
    """Os degraus do grafico do topo, do universo ate o que exige acao hoje.

    Cada degrau carrega o numero E a conta que o produziu: numero sem fonte nao existe,
    e aqui a fonte e a propria triagem.
    """
    acionaveis = t["total"] - t["esperados"]
    f = t["faixas"]
    return [
        {"id": "total", "rotulo": "Total coletado", "n": t["total"], "nota": "achados"},
        {"id": "acionaveis", "rotulo": "Menos os esperados", "n": acionaveis,
         "nota": f"menos {t['esperados']}" if t["esperados"] else "nenhum esperado"},
        {"id": "registrar", "rotulo": "Registrar e seguir", "n": len(f["registrar"]["achados"]),
         "nota": "sem prazo"},
        {"id": "programar", "rotulo": "Programar", "n": len(f["programar"]["achados"]),
         "nota": "com janela"},
        {"id": "agir", "rotulo": "Agir agora", "n": len(f["agir"]["achados"]), "nota": "hoje"},
    ]

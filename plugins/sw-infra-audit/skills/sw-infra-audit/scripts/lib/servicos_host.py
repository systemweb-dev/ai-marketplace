"""Os serviços de um alvo `host` no formato que a capa e a nota já leem (`name`, `replicas`).

Assim o host conta como o cluster, sem um segundo jeito de contar: ativo é "1/1", parado ou ausente
é "0/1", e não medido (`servico.ativo` sem resposta) é réplica ilegível, que `estado_de` trata como
"sem dado", fora da base da nota.
"""
from lib.dados_blocos import _resposta

AUSENTE = "servico_declarado_ausente"


def servicos(alvo):
    if alvo.get("tipo") != "host":
        return []
    ausentes = {a.get("componente") for a in alvo.get("achados") or [] if a.get("regra") == AUSENTE}
    saida = []
    for comp in alvo.get("componentes") or []:
        if comp.get("papel") == "maquina":
            continue
        ativo = _resposta(comp, "servico.ativo")
        if comp.get("nome") in ausentes or (ativo is not None and ativo != "ativo"):
            replicas = "0/1"
        else:
            replicas = "1/1" if ativo == "ativo" else None
        saida.append({"name": comp.get("nome"), "replicas": replicas, "tasks_failed": 0})
    return saida


def aceitos(alvo, aceites):
    """O aceite do ausente mira o componente: o `objeto` do achado é o nome dele.

    `aceitar --componente pg` grava `componente` e deixa `objeto` vazio. Ler só o `objeto` daria
    None, que `estado_de` entende como "vale para o alvo inteiro" e calaria todo serviço parado.
    """
    return {a.get("objeto") or a.get("componente") for a in aceites
            if a.get("alvo") == alvo.get("nome") and a.get("regra") == AUSENTE and not a.get("vencido")}

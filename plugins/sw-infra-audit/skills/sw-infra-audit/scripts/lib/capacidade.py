"""Achado de capacidade da máquina: disco e memória acima de 90%.

Não é limiar de pergunta porque as perguntas `maquina.*` são opcionais, e o catálogo recusa limiar em
opcional (sem resposta, o limiar travaria o verde sem motivo). Aqui só resposta COM número produz
achado: `sem_dados` nunca vira "disco cheio" nem "disco folgado". Vale para host e nó do cluster —
o mesmo disco a 94% não pode ser achado num lugar e silêncio no outro (decisão do dono, 2026-11-13).
"""
import math

LIMITES = {"maquina.disco": (90, "disco_quase_cheio", "high"),
           "maquina.memoria": (90, "memoria_sem_folga", "medium")}
REGRAS_PRODUZIDAS = {regra for _, regra, _ in LIMITES.values()}


def achados(componente):
    if componente.get("papel") != "maquina":
        return []
    saida = []
    for resposta in componente.get("respostas", []):
        limite = LIMITES.get(resposta.get("pergunta"))
        valor = resposta.get("valor")
        if limite is None or resposta.get("sem_dados") or type(valor) not in (int, float):
            continue
        if math.isfinite(valor) and valor > limite[0]:
            saida.append({"regra": limite[1], "severidade": limite[2],
                          "objeto": componente["nome"], "valor": valor})
    return saida

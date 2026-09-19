"""Risco já decidido: sai dos achados, vai para a lista de aceites, e volta quando vence.

Aplicado DEPOIS das regras, nunca antes: se o aceite filtrasse a coleta, ninguém veria o risco
mudar de tamanho. E aceite que não casa com nada é reportado — a justificativa envelheceu junto
com o problema que ela explicava.
"""

from datetime import date

PRECEDENCIA = {"infra": 0, "projeto": 1}     # o mais específico vence


def _data(valor, onde):
    """Data ISO, sempre. Comparar texto faria "31/12/2026" nunca vencer e "19/09/2026" vencer
    sempre — silenciosamente, que é o pior jeito de errar num registro de risco aceito."""
    try:
        return date.fromisoformat(str(valor))
    except (TypeError, ValueError) as erro:
        raise ValueError(f"{onde}: data precisa ser AAAA-MM-DD, veio {valor!r}") from erro


def _casa(achado, aceite):
    if aceite.get("alvo") != achado.get("alvo") or aceite.get("regra") != achado.get("regra"):
        return False
    alvo_objeto = aceite.get("objeto")
    return alvo_objeto in (None, achado.get("objeto"))


def _vencido(aceite, hoje):
    revisar = aceite.get("revisar_em")
    if revisar is None:
        return False                        # sem data de revisão: vale, e o relatório mostra isso
    return _data(revisar, f"aceite de {aceite.get('alvo')}") < _data(hoje, "--at")


def aplicar(alvos, aceites, hoje):
    """Remove dos `alvos` os achados aceitos e devolve a lista de aceites para o relatório.

    Muta `alvos` de propósito: o achado aceito não pode continuar contando para a nota.
    """
    escolhidos = {}
    for aceite in aceites:
        if not aceite.get("alvo") or not aceite.get("regra"):
            raise ValueError(f"aceite sem alvo ou regra: {aceite}")
        chave = (aceite.get("alvo"), aceite.get("regra"), aceite.get("objeto"))
        atual = escolhidos.get(chave)
        if atual is None or PRECEDENCIA.get(aceite.get("origem"), 0) > \
                PRECEDENCIA.get(atual.get("origem"), 0):
            novo = dict(aceite)
            if atual is not None:
                novo["sobrepoe"] = atual.get("origem")
            escolhidos[chave] = novo

    auditados = {alvo.get("nome") for alvo in alvos}
    # alvo sem coleta não tem achado: marcar obsoleto faria o usuário apagar justificativa válida
    coletados = {alvo.get("nome") for alvo in alvos if alvo.get("coletado", True)}
    saida = []
    for aceite in escolhidos.values():
        # aceite de alvo que não entrou nesta auditoria não é obsoleto: apenas não se aplica hoje
        if aceite.get("alvo") not in auditados:
            continue
        vencido = _vencido(aceite, hoje)
        casou = False
        for alvo in alvos:
            restantes = []
            for achado in alvo.get("achados", []):
                if not _casa(achado, aceite):
                    restantes.append(achado)
                    continue
                casou = True
                if vencido:
                    achado["aceite_vencido"] = True
                    restantes.append(achado)
            alvo["achados"] = restantes
        saida.append({**aceite, "vencido": vencido,
                      "obsoleto": not casou and aceite["alvo"] in coletados})
    return sorted(saida, key=lambda a: (a.get("alvo") or "", a.get("regra") or ""))

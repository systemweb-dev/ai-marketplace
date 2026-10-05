"""Quanto da medição a auditoria conseguiu fazer — e que teto isso impõe ao veredito.

A skill prega "não consegui ver ≠ está ruim". O inverso — "não consegui ver ≠ está bom" —
é o que este módulo protege: entre 29/09 e 03/10 um cluster passou de 🔴 para 🟢 sem nada ter
melhorado, porque a pergunta que produz o achado não foi respondida e não havia o que agravar.

Funções puras: recebem o registro do alvo e devolvem dado. Quem escreve `saude` é o
`collect.main`, ao lado do `agravar_saude` que já existe.
"""
import json


def _respondeu(resposta, pergunta):
    """A resposta conta como respondida?

    Lista vazia em pergunta COM limiar não conta: `_sem_numero` e `_sem_contadores` devolvem
    a resposta intacta quando `valor` é `[]`, então a fonte responder "nenhum item" marcaria
    100% de cobertura sem nada ter sido medido.
    """
    if resposta.get("sem_dados") or resposta.get("erro_interno"):
        return False
    valor = resposta.get("valor")
    if pergunta.get("limiar") and isinstance(valor, list) and not valor:
        return False
    return True


def medir(alvo):
    """Mede a cobertura de um alvo.

    `perguntadas` conta só o que a skill SABE perguntar para aquele papel. Papel sem pergunta
    registrada (hoje só `observabilidade`) fica fora do denominador: ele é limite da skill, não
    falha de cobertura, e já é reportado em "O que falta declarar". `app`, `banco` e `cache`
    estavam nesta lista e ganharam perguntas na v0.13.0.

    Desde a v0.16.0, componente cujo PAPEL não foi provado por nenhuma fonte também entra em
    `mudos`, como `<identidade>`: papel errado faz as perguntas erradas, e isso é lacuna de
    medição tanto quanto pergunta sem resposta.
    """
    from lib.perguntas import do_papel

    perguntadas = respondidas = 0
    mudos = []
    # Uma medida é (pergunta, valor, fonte). Quando o adaptador não restringe a consulta ao
    # componente, o MESMO número chega por vários — e contar cada chegada inflava a
    # cobertura: 6 de 9 onde o honesto eram 3 de 6.
    medidas_vistas = set()
    for componente in alvo.get("componentes") or []:
        # D6 — identidade não provada é lacuna de medição, não detalhe cosmético. Papel
        # provisório errado faz as perguntas erradas, e o teto de saúde não pega isso: ele só
        # olha pergunta com `limiar`, e das 12 perguntas canônicas só `fila.filas` tem uma.
        # Quem OBSERVA outros nunca poderá ser confirmado (D4): a série que ele publica é do
        # observado. Cobrar identidade dele seria cobrar o impossível toda rodada — e são 16
        # dos 37 produtos do catálogo que caem aqui.
        if componente.get("papel_origem") in (None, "padrão", "imagem") \
                and not componente.get("exportador"):
            ambiguo = componente.get("papel_ambiguo")
            if ambiguo:
                # D3 pede o oposto de "nenhuma fonte provou": DUAS provaram, e em desacordo.
                # Dizer "nenhuma" aqui manda o dono procurar exporter que ele já tem.
                motivo = (f"duas famílias reconhecem este componente e discordam do papel "
                          f"({', '.join(ambiguo)}) — declare `papel` no "
                          f"`[[alvo.componente]]` do alvos.toml para desempatar")
            else:
                motivo = ("o papel deste componente não foi provado por nenhuma fonte — "
                          "declare `papel` no `[[alvo.componente]]` do alvos.toml, ou aponte "
                          "uma `metricas_url` cujo exporter o reconheça")
            mudos.append({"componente": componente.get("nome"),
                          "pergunta": "<identidade>", "motivo": motivo})
        catalogo = {p["id"]: p for p in do_papel(componente.get("papel"))}
        if not catalogo:
            continue
        perguntadas += len(catalogo)
        por_id = {r.get("pergunta"): r for r in (componente.get("respostas") or [])}
        for id_pergunta, pergunta in catalogo.items():
            resposta = por_id.get(id_pergunta)
            if resposta is not None and _respondeu(resposta, pergunta):
                medida = (id_pergunta,
                          json.dumps(resposta.get("valor"), sort_keys=True, default=str),
                          resposta.get("fonte"))
                if medida in medidas_vistas:
                    perguntadas -= 1          # não era outra pergunta: era a mesma medida
                else:
                    medidas_vistas.add(medida)
                    respondidas += 1
                continue
            mudos.append({
                "componente": componente.get("nome"),
                "pergunta": id_pergunta,
                "motivo": (resposta or {}).get("motivo") or "a pergunta não foi feita",
            })
    pct = round(100 * respondidas / perguntadas) if perguntadas else None
    return {"perguntadas": perguntadas, "respondidas": respondidas, "pct": pct, "mudos": mudos}


# Estados que a cobertura pode impor. Espelha `_PIOR_ESTADO` do collect: `low` e `info` não
# aparecem porque um achado dessa severidade não derrubaria o alvo — e a AUSÊNCIA dele não
# pode ser mais severa que a presença.
_TRAVA = {"critical": "🟡", "high": "🟡", "medium": "🟡"}
_GRAVIDADE = {"🟢": 0, "🟡": 1, "🔴": 2}


def teto_por_cobertura(alvo, aceites_vigentes=(), severidade_por_pergunta=None):
    """Impede o 🟢 quando uma pergunta COM limiar ficou sem resposta.

    Quatro guardas, todas deliberadas:

    1. **Teto, nunca piso.** Só impede o 🟢; nunca produz 🔴 nem desce um alvo já pior.
       Vermelho significa "algo está fora do ar", e não ver não é prova disso.
    2. **Só severidade que trava.** Limiar `low` não derruba um 🟢 que o próprio achado não
       derrubaria.
    3. **Aceite vigente dispensa.** Se a regra daquele limiar já foi aceita, o achado não
       contaria de qualquer forma — travar por ele cobraria duas vezes. Aceite VENCIDO não
       dispensa: ele voltou a contar.
    4. **Estado fora da escala não é tocado.** `sem dados` continua `sem dados`.
    """
    from lib.perguntas import do_papel

    atual = alvo.get("saude")
    if atual not in _GRAVIDADE:                                  # guarda 4
        return
    severidade_por_pergunta = severidade_por_pergunta or {}

    for componente in alvo.get("componentes") or []:
        catalogo = {p["id"]: p for p in do_papel(componente.get("papel"))}
        por_id = {r.get("pergunta"): r for r in (componente.get("respostas") or [])}
        for id_pergunta, pergunta in catalogo.items():
            limiar = pergunta.get("limiar")
            if not limiar:
                continue
            resposta = por_id.get(id_pergunta)
            if resposta is not None and _respondeu(resposta, pergunta):
                continue
            if limiar.get("regra") in aceites_vigentes:           # guarda 3
                continue
            severidade = severidade_por_pergunta.get(id_pergunta, limiar.get("severidade"))
            exigido = _TRAVA.get(severidade)                      # guarda 2
            if exigido and _GRAVIDADE[exigido] > _GRAVIDADE[alvo["saude"]]:   # guarda 1
                alvo["saude"] = exigido

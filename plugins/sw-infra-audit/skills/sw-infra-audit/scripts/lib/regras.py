"""Registro explícito de regras — a única lista enumerável de tudo que vira achado.

Antes, os identificadores eram literais no corpo das funções de `rules.py`, e o coletor http
criava os seus por fora. Enumerar isso exigia ler AST; e o que não se enumera não se cobra —
por isso era possível existir achado sem remediação, e por isso `rule_meta` carregava uma
entrada morta (`OPS_SERVICE_DOWN`, que nenhum produtor emite).

`esperada = True` marca a regra que descreve comportamento NORMAL: o proxy monta o docker.sock
porque é assim que ele descobre serviços; um job de migração em 0 réplicas concluiu. Essas não
pesam na nota e não exigem arquivo de remediação — dizer "corrija" ali seria ruído.

A severidade aqui é a PADRÃO da regra; o achado pode trazer a sua (o vocabulário antigo usa
`crit/high/med/low`, o novo usa `critical/high/medium/low/info`).
"""

REGRAS = {
    # --- segurança (lib/rules.py)
    "SEC_PRIVILEGED":           {"severidade_padrao": "high",   "origem": "rules", "esperada": False},
    "SEC_DOCKER_SOCK":          {"severidade_padrao": "high",   "origem": "rules", "esperada": False},
    "SEC_DOCKER_SOCK_EXPECTED": {"severidade_padrao": "low",    "origem": "rules", "esperada": True},
    "SEC_PORT_EXPOSED":         {"severidade_padrao": "medium", "origem": "rules", "esperada": False},
    "SEC_IMAGE_UNPINNED":       {"severidade_padrao": "medium", "origem": "rules", "esperada": False},
    "SEC_USER_ROOT":            {"severidade_padrao": "medium", "origem": "rules", "esperada": False},
    # --- operação (lib/rules.py)
    "OPS_NODE_DOWN":            {"severidade_padrao": "high",   "origem": "rules", "esperada": False},
    "OPS_NODE_DRAIN":           {"severidade_padrao": "low",    "origem": "rules", "esperada": False},
    "OPS_SERVICE_STOPPED":      {"severidade_padrao": "medium", "origem": "rules", "esperada": False},
    "OPS_REPLICAS_DEGRADED":    {"severidade_padrao": "medium", "origem": "rules", "esperada": False},
    "OPS_TASK_FAILING":         {"severidade_padrao": "medium", "origem": "rules", "esperada": False},
    "OPS_NO_HEALTHCHECK":       {"severidade_padrao": "low",    "origem": "rules", "esperada": False},
    "OPS_NO_LIMITS":            {"severidade_padrao": "low",    "origem": "rules", "esperada": False},
    "OPS_ENGINE_DRIFT":         {"severidade_padrao": "low",    "origem": "rules", "esperada": False},
    "OPS_JOB_COMPLETED":        {"severidade_padrao": "low",    "origem": "rules", "esperada": True},
    "OPS_TLS_EXPIRED":          {"severidade_padrao": "high",   "origem": "rules", "esperada": False},
    "OPS_TLS_EXPIRING":         {"severidade_padrao": "medium", "origem": "rules", "esperada": False},
    "OPS_DAEMON_UNREACHABLE":   {"severidade_padrao": "high",   "origem": "rules", "esperada": False},
    # --- coletor http
    "certificado_vencendo":     {"severidade_padrao": "high",    "origem": "coletor_http", "esperada": False},
    "sem_tls":                  {"severidade_padrao": "medium",  "origem": "coletor_http", "esperada": False},
    "http_fora_do_ar":          {"severidade_padrao": "critical", "origem": "coletor_http", "esperada": False},
    "http_resposta_de_erro":    {"severidade_padrao": "medium",  "origem": "coletor_http", "esperada": False},
}


def severidade(regra, padrao="info"):
    return REGRAS.get(regra, {}).get("severidade_padrao", padrao)


def esperada(regra):
    return REGRAS.get(regra, {}).get("esperada", False)


def exigem_remediacao():
    """As regras que precisam de arquivo em references/remediacao/.

    Regra esperada fica de fora: ela descreve o normal, não um problema a corrigir.
    """
    return {id_ for id_, meta in REGRAS.items() if not meta["esperada"]}

"""Metadados didáticos por rule_id — o que é / por que importa. Usado pra explicar os findings
em linguagem clara no relatório (o `fix` vem do próprio finding)."""

RULE_META = {
    "SEC_PRIVILEGED": {
        "label": "Container privilegiado",
        "what": "O container roda em modo --privileged (acesso quase total ao host).",
        "why": "Uma invasão nesse container vira controle do host inteiro — é o maior risco de escalada.",
    },
    "SEC_DOCKER_SOCK": {
        "label": "Mount de path sensível do host",
        "what": "Monta o docker.sock ou diretórios críticos do host (/, /etc, /root, /proc, /sys).",
        "why": "Acesso ao docker.sock ≈ root no host; um comprometimento escala pra todo o cluster. "
               "Comum em ferramentas de monitoramento (cadvisor, promtail) — nesses casos, avaliar socket-proxy read-only.",
    },
    "SEC_PORT_EXPOSED": {
        "label": "Porta publicada em 0.0.0.0",
        "what": "A porta é publicada em todas as interfaces do host (não só na rede interna).",
        "why": "Se o firewall/security-group da cloud deixar passar, o serviço fica alcançável de fora. "
               "Não é prova de exposição real — mas é a superfície.",
    },
    "SEC_IMAGE_UNPINNED": {
        "label": "Imagem sem versão fixa",
        "what": "Usa :latest ou não fixa o digest da imagem.",
        "why": "O que roda pode mudar sem aviso: deploys não são reproduzíveis e um novo pull pode "
               "trazer código diferente (ou comprometido).",
    },
    "SEC_USER_ROOT": {
        "label": "Roda como root",
        "what": "O container roda como root (uid 0 ou sem USER definido, que é root por padrão).",
        "why": "Amplia o estrago de qualquer falha na aplicação. Princípio do menor privilégio: rodar como usuário comum.",
    },
}


def meta(rule_id):
    return RULE_META.get(rule_id, {"label": rule_id, "what": "", "why": ""})

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


RULE_META.update({
    "SEC_DOCKER_SOCK_EXPECTED": {
        "label": "docker.sock em ferramenta que precisa dele",
        "what": "Monta o docker.sock — é assim que a ferramenta funciona (Traefik descobre serviços, "
                "cAdvisor/Promtail leem containers, agentes gerenciam o host).",
        "why": "Informativo, não é um desvio: sem o socket essas ferramentas não operam. Ainda assim o "
               "acesso equivale a root no host — se quiser reduzir a superfície, um socket-proxy read-only resolve.",
    },
    "OPS_TLS_EXPIRED": {
        "label": "Certificado TLS do daemon expirado",
        "what": "O certificado que protege a API do Docker (porta 2376) expirou ou ainda não é válido.",
        "why": "Bloqueia TODO acesso remoto ao cluster: docker context, deploys de CI/CD, Portainer "
               "via TCP e a própria auditoria. Os containers continuam rodando, mas ninguém consegue "
               "gerenciá-los remotamente até renovar.",
    },
    "OPS_TLS_EXPIRING": {
        "label": "Certificado TLS perto de expirar",
        "what": "O certificado do context Docker vence em menos de 30 dias.",
        "why": "No dia do vencimento todo acesso remoto ao cluster para de uma vez — CLI, deploys "
               "de CI/CD e Portainer via TCP. Renovar antes evita uma parada de gestão inesperada.",
    },
    "OPS_DAEMON_UNREACHABLE": {
        "label": "Daemon inacessível",
        "what": "Não foi possível conectar na API do Docker do host.",
        "why": "Sem acesso não há gestão remota nem auditoria. Pode ser firewall, rede ou dockerd fora do ar.",
    },
    "OPS_NODE_DOWN": {
        "label": "Nó fora do ar",
        "what": "Um nó do Swarm não está no estado Ready.",
        "why": "As tasks daquele nó são reagendadas; se não houver capacidade sobrando, serviços ficam degradados.",
    },
    "OPS_NODE_DRAIN": {
        "label": "Nó em drain",
        "what": "O nó está marcado como Drain e não recebe novas tasks.",
        "why": "Normal durante manutenção; vira problema se foi esquecido assim (capacidade ociosa).",
    },
    "OPS_SERVICE_DOWN": {
        "label": "Serviço fora do ar",
        "what": "O serviço está com 0 réplicas rodando, embora deseje mais de uma.",
        "why": "Indisponibilidade real, agora. É a prioridade máxima de qualquer auditoria.",
    },
    "OPS_SERVICE_STOPPED": {
        "label": "Serviço parado (0 réplicas)",
        "what": "O serviço existe mas não tem nenhuma réplica no ar.",
        "why": "Pode ser INTENCIONAL (escalado a zero, app desativado) ou uma falha de start — a "
               "auditoria não distingue os dois. Vale confirmar: se era pra estar no ar, é incidente; "
               "se não era, o service pode ser removido para reduzir ruído.",
    },
    "OPS_JOB_COMPLETED": {
        "label": "Job de execução única concluído",
        "what": "Serviço de migração/seed/manutenção (flyway, migrate, cron…) com 0 réplicas.",
        "why": "Informativo: é o estado normal depois que o job roda e termina. Não indica problema.",
    },
    "OPS_TASK_FAILING": {
        "label": "Tasks falhando",
        "what": "O serviço teve tasks em estado Failed/Rejected recentemente.",
        "why": "Indica crash-loop ou erro de agendamento — o número de réplicas pode parecer OK "
               "enquanto o container reinicia sem parar por baixo.",
    },
    "OPS_NO_LIMITS": {
        "label": "Sem limite de CPU/memória",
        "what": "O serviço roda sem --limit-cpu / --limit-memory.",
        "why": "Um vazamento de memória ou pico de CPU consome o nó inteiro e derruba os vizinhos. "
               "Limite é o cinto de segurança do nó.",
    },
    "OPS_NO_HEALTHCHECK": {
        "label": "Sem healthcheck",
        "what": "A imagem/serviço não define HEALTHCHECK.",
        "why": "Sem ele o Swarm só sabe se o processo existe, não se a aplicação responde — "
               "um app travado continua recebendo tráfego.",
    },
    "OPS_REPLICAS_DEGRADED": {
        "label": "Réplicas abaixo do desejado",
        "what": "O serviço roda com menos réplicas do que a configuração pede.",
        "why": "Capacidade reduzida e menor tolerância a falha; costuma indicar erro de start, "
               "constraint impossível ou falta de recurso no nó.",
    },
})


def meta(rule_id):
    return RULE_META.get(rule_id, {"label": rule_id, "what": "", "why": ""})

"""Regras determinísticas de finding sobre os fatos já coletados.

Duas famílias, deliberadamente separadas:
  • OPS_*  — **operação**: está rodando? (nó fora, réplica não convergida, task falhando).
             É o que define a SAÚDE do cluster.
  • SEC_*  — **postura de segurança**: higiene/hardening. Importante, mas não impede nada de
             rodar — por isso NÃO derruba a saúde operacional.

Os findings vêm daqui (regra); o agente só prioriza e escreve a prosa.
"""
# Paths de host cujo bind é sensível. Match por prefixo (path == p ou começa com p + "/").
_SENSITIVE = ("/var/run/docker.sock", "/run/docker.sock", "/etc", "/root",
              "/var/run", "/proc", "/sys")

# Ferramentas em que montar o docker.sock é ESPERADO (é como elas funcionam). O achado continua
# sendo registrado — mas como informativo, não como risco crítico.
_SOCKET_EXPECTED = ("cadvisor", "promtail", "node-exporter", "node_exporter", "portainer",
                    "traefik", "watchtower", "autoheal", "socket-proxy", "prune", "logspout",
                    "dockerd-exporter", "swarm-cronjob", "shepherd", "diun")


def _f(rid, sev, obj, evidence, fix, scope, expected=False):
    return {"rule_id": rid, "severity": sev, "object": obj, "evidence": evidence,
            "fix": fix, "scope": scope, "expected": expected}


def _is_sensitive(src):
    if not src:
        return False
    if src == "/":
        return True
    return any(src == p or src.startswith(p + "/") for p in _SENSITIVE)


def _is_root(user):
    if user is None:
        return True                      # sem USER definido = root por padrão
    u = str(user).lower()
    return u == "root" or u == "0" or u.startswith("0:")


def _socket_is_expected(wl):
    hay = " ".join(str(x or "").lower() for x in (wl.get("image"), wl.get("name")))
    return any(t in hay for t in _SOCKET_EXPECTED)


# ---------------------------------------------------------------- segurança (postura)
def findings_for_workload(wl, scope):
    """wl = {name?, image, tag, digest, user, env_keys, privileged, mounts, ports}."""
    out = []
    name = wl.get("name") or wl.get("image")

    if wl.get("privileged"):
        out.append(_f("SEC_PRIVILEGED", "high", name, "Privileged=true",
                      "remover --privileged; conceder só as capabilities necessárias", scope))

    if any(_is_sensitive(m.get("source")) for m in (wl.get("mounts") or [])):
        if _socket_is_expected(wl):
            out.append(_f("SEC_DOCKER_SOCK_EXPECTED", "low", name,
                          "monta o docker.sock — esperado para esta ferramenta (monitoramento/proxy/agente)",
                          "opcional: usar socket-proxy read-only para reduzir a superfície",
                          scope, expected=True))
        else:
            out.append(_f("SEC_DOCKER_SOCK", "high", name,
                          "mount de path sensível do host (docker.sock / raiz / /etc / /proc…)",
                          "remover o mount sensível ou usar socket-proxy read-only", scope))

    if any(isinstance(p, dict) and p.get("host_ip") in ("0.0.0.0", "::")
           for p in (wl.get("ports") or [])):
        out.append(_f("SEC_PORT_EXPOSED", "med", name,
                      "porta publicada em 0.0.0.0 (todas as interfaces do host)",
                      "publicar só na interface interna necessária, ou proteger via firewall", scope))

    if wl.get("tag") == "latest" or not wl.get("digest"):
        out.append(_f("SEC_IMAGE_UNPINNED", "med", name,
                      f'imagem {wl.get("image")}:{wl.get("tag")} sem digest fixo',
                      "fixar tag imutável + digest (image@sha256:...)", scope))

    if _is_root(wl.get("user")):
        out.append(_f("SEC_USER_ROOT", "med", name,
                      "container roda como root (user root/uid 0 ou USER ausente)",
                      "definir USER não-root na imagem/service", scope))
    return out


# ---------------------------------------------------------------- operação (saúde real)
def _replicas(rep):
    """'2/3' -> (2, 3) ; formatos estranhos -> (None, None)."""
    try:
        run_, des = str(rep).split("/")
        return int(run_), int(des)
    except (ValueError, AttributeError):
        return None, None


# Serviços de execução única (migração/seed/cron): ficar em 0/N é o estado NORMAL deles.
_JOB_LIKE = ("flyway", "migrate", "migration", "seed", "init", "install", "setup",
             "backup", "cron", "job", "task", "prune", "cleanup")


def _is_job_like(name, image=""):
    hay = f"{name or ''} {image or ''}".lower()
    return any(t in hay for t in _JOB_LIKE)


# Tipos que rodam CONTINUAMENTE — se um deles termina, é problema, não conclusão.
_LONG_RUNNING = {"banco", "fila", "cache", "cache/fila", "busca", "ingress/proxy",
                 "proxy", "api-gateway", "object-storage"}


def is_job_service(svc):
    """Serviço de execução única (terminar é o comportamento correto dele).

    Três sinais, do mais forte ao mais fraco:
      1. modo *-job do Swarm — inequívoco;
      2. nome/imagem de job (flyway, migrate, seed…);
      3. a task terminou com sucesso (Complete) E o serviço NÃO é de um tipo que roda
         continuamente. É isso que separa "app_database rodando migration numa imagem
         própria" de "postgres que parou" — o segundo tem kind=banco e continua sendo
         reportado. Sem essa checagem de tipo, um banco fora do ar ficaria escondido.
    """
    if str(svc.get("mode") or "").endswith("-job"):
        return True
    if _is_job_like(svc.get("name"), svc.get("image")):
        return True
    return bool(svc.get("completed_job")) and svc.get("kind") not in _LONG_RUNNING


def findings_operational(report):
    """Achados de OPERAÇÃO.

    Régua deliberadamente conservadora: só **nó fora do ar** é crítico. Serviço em 0 réplicas
    pode ser intencional (escalado a zero) ou job concluído — a auditoria não tem como saber,
    então reporta como "verificar", nunca como falha confirmada.
    """
    out = []
    nodes = report.get("nodes")
    for n in (nodes if isinstance(nodes, list) else []):
        state = str(n.get("state") or "").lower()
        if state and state != "ready":
            out.append(_f("OPS_NODE_DOWN", "high", n.get("hostname"),
                          f'nó com estado "{n.get("state")}"',
                          "investigar o nó (docker node inspect) e restaurar o daemon/rede",
                          "cluster-wide"))
        if str(n.get("availability") or "").lower() == "drain":
            out.append(_f("OPS_NODE_DRAIN", "low", n.get("hostname"), "nó em drain (não recebe tasks)",
                          "confirmar se é intencional (manutenção)", "cluster-wide"))

    # versões de engine divergentes entre os nós
    engines = {n.get("engine") for n in (nodes if isinstance(nodes, list) else []) if n.get("engine")}
    if len(engines) > 1:
        out.append(_f("OPS_ENGINE_DRIFT", "low", "cluster",
                      "versões do Docker Engine diferentes entre os nós: " + ", ".join(sorted(engines)),
                      "padronizar a versão do engine nos nós (atualizações em janela, um nó por vez)",
                      "cluster-wide"))

    services = report.get("services")
    for s in (services if isinstance(services, list) else []):
        name = s.get("name")
        running, desired = _replicas(s.get("replicas"))
        if desired is None:
            continue
        if desired > 0 and running == 0:
            # O que faz ser JOB é o modo do Swarm (*-job) ou o nome/imagem. O estado "Complete"
            # NÃO basta: um `replicated` comum também fica Complete quando o container sai com 0
            # e não é reiniciado — e aí é um serviço PARADO (já escondeu banco fora do ar).
            if is_job_service(s):
                out.append(_f("OPS_JOB_COMPLETED", "low", name,
                              f'0 réplicas ({s.get("replicas")}) — serviço de execução única já concluído',
                              "nenhuma ação: é o estado normal de um job de migração/manutenção",
                              "cluster-wide", expected=True))
            else:
                _how = ("concluiu e não foi reiniciado" if s.get("completed_job")
                        else "nenhuma réplica subiu")
                out.append(_f("OPS_SERVICE_STOPPED", "med", name,
                              f'0 réplicas no ar ({s.get("replicas")}) — {_how}',
                              f"confirmar se é intencional: docker service ps {name} --no-trunc",
                              "cluster-wide"))
        elif running is not None and running < desired:
            out.append(_f("OPS_REPLICAS_DEGRADED", "med", name,
                          f'réplicas abaixo do desejado ({s.get("replicas")})',
                          f"docker service ps {name} --no-trunc para ver por que não converge",
                          "cluster-wide"))

        # tasks que falharam recentemente — crash-loop que o "réplicas ok" esconde
        if s.get("tasks_failed"):
            out.append(_f("OPS_TASK_FAILING", "med", name,
                          f'{s["tasks_failed"]} task(s) falharam recentemente'
                          + (f': {s.get("failed_reason")}' if s.get("failed_reason") else ""),
                          f"docker service ps {name} --no-trunc para ver o erro completo",
                          "cluster-wide"))

        # confiabilidade (higiene): sem limite de recurso e sem healthcheck
        lim = s.get("limits") or {}
        if not lim.get("nano_cpus") and not lim.get("mem_bytes"):
            out.append(_f("OPS_NO_LIMITS", "low", name,
                          "sem limite de CPU/memória definido",
                          f"docker service update --limit-cpu 1 --limit-memory 512M {name}",
                          "cluster-wide"))
        if s.get("has_healthcheck") is False:
            out.append(_f("OPS_NO_HEALTHCHECK", "low", name,
                          "sem HEALTHCHECK definido",
                          "definir HEALTHCHECK na imagem ou --health-cmd no service",
                          "cluster-wide"))
    return out


# ---------------------------------------------------------------- falhas de acesso ao cluster
def findings_from_errors(errors, context):
    """Transforma erros de coleta em achados quando revelam um problema REAL de infraestrutura.

    Genérico: olha a mensagem do próprio docker, sem depender de plataforma.
    """
    out, seen = [], set()
    for e in errors or []:
        msg = str(e.get("reason") or "").lower()
        if "certificate has expired" in msg or "certificate is not yet valid" in msg:
            rid = "OPS_TLS_EXPIRED"
            if rid in seen:
                continue
            seen.add(rid)
            out.append(_f(rid, "high", f"daemon/{context}",
                          f'certificado TLS do daemon inválido: {e.get("reason")}',
                          "renovar os certificados do daemon (server + client) e recarregar o "
                          "dockerd; até lá o acesso remoto (CLI, CI/CD, Portainer via TCP) fica quebrado",
                          "cluster-wide"))
        elif "connection refused" in msg or "no route to host" in msg or "i/o timeout" in msg:
            rid = "OPS_DAEMON_UNREACHABLE"
            if rid in seen:
                continue
            seen.add(rid)
            out.append(_f(rid, "high", f"daemon/{context}",
                          f'daemon inacessível: {e.get("reason")}',
                          "verificar rede/firewall e se o dockerd está no ar no host",
                          "cluster-wide"))
    return out


def findings_from_cert(cert_info, context):
    """Achado proativo de validade do certificado TLS do daemon (None = context sem TLS)."""
    if not cert_info:
        return []
    st, days, exp = cert_info["status"], cert_info["days_left"], cert_info["not_after"]
    if st == "expired":
        return [_f("OPS_TLS_EXPIRED", "high", f"daemon/{context}",
                   f"certificado do context expirou em {exp}",
                   "renovar CA/servidor/cliente reutilizando as mesmas chaves privadas (validar com "
                   "openssl verify ANTES de aplicar), ou migrar o context para ssh:// — sem certificado, "
                   "sem expiração. Runbook: references/tls-renewal.md", "cluster-wide")]
    if st == "expiring":
        return [_f("OPS_TLS_EXPIRING", "med", f"daemon/{context}",
                   f"certificado do context expira em {days} dia(s) ({exp})",
                   "renovar antes do vencimento — quando expira, todo acesso remoto (CLI, CI/CD, "
                   "paineis via TCP) para de funcionar. Lembre de atualizar TODOS os clientes "
                   "(incluindo secrets de CI/CD). Runbook: references/tls-renewal.md", "cluster-wide")]
    return []

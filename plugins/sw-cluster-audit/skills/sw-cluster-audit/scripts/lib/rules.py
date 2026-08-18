"""Regras determinísticas de finding sobre um workload já redigido (container ou service).

Os findings vêm daqui (regra), NUNCA do agente — o agente só prioriza e escreve a prosa.
"""
# Paths de host cujo bind é sensível. Match por prefixo (path == p ou começa com p + "/").
_SENSITIVE = ("/var/run/docker.sock", "/run/docker.sock", "/etc", "/root",
              "/var/run", "/proc", "/sys")


def _f(rid, sev, obj, evidence, fix, scope):
    return {"rule_id": rid, "severity": sev, "object": obj,
            "evidence": evidence, "fix": fix, "scope": scope}


def _is_sensitive(src):
    if not src:
        return False
    if src == "/":                       # bind da raiz do host
        return True
    return any(src == p or src.startswith(p + "/") for p in _SENSITIVE)


def _is_root(user):
    # None = sem USER definido (default do Docker é root); "0"/"0:0" = uid 0
    if user is None:
        return True
    u = str(user).lower()
    return u == "root" or u == "0" or u.startswith("0:")


def findings_for_workload(wl, scope):
    """wl = {name?, image, tag, digest, user, env_keys, privileged, mounts, ports}.

    `ports` de container = [{port, host_ip, host_port}]; de service = [num] (publish cluster-wide).
    """
    out = []
    name = wl.get("name") or wl.get("image")
    if wl.get("privileged"):
        out.append(_f("SEC_PRIVILEGED", "high", name, "Privileged=true",
                      "remover --privileged; conceder só as capabilities necessárias", scope))
    if any(_is_sensitive(m.get("source")) for m in (wl.get("mounts") or [])):
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
                      f"imagem {wl.get('image')}:{wl.get('tag')} sem digest fixo",
                      "fixar tag imutável + digest (image@sha256:...)", scope))
    if _is_root(wl.get("user")):
        out.append(_f("SEC_USER_ROOT", "med", name,
                      "container roda como root (user root/uid 0 ou USER ausente)",
                      "definir USER não-root na imagem/service", scope))
    return out

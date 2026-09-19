"""Redação com field-allowlist POSITIVA: só os campos listados saem; o resto é descartado.

Vale pra TODOS os inspects. NUNCA serializa Env/Cmd/Args/Labels (nem em Config.*, nem em
TaskTemplate.ContainerSpec.*, nem Spec.Labels). Env vira só as CHAVES.
"""
import re


def _env_keys(env):
    """['K=v', ...] -> ['K', ...] (descarta o valor)."""
    return [e.split("=", 1)[0] for e in (env or [])]


def _container_ports(insp):
    """Preserva os bindings de host (necessários pra regra de porta em 0.0.0.0)."""
    raw = (insp.get("NetworkSettings", {}) or {}).get("Ports", {}) or {}
    out = []
    for port, binds in raw.items():
        if binds:
            for b in binds:
                out.append({"port": port, "host_ip": b.get("HostIp"), "host_port": b.get("HostPort")})
        else:
            out.append({"port": port, "host_ip": None, "host_port": None})
    return out


def redact_container(insp):
    c = insp.get("Config", {}) or {}
    h = insp.get("HostConfig", {}) or {}
    return {  # <-- só estes campos existem na saída (positivo)
        "image": c.get("Image"),
        "user": c.get("User") or None,
        "env_keys": _env_keys(c.get("Env")),
        "privileged": bool(h.get("Privileged", False)),
        "cap_add": h.get("CapAdd") or [],
        "mounts": [{"type": m.get("Type"), "source": m.get("Source"), "target": m.get("Destination")}
                   for m in (insp.get("Mounts") or [])],
        "ports": _container_ports(insp),
    }


def _res(block):
    """Limits/Reservations do TaskTemplate → só os números (nunca outros campos)."""
    b = block or {}
    return {"nano_cpus": b.get("NanoCPUs"), "mem_bytes": b.get("MemoryBytes")}


def _mode(mode_spec):
    """replicated | global | replicated-job | global-job (o sufixo -job importa pras regras)."""
    m = mode_spec or {}
    for key, name in (("ReplicatedJob", "replicated-job"), ("GlobalJob", "global-job"),
                      ("Global", "global")):
        if key in m:
            return name
    return "replicated"


def redact_service(insp):
    spec = insp.get("Spec", {}) or {}
    tt = spec.get("TaskTemplate", {}) or {}
    cs = tt.get("ContainerSpec", {}) or {}
    ep = spec.get("EndpointSpec", {}) or {}
    res = tt.get("Resources", {}) or {}
    return {
        # --- confiabilidade (números e booleanos; nada de conteúdo de comando) ---
        "limits": _res(res.get("Limits")),
        "reservations": _res(res.get("Reservations")),
        # Healthcheck.Test pode conter credencial → guarda só SE existe, nunca o comando
        "has_healthcheck": bool((cs.get("Healthcheck") or {}).get("Test")),
        "constraints": list((tt.get("Placement") or {}).get("Constraints") or []),
        "updated_at": insp.get("UpdatedAt"),
        "mode": _mode(spec.get("Mode")),
        "name": spec.get("Name"),
        "image": cs.get("Image"),
        "user": cs.get("User") or None,
        "env_keys": _env_keys(cs.get("Env")),
        "privileged": bool((cs.get("Privileges", {}) or {}).get("Privileged") or False),
        "mounts": [{"type": m.get("Type"), "source": m.get("Source"), "target": m.get("Target")}
                   for m in (cs.get("Mounts") or [])],
        "ports": [p.get("PublishedPort") for p in (ep.get("Ports") or [])],
        "routing_labels": redact_labels(spec.get("Labels")),   # traefik.* (valores sensíveis redigidos)
    }


_CRED = re.compile(r"//[^/@\s]+:[^/@\s]+@")  # http://user:pass@host -> http://***@host

# Labels de roteamento (analisáveis) — prefixos allowlisted.
_LABEL_PREFIXES = ("traefik.",)
# Chaves cujo VALOR é redigido mesmo estando num prefixo permitido (podem carregar segredo).
_SENSITIVE_LABEL = re.compile(
    r"(basicauth|\.users|password|passwd|secret|token|apikey|api[_-]?key|credential|authorization)", re.I)


def redact_labels(labels):
    """Extrai labels de roteamento (prefixos allowlisted); REDIGE o valor de chaves sensíveis.

    Mantém a config de roteamento (rule/entrypoints/service/tls) visível pra análise, sem vazar
    hash de basic-auth / tokens que às vezes vivem em labels do Traefik.
    """
    out = {}
    for k, v in (labels or {}).items():
        if not any(k.startswith(p) for p in _LABEL_PREFIXES):
            continue
        if _SENSITIVE_LABEL.search(k):
            out[k] = "***"                      # chave sensível → valor todo redigido
        elif isinstance(v, str):
            out[k] = _CRED.sub("//***@", v)      # senão, redige cred embutida em URL (loadbalancer.server.url)
        else:
            out[k] = v
    return out


def scrub_text(text, limit=200):
    """Sanitiza texto livre vindo do daemon (ex.: erro de task) antes de entrar no relatório.

    A coleta usa allowlist POSITIVA de campos; texto de erro é a única exceção — então passa
    pelo mesmo scrub de credencial-em-URL e é truncado para não virar um dump.
    """
    return _CRED.sub("//***@", str(text or ""))[:limit]


def scrub_info(info):
    mirrors = (info.get("RegistryConfig", {}) or {}).get("Mirrors") or []
    return {
        "server_version": info.get("ServerVersion"),
        "registry_mirrors": [_CRED.sub("//***@", m) for m in mirrors],
    }

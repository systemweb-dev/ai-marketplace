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
        "routing_labels": redact_labels(spec.get("Labels")),   # só prefixo declarado; valor sensível redigido
    }


# http://user:pass@host -> http://***@host. A senha pode ter `@` e `/`, então vai até o último `@`
# do trecho; só números logo depois do `:` são porta, e aí o `@` adiante é do caminho.
_CRED = re.compile(r"//[^/@\s:]*:(?!\d{1,5}(?:[/?#\s]|$))\S*@")

# Labels de roteamento (analisáveis) — os prefixos vêm de `references/produtos.toml`, onde
# cada proxy declara como ELE publica rota. Era `("traefik.",)` cravado aqui, e com outro proxy
# a configuração de roteamento ficava invisível no relatório: não vazava, mas também não
# aparecia. Acrescentar um proxy passou a ser um bloco de dados.
# Chaves cujo VALOR é redigido mesmo estando num prefixo permitido (podem carregar segredo).
_SENSITIVE_LABEL = re.compile(
    r"(basicauth|\.users|password|passwd|secret|token|apikey|api[_-]?key|credential|authorization"
    r"|customrequestheaders|customresponseheaders|\.cookie)", re.I)


def redact_labels(labels):
    """Extrai labels de roteamento (prefixos allowlisted); REDIGE o valor de chaves sensíveis.

    Mantém a config de roteamento (rule/entrypoints/service/tls) visível pra análise, sem vazar
    hash de basic-auth / tokens que às vezes vivem em labels do Traefik.
    """
    from lib.produtos import prefixos_de_rota

    prefixos = prefixos_de_rota()
    out = {}
    for k, v in (labels or {}).items():
        if not any(k.startswith(p) for p in prefixos):
            continue
        if _SENSITIVE_LABEL.search(k):
            out[k] = "***"                      # chave sensível → valor todo redigido
        elif isinstance(v, str):
            out[k] = _CRED.sub("//***@", v)      # senão, redige cred embutida em URL (loadbalancer.server.url)
        else:
            out[k] = v
    return out


_VALOR = r"""("[^"\n]*"|'[^'\n]*'|\S+)"""
_SEGREDOS = (
    re.compile(r"(--(?:[\w-]+-)?(?:password|token|secret)(?:=|[ \t]+))" + _VALOR, re.I),
    re.compile(r"(\b\w*PASSWORD=|\b(?:\w+_)?(?:TOKEN|SECRET)=|\b\w+_KEY=)" + _VALOR, re.I),
    re.compile(r"(\bAuthorization:[ \t]*(?:Bearer|Basic)[ \t]+)" + _VALOR, re.I),
    re.compile(r"(\b(?:mysql|mysqldump|mysqladmin|mariadb|mariadb-dump)\b[^\n|;&]*?[ \t]-p)" + _VALOR),
)
_REFERENCIA = re.compile(r"\$(?:\w+|\{\w+\}|\(.*)")     # `${X:-valor}` fica de fora: traz um valor
_FECHO = ".,;:)]`'\""
_PROSA = {"para", "no", "na", "em", "e", "ou", "de", "do", "da", "com", "é", "foi", "não"}


def _ocultar(casado):
    """Troca só o valor. Referência a variável não é segredo, e `--password para` é uma frase."""
    prefixo, valor = casado.groups()
    entre_aspas = len(valor) >= 2 and valor[0] in "\"'" and valor[-1] == valor[0]
    nucleo = valor[1:-1] if entre_aspas else valor.rstrip(_FECHO)
    if not nucleo or _REFERENCIA.fullmatch(nucleo):
        return casado.group(0)
    if prefixo[-1].isspace() and (nucleo.startswith("--") or nucleo.lower() in _PROSA):
        return casado.group(0)
    if entre_aspas:
        return f"{prefixo}{valor[0]}***{valor[0]}"
    return f"{prefixo}***{valor[len(nucleo):]}"


def scrub_text(text, limit=200):
    """Sanitiza texto livre (erro do daemon, texto e comando do agente) antes do relatório.

    A coleta usa allowlist POSITIVA de campos; texto livre é a exceção. Mascara credencial em
    URL, flag, variável, cabeçalho e `-p` do mysql, e trunca para não virar um dump.
    """
    texto = _CRED.sub("//***@", str(text or ""))
    for padrao in _SEGREDOS:
        texto = padrao.sub(_ocultar, texto)
    return texto[:limit]


def scrub_info(info):
    mirrors = (info.get("RegistryConfig", {}) or {}).get("Mirrors") or []
    return {
        "server_version": info.get("ServerVersion"),
        "registry_mirrors": [_CRED.sub("//***@", m) for m in mirrors],
    }
